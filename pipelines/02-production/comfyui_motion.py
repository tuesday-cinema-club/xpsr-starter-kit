#!/usr/bin/env python3
"""
Gate 03, second pass: animate approved keyframes with a local motion model.

Two-pass motion: lock a still first, then animate only the frames the director
approved. This script refuses to run until frames_state.json says Approve.
For each shot it:
  1. uploads the approved shot_NN_keyframe.png as the first frame
  2. writes a motion prompt from the shot's action, camera move and the
     bible's lighting key, with a fixed seed
  3. asks for as many frames as the shot needs, up to the model's limit
     (Wan 2.2 5B: 121 frames, about 5 seconds at 24 fps)
  4. downloads the frames and encodes shot_NN_motion.mp4 with ffmpeg
  5. appends a provenance.csv row (stage "temporal")

The motion clips go back to the director at Gate 03 before the edit.
Nothing leaves your machine. Standard library plus ffmpeg.

Example:
    python3 pipelines/02-production/comfyui_motion.py \\
        --shots my-project/shots.json \\
        --bible templates/ember-and-oak-bible.json \\
        --frames my-project/frames \\
        --out my-project/motion \\
        --comfyui-dir ~/ComfyUI
"""

import argparse
import copy
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from common import append_provenance, file_sha256_short, load_json, new_state, say, write_json  # noqa: E402
from comfyui_client import ComfyUI, nodes_of  # noqa: E402

DEFAULT_WORKFLOW = os.path.join(HERE, "workflows", "wan22_ti2v_5b_keyframe_to_motion.json")

CAMERA = {
    "Static": "The camera is locked off on a tripod and does not move.",
    "Push In": "The camera slowly pushes in toward the subject.",
    "Pull Out": "The camera slowly dollies backward, away from the subject, who gets smaller in frame as more of the room is revealed.",
    "Pan Left": "The camera slowly pans left.",
    "Pan Right": "The camera slowly pans right.",
    "Tilt Up": "The camera slowly tilts up.",
    "Tilt Down": "The camera slowly tilts down.",
    "Handheld": "Gentle handheld camera movement.",
}


def frames_for(duration: float, fps: float, max_frames: int) -> int:
    """Frame count for a shot: Wan wants 4k+1 frames, capped at the model's limit."""
    wanted = max(1, round(duration * fps))
    return min(max_frames, 4 * math.ceil((wanted - 1) / 4) + 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--shots", required=True, help="Approved shots.json")
    p.add_argument("--bible", required=True, help="Project bible.json (lighting key and negative prompt)")
    p.add_argument("--frames", required=True, help="Folder with the approved keyframes and frames_state.json")
    p.add_argument("--out", required=True, help="Where to save the motion clips")
    p.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="ComfyUI API-format image-to-video workflow")
    p.add_argument("--server", default="127.0.0.1:8188")
    p.add_argument("--seed", type=int, default=520891, help="Base seed; shot N uses seed + N")
    p.add_argument("--steps", type=int)
    p.add_argument("--fps", type=float, default=24.0)
    p.add_argument("--max-frames", type=int, default=121, help="Longest clip the motion model makes (default 121)")
    p.add_argument("--only", type=int, action="append", help="Animate only this shot number (repeatable)")
    p.add_argument("--comfyui-dir", default=os.environ.get("COMFYUI_DIR"),
                   help="ComfyUI folder, used to hash the model for provenance")
    p.add_argument("--provenance", help="provenance.csv (default: next to --shots)")
    p.add_argument("--suffix", default="", help="Added to output names, e.g. '_take2'")
    args = p.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is required: see environment/README.md")
    state_file = os.path.join(args.frames, "frames_state.json")
    if not os.path.exists(state_file) or load_json(state_file).get("status") != "approved":
        sys.exit(f"Gate 03 has not approved these keyframes ({state_file}). "
                 "Two-pass motion: approve the stills with gate.py first.")

    shots = load_json(args.shots)
    bible = load_json(args.bible)
    rules = bible["visual_rules"]
    template = load_json(args.workflow)
    prov = args.provenance or os.path.join(os.path.dirname(args.shots) or ".", "provenance.csv")
    os.makedirs(args.out, exist_ok=True)

    comfy = ComfyUI(args.server)
    stats = comfy.ping()
    say("ok", f"ComfyUI {stats['system'].get('comfyui_version', '')} is up on "
        f"{stats.get('devices', [{}])[0].get('name', 'unknown device')}")

    unet = nodes_of(template, "UNETLoader")[0]
    model_name = template[unet]["inputs"]["unet_name"]
    model_hash = "unhashed"
    if args.comfyui_dir:
        path = os.path.join(os.path.expanduser(args.comfyui_dir), "models", "diffusion_models", model_name)
        if os.path.exists(path):
            say("*", f"Hashing {model_name} for provenance (cached after the first run) ...")
            model_hash = file_sha256_short(path, cache=os.path.join(os.path.expanduser(args.comfyui_dir), ".tcc_hashes.json"))

    encoders = nodes_of(template, "CLIPTextEncode")
    positive = next(k for k in encoders if template[k]["_meta"]["title"].startswith("Positive"))
    negative = next((k for k in encoders if template[k]["_meta"]["title"].startswith("Negative")), None)
    sampler = nodes_of(template, "KSampler")[0]
    latent = nodes_of(template, "Wan22ImageToVideoLatent")[0]
    first_frame = nodes_of(template, "LoadImage")[0]
    saver = nodes_of(template, "SaveImage")[0]

    records = []
    for shot in shots["shots"]:
        n = shot["shot_number"]
        if args.only and n not in args.only:
            continue
        keyframe = os.path.join(args.frames, f"shot_{n:02d}_keyframe.png")
        if not os.path.exists(keyframe):
            sys.exit(f"Missing approved keyframe {keyframe}")
        wf = copy.deepcopy(template)
        prompt = (f"{shot['action_description']} {CAMERA.get(shot['camera_move'], '')} "
                  f"{rules.get('lighting_key', '')}.").strip()
        wf[positive]["inputs"]["text"] = prompt
        if negative and rules.get("negative_prompt"):
            wf[negative]["inputs"]["text"] += ", " + rules["negative_prompt"]
        length = frames_for(shot["duration_sec"], args.fps, args.max_frames)
        wf[latent]["inputs"]["length"] = length
        seed = args.seed + n
        wf[sampler]["inputs"]["seed"] = seed
        if args.steps:
            wf[sampler]["inputs"]["steps"] = args.steps
        wf[first_frame]["inputs"]["image"] = comfy.upload_image(keyframe)
        wf[saver]["inputs"]["filename_prefix"] = f"{bible['project_id']}_motion{n:02d}"

        say("*", f"Shot {n}: animating {length} frames ({length / args.fps:.1f}s of {shot['duration_sec']}s, "
            f"{shot['camera_move']}, seed {seed}) ...")
        t0 = time.time()
        outputs = comfy.wait(comfy.queue(wf), timeout=4 * 3600)
        images = outputs[saver]["images"]
        dest = os.path.join(args.out, f"shot_{n:02d}_motion{args.suffix}.mp4")
        with tempfile.TemporaryDirectory() as tmp:
            for i, img in enumerate(images):
                comfy.download(img, os.path.join(tmp, f"f_{i:04d}.png"))
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-framerate", str(args.fps),
                            "-i", os.path.join(tmp, "f_%04d.png"), "-c:v", "libx264", "-preset", "slow",
                            "-crf", "14", "-pix_fmt", "yuv420p", dest], check=True)
        took = time.time() - t0
        say("ok", f"Shot {n}: {dest} ({len(images)} frames, {took / 60:.1f} min)")
        if length / args.fps < shot["duration_sec"] - 0.05:
            say("!", f"Shot {n}: the clip is {length / args.fps:.1f}s; the edit will hold its last frame "
                f"for {shot['duration_sec'] - length / args.fps:.1f}s")

        append_provenance(prov, asset_id=f"shot_{n:02d}_motion{args.suffix}", stage="temporal",
                          tool_or_model=f"ComfyUI/{model_name}", checkpoint_hash=model_hash, seed=seed,
                          prompt_or_input=f"{prompt} | first frame: {os.path.basename(keyframe)}")
        records.append({"shot_number": n, "file": os.path.basename(dest), "first_frame": os.path.basename(keyframe),
                        "seed": seed, "frames": len(images), "prompt": prompt, "seconds": round(took, 1)})

    write_json(os.path.join(args.out, f"motion{args.suffix}.json"),
               {"workflow": os.path.basename(args.workflow), "model": model_name,
                "model_sha256_short": model_hash, "fps": args.fps, "clips": records})
    state_path = os.path.join(args.out, f"motion_state{args.suffix}.json")
    write_json(state_path, new_state(bible["project_id"], "produce", os.path.join(args.out, f"motion{args.suffix}.json"),
                                     {"schema": "pass", "bible_match": "not_applicable"}))
    say(">", "Gate 03 paused again: the director watches every clip before the edit.")
    print(f"      python3 pipelines/gate.py --state {state_path} --decision Approve --by \"<director>\" --provenance {prov}")


if __name__ == "__main__":
    main()
