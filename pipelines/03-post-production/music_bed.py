#!/usr/bin/env python3
"""
Generate takes of a music bed with Meta's MusicGen (AudioCraft), offline.

Each take is a stereo WAV at the shot list's total length (or --duration),
with a fixed seed, a JSON sidecar and a PENDING_REVIEW provenance row. A person
listens to every take and picks one before it goes under the voice; the pick is
passed to assemble_animatic.py --music.

Needs AudioCraft (`pip install audiocraft`, which pulls in PyTorch), so run it
with that Python, not the kit's standard-library Python:

    ~/tools/audiocraft/.venv/bin/python pipelines/03-post-production/music_bed.py \\
        --shots my-project/shots.json --takes 3 \\
        --prompt "warm minimal ambient underscore, felt piano over soft synth pads, no drums" \\
        --out-dir my-project/audio/music

Models and memory (MusicGen weights are CC-BY-NC 4.0: non-commercial use only):
  facebook/musicgen-stereo-medium  1.5B, runs on an 8 GB GPU, seconds per take
  facebook/musicgen-stereo-large   3.3B, too big for 8 GB at full length: use
                                   --device cpu (about 25 minutes per 30 s take on
                                   64 cores) or --device cuda --half for clips of
                                   about 5 seconds, which is enough to audition
                                   a prompt.

Describe instruments, tempo and mood. Do not name artists: the bed should not
imitate anyone.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import append_provenance, load_json, say  # noqa: E402


def load(model_name: str, device: str, half: bool):
    import torch
    from audiocraft.models import MusicGen
    if device == "cpu":
        torch.set_num_threads(os.cpu_count() or 8)
        return MusicGen.get_pretrained(model_name, device="cpu")
    if not half:
        return MusicGen.get_pretrained(model_name, device="cuda")
    # Load on the CPU, then move a half-precision language model to the GPU.
    # The T5 text encoder is kept outside the module tree, so move it by hand.
    m = MusicGen.get_pretrained(model_name, device="cpu")
    m.lm = m.lm.half().to("cuda")
    m.compression_model = m.compression_model.to("cuda")
    for c in m.lm.condition_provider.conditioners.values():
        if hasattr(c, "t5"):
            c.t5 = c.t5.to("cuda")
        c.device = "cuda"
    m.device = torch.device("cuda")
    return m


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompt", required=True, help="Instruments, tempo and mood; no artist names")
    p.add_argument("--shots", help="shots.json: the bed is as long as the spot")
    p.add_argument("--duration", type=float, help="Seconds (default: total of --shots)")
    p.add_argument("--takes", type=int, default=3)
    p.add_argument("--seed", type=int, default=700, help="Take N uses seed + N")
    p.add_argument("--model", default="facebook/musicgen-stereo-medium")
    p.add_argument("--device", choices=["cuda", "cpu"], default=None, help="Default: cuda if available")
    p.add_argument("--half", action="store_true", help="Half precision on the GPU (short clips with the large model)")
    p.add_argument("--name", default="music_take", help="File name stem")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--provenance", help="provenance.csv (default: next to --shots; none without --shots)")
    args = p.parse_args()

    try:
        import soundfile as sf
        import torch
    except ImportError:
        sys.exit(f"AudioCraft is not installed in this Python:\n  {sys.executable} -m pip install audiocraft soundfile")
    if args.duration is None:
        if not args.shots:
            sys.exit("Pass --shots or --duration")
        args.duration = sum(s["duration_sec"] for s in load_json(args.shots)["shots"])
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    prov = args.provenance or (os.path.join(os.path.dirname(args.shots) or ".", "provenance.csv") if args.shots else None)
    os.makedirs(args.out_dir, exist_ok=True)

    say("*", f"Loading {args.model} on {device}{' (half precision)' if args.half else ''} ...")
    model = load(args.model, device, args.half)
    model.set_generation_params(duration=args.duration, use_sampling=True, top_k=250, cfg_coef=3.0)

    takes = []
    for n in range(1, args.takes + 1):
        seed = args.seed + n
        torch.manual_seed(seed)
        say("*", f"Take {n}: {args.duration:g}s, seed {seed} ...")
        start = time.time()
        wav = model.generate([args.prompt])[0].float().cpu().numpy().T
        elapsed = time.time() - start
        name = f"{args.name}_{n}.wav"
        sf.write(os.path.join(args.out_dir, name), wav, model.sample_rate)
        takes.append({"take": n, "file": name, "seed": seed, "seconds": round(len(wav) / model.sample_rate, 2),
                      "render_seconds": round(elapsed, 1)})
        if prov:
            append_provenance(prov, asset_id=name, stage="music", tool_or_model=f"audiocraft/{args.model}",
                              seed=seed, prompt_or_input=args.prompt)
        say("ok", f"Take {n}: {name} ({elapsed:.0f}s to render)")

    meta = {"model": args.model, "device": device, "half": args.half, "prompt": args.prompt,
            "duration": args.duration, "sample_rate": model.sample_rate, "takes": takes}
    with open(os.path.join(args.out_dir, f"{args.name}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    say(">", "Listen to every take, pick one, and pass it to assemble_animatic.py --music.")


if __name__ == "__main__":
    main()
