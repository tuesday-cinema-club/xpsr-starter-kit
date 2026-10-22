#!/usr/bin/env python3
"""
Gate 03: render one keyframe per shot through a local ComfyUI server.

For each shot in shots.json this script:
  1. uploads the Blender depth pass (shot_NN_depth.png) to ComfyUI
  2. fills the workflow with the shot's visual_prompt + the bible's style and
     negative prompts, and a fixed seed
  3. queues it on http://127.0.0.1:8188 and waits for the result
  4. downloads the frame to --out as shot_NN_keyframe.png
  5. appends a provenance.csv row: model, checkpoint hash, seed, prompt

Nothing leaves your machine. Standard library only.

Example:
    python3 pipelines/02-production/comfyui_client.py \\
        --shots my-project/shots.json \\
        --bible templates/ember-and-oak-bible.json \\
        --previs my-project/previs \\
        --out my-project/frames \\
        --comfyui-dir ~/ComfyUI

Use --workflow workflows/sdxl_txt2img.json to render without depth passes.
"""

import argparse
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import append_provenance, file_sha256_short, load_json, new_state, say, write_json  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WORKFLOW = os.path.join(HERE, "workflows", "sdxl_depth_controlnet.json")


class ComfyUI:
    def __init__(self, server: str):
        self.base = server if server.startswith("http") else f"http://{server}"
        self.client_id = uuid.uuid4().hex

    def _get(self, path: str):
        with urllib.request.urlopen(f"{self.base}{path}", timeout=30) as r:
            return r.read()

    def ping(self) -> dict:
        try:
            return json.loads(self._get("/system_stats"))
        except (urllib.error.URLError, ConnectionError) as exc:
            sys.exit(f"ComfyUI is not reachable at {self.base} ({exc}).\n"
                     "Start it with: python main.py --listen 127.0.0.1 --port 8188")

    def upload_image(self, path: str) -> str:
        boundary = uuid.uuid4().hex
        name = os.path.basename(path)
        with open(path, "rb") as f:
            data = f.read()
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            f"Content-Type: image/png\r\n\r\n"
        ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(f"{self.base}/upload/image", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            info = json.loads(r.read())
        return f"{info['subfolder']}/{info['name']}" if info.get("subfolder") else info["name"]

    def queue(self, workflow: dict) -> str:
        payload = json.dumps({"prompt": workflow, "client_id": self.client_id}).encode()
        req = urllib.request.Request(f"{self.base}/prompt", data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())["prompt_id"]
        except urllib.error.HTTPError as exc:
            sys.exit(f"ComfyUI rejected the workflow: {exc.read().decode('utf-8', 'replace')}")

    def wait(self, prompt_id: str, timeout: int = 1800) -> dict:
        start = time.time()
        while time.time() - start < timeout:
            hist = json.loads(self._get(f"/history/{prompt_id}"))
            if prompt_id in hist:
                entry = hist[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    sys.exit(f"ComfyUI reported an error: {json.dumps(status.get('messages', []))[:800]}")
                if entry.get("outputs"):
                    return entry["outputs"]
            time.sleep(1.0)
        sys.exit(f"Timed out after {timeout}s waiting for ComfyUI")

    def download(self, image: dict, dest: str) -> None:
        q = urllib.parse.urlencode({"filename": image["filename"], "subfolder": image.get("subfolder", ""),
                                    "type": image.get("type", "output")})
        with open(dest, "wb") as f:
            f.write(self._get(f"/view?{q}"))


def nodes_of(workflow: dict, class_type: str):
    return [k for k, v in workflow.items() if v.get("class_type") == class_type]


def find_roles(workflow: dict) -> dict:
    """Find the nodes the client fills in, by convention rather than fixed ids:

    - model:    CheckpointLoaderSimple (models/checkpoints) or UNETLoader (models/diffusion_models)
    - positive: the CLIPTextEncode whose title starts with "Positive"; its _meta may hold
                "tcc_prompt_template" with a {prompt} placeholder
    - negative: the CLIPTextEncode whose title starts with "Negative" (optional)
    - seed:     KSampler.seed or RandomNoise.noise_seed
    - steps:    KSampler.steps or Flux2Scheduler.steps
    - guide:    a LoadImage node; its _meta "tcc_guide" says which Blender pass to load
                ("depth", the default, or "grey")
    """
    def titled(prefix):
        return next((k for k in nodes_of(workflow, "CLIPTextEncode")
                     if workflow[k].get("_meta", {}).get("title", "").startswith(prefix)), None)

    if nodes_of(workflow, "CheckpointLoaderSimple"):
        k = nodes_of(workflow, "CheckpointLoaderSimple")[0]
        model = (workflow[k]["inputs"]["ckpt_name"], "checkpoints")
    elif nodes_of(workflow, "UNETLoader"):
        k = nodes_of(workflow, "UNETLoader")[0]
        model = (workflow[k]["inputs"]["unet_name"], "diffusion_models")
    else:
        sys.exit("Workflow has no CheckpointLoaderSimple or UNETLoader node")
    positive = titled("Positive") or ("6" if "6" in workflow else None)
    if not positive:
        sys.exit("Workflow needs a CLIPTextEncode node titled 'Positive ...'")
    negative = titled("Negative")
    if nodes_of(workflow, "KSampler"):
        k = nodes_of(workflow, "KSampler")[0]
        seed, steps = (k, "seed"), (k, "steps")
    else:
        seed = (nodes_of(workflow, "RandomNoise")[0], "noise_seed")
        steps = (nodes_of(workflow, "Flux2Scheduler")[0], "steps")
    guides = nodes_of(workflow, "LoadImage")
    guide = guides[0] if guides else None
    return {
        "model": model, "positive": positive, "negative": negative, "seed": seed, "steps": steps,
        "guide": guide,
        "guide_kind": workflow[guide].get("_meta", {}).get("tcc_guide", "depth") if guide else None,
        "prompt_template": workflow[positive].get("_meta", {}).get("tcc_prompt_template", "{prompt}"),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--shots", required=True, help="Approved shots.json")
    p.add_argument("--bible", required=True, help="Project bible.json (style and negative prompts)")
    p.add_argument("--previs", help="Folder with shot_NN_depth.png from blender_previs.py")
    p.add_argument("--out", required=True, help="Where to save keyframes")
    p.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="ComfyUI API-format workflow JSON")
    p.add_argument("--server", default="127.0.0.1:8188")
    p.add_argument("--seed", type=int, default=420891, help="Base seed; shot N uses seed + N")
    p.add_argument("--steps", type=int)
    p.add_argument("--depth-strength", type=float, help="ControlNet strength 0-1 (default from workflow)")
    p.add_argument("--depth-end", type=float, help="Stop applying depth at this fraction of the steps, 0-1 (default from workflow)")
    p.add_argument("--only", type=int, action="append", help="Render only this shot number (repeatable)")
    p.add_argument("--comfyui-dir", default=os.environ.get("COMFYUI_DIR"),
                   help="ComfyUI folder, used to hash the checkpoint for provenance")
    p.add_argument("--provenance", help="provenance.csv (default: next to --shots)")
    p.add_argument("--lock-characters", action="store_true",
                   help="Append each on-screen character's visual_lock from the bible to the prompt (better continuity)")
    p.add_argument("--suffix", default="", help="Added to output names, e.g. '_take3' to keep alternate takes")
    args = p.parse_args()

    shots = load_json(args.shots)
    bible = load_json(args.bible)
    template = load_json(args.workflow)
    rules = bible["visual_rules"]
    prov = args.provenance or os.path.join(os.path.dirname(args.shots) or ".", "provenance.csv")
    os.makedirs(args.out, exist_ok=True)

    comfy = ComfyUI(args.server)
    stats = comfy.ping()
    device = stats.get("devices", [{}])[0].get("name", "unknown device")
    say("ok", f"ComfyUI {stats['system'].get('comfyui_version', '')} is up on {device}")

    roles = find_roles(template)
    model_name, model_folder = roles["model"]
    ckpt_hash = "unhashed"
    if args.comfyui_dir:
        ckpt_path = os.path.join(os.path.expanduser(args.comfyui_dir), "models", model_folder, model_name)
        if os.path.exists(ckpt_path):
            say("*", f"Hashing {model_name} for provenance (cached after the first run) ...")
            ckpt_hash = file_sha256_short(ckpt_path, cache=os.path.join(os.path.expanduser(args.comfyui_dir), ".tcc_hashes.json"))
    cn_nodes = nodes_of(template, "ControlNetLoader")
    cn_name = template[cn_nodes[0]]["inputs"]["control_net_name"] if cn_nodes else None
    guide_kind = roles["guide_kind"]

    records = []
    for shot in shots["shots"]:
        n = shot["shot_number"]
        if args.only and n not in args.only:
            continue
        wf = copy.deepcopy(template)
        base_prompt = f"{shot['visual_prompt']}, {rules.get('style_prompt', '')}".strip(", ")
        if args.lock_characters and shot["characters"]:
            locks = {c["id"]: c for c in bible["characters"]}
            described = [f"{locks[c]['name']}: {locks[c]['visual_lock']}" for c in shot["characters"] if c in locks]
            base_prompt += ". Characters, exactly as described: " + "; ".join(described)
        prompt = roles["prompt_template"].replace("{prompt}", base_prompt)
        wf[roles["positive"]]["inputs"]["text"] = prompt
        if roles["negative"]:
            wf[roles["negative"]]["inputs"]["text"] = rules.get("negative_prompt", "")
        seed = args.seed + n
        node_id, key = roles["seed"]
        wf[node_id]["inputs"][key] = seed
        if args.steps:
            node_id, key = roles["steps"]
            wf[node_id]["inputs"][key] = args.steps
        wf[nodes_of(wf, "SaveImage")[0]]["inputs"]["filename_prefix"] = f"{bible['project_id']}_shot{n:02d}"

        guide_src = None
        if roles["guide"]:
            if not args.previs:
                sys.exit(f"This workflow needs {guide_kind} passes from Blender: pass --previs <folder>")
            guide_src = os.path.join(args.previs, f"shot_{n:02d}_{guide_kind}.png")
            if not os.path.exists(guide_src):
                sys.exit(f"Missing {guide_src}. Run blender_previs.py first.")
            wf[roles["guide"]]["inputs"]["image"] = comfy.upload_image(guide_src)
            apply_nodes = nodes_of(wf, "ControlNetApplyAdvanced")
            if apply_nodes:
                apply_node = wf[apply_nodes[0]]["inputs"]
                if args.depth_strength is not None:
                    apply_node["strength"] = args.depth_strength
                if args.depth_end is not None:
                    apply_node["end_percent"] = args.depth_end

        say("*", f"Shot {n}: queueing ({shot['framing']}, {shot['lens_mm']}mm, seed {seed}) ...")
        t0 = time.time()
        outputs = comfy.wait(comfy.queue(wf))
        image = next(img for out in outputs.values() for img in out.get("images", []))
        dest = os.path.join(args.out, f"shot_{n:02d}_keyframe{args.suffix}.png")
        comfy.download(image, dest)
        took = time.time() - t0
        say("ok", f"Shot {n}: {dest} ({took:.0f}s)")

        tool = f"ComfyUI/{model_name}" + (f" + {cn_name}" if cn_name and guide_src else "")
        append_provenance(prov, asset_id=f"shot_{n:02d}_keyframe{args.suffix}", stage="keyframe", tool_or_model=tool,
                          checkpoint_hash=ckpt_hash, seed=seed,
                          prompt_or_input=prompt + (f" | {guide_kind}: {os.path.basename(guide_src)}" if guide_src else ""))
        records.append({"shot_number": n, "file": os.path.basename(dest), "seed": seed, "prompt": prompt,
                        "guide": os.path.basename(guide_src) if guide_src else None,
                        "seconds": round(took, 1)})

    write_json(os.path.join(args.out, f"frames{args.suffix}.json"),
               {"workflow": os.path.basename(args.workflow), "checkpoint": model_name,
                "checkpoint_sha256_short": ckpt_hash, "controlnet": cn_name, "frames": records})
    state_path = os.path.join(args.out, f"frames_state{args.suffix}.json")
    write_json(state_path, new_state(bible["project_id"], "produce", os.path.join(args.out, f"frames{args.suffix}.json"),
                                     {"schema": "pass", "bible_match": "not_applicable"}))
    say(">", "Gate 03 paused: the director approves keyframes before any motion or edit.")
    print(f"      python3 pipelines/gate.py --state {state_path} --decision Approve --by \"<director>\" --provenance {prov}")
    print(f"      Open {args.out} and review every frame. Fix problems in GIMP or rerun with --only N --seed S.")


if __name__ == "__main__":
    main()
