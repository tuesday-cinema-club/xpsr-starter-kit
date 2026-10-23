#!/usr/bin/env python3
"""
Build a timed SCRATCH voiceover from the shot list, offline.

In the workshop the Edit & Sound crew records the real voiceover on a phone.
This script makes a placeholder track with Piper (local text-to-speech) so the
edit can be timed before the human take exists. Every line starts a moment
after its shot begins. The provenance row marks the track as a stand-in.

Needs the optional piper-tts package (installed by environment/setup-mac-linux.sh
into .venv) and a voice model, for example en_US-ljspeech-high (trained on the
public-domain LJ Speech dataset):

    .venv/bin/python -m piper.download_voices --download-dir ~/.local/share/piper-voices en_US-ljspeech-high

Example (run with the venv's Python so Piper is importable):
    .venv/bin/python pipelines/03-post-production/scratch_vo.py \\
        --shots my-project/shots.json \\
        --voice ~/.local/share/piper-voices/en_US-ljspeech-high.onnx \\
        --out my-project/audio/vo_scratch.wav

For a more natural scratch voice, pass --voice kokoro:<voice> to use Kokoro-82M
(Apache 2.0) instead, after `pip install kokoro soundfile` (pulls in PyTorch):

    python3 pipelines/03-post-production/scratch_vo.py --shots my-project/shots.json \
        --voice kokoro:am_michael --out my-project/audio/vo_scratch.wav

To use a recorded human take instead, skip this script and pass your file
to transcribe.py and assemble_animatic.py.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import append_provenance, load_json, say  # noqa: E402

LEAD_IN = 0.4   # seconds of picture before each line starts


_KOKORO = {}


def synth_kokoro(text: str, voice: str, dest: str, speed: float = 1.0) -> None:
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
    except ImportError:
        sys.exit(f"Kokoro is not installed in this Python:\n  {sys.executable} -m pip install kokoro soundfile")
    if "pipe" not in _KOKORO:
        _KOKORO["pipe"] = KPipeline(lang_code=voice[0], repo_id="hexgrad/Kokoro-82M")
    audio = np.concatenate([chunk for _, _, chunk in _KOKORO["pipe"](text, voice=voice, speed=speed)])
    sf.write(dest, audio, 24000)


def synth(text: str, voice: str, dest: str, speed: float = 1.0) -> None:
    if voice.startswith("kokoro:"):
        return synth_kokoro(text, voice.split(":", 1)[1], dest, speed)
    proc = subprocess.run([sys.executable, "-m", "piper", "-m", voice, "-f", dest,
                           "--length-scale", str(1.0 / speed)],
                          input=text.encode("utf-8"), capture_output=True)
    if proc.returncode != 0 or not os.path.exists(dest):
        sys.exit("Piper failed. Is piper-tts installed in this Python?\n"
                 f"  {sys.executable} -m pip install piper-tts\n{proc.stderr.decode()[-600:]}")


def duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--shots", required=True)
    p.add_argument("--voice", required=True, help="Piper .onnx voice model, or kokoro:<voice> such as kokoro:am_michael")
    p.add_argument("--out", required=True, help="Output .wav")
    p.add_argument("--speed", type=float, default=1.0, help="Speaking rate, e.g. 1.1 for 10%% faster (default 1.0)")
    p.add_argument("--provenance", help="provenance.csv (default: next to --shots)")
    args = p.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is required: see environment/README.md")
    shots = load_json(args.shots)["shots"]
    total = sum(s["duration_sec"] for s in shots)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    prov = args.provenance or os.path.join(os.path.dirname(args.shots) or ".", "provenance.csv")

    inputs, filters, script_lines, t = [], [], [], 0.0
    with tempfile.TemporaryDirectory() as tmp:
        for s in shots:
            line = s["voiceover_line"].strip()
            if line:
                wav = os.path.join(tmp, f"line_{s['shot_number']:02d}.wav")
                synth(line, args.voice, wav, args.speed)
                length = duration(wav)
                start = t + LEAD_IN
                if start + length > t + s["duration_sec"]:
                    say("!", f"Shot {s['shot_number']}: line runs {length:.1f}s, longer than the shot allows")
                idx = len(inputs) // 2
                inputs += ["-i", wav]
                ms = int(start * 1000)
                filters.append(f"[{idx}:a]aresample=48000,adelay={ms}|{ms}[a{idx}]")
                script_lines.append(f"{start:6.2f}s  shot {s['shot_number']}: {line}")
                say("ok", f"Shot {s['shot_number']}: '{line}' at {start:.2f}s ({length:.1f}s)")
            t += s["duration_sec"]
        if not inputs:
            sys.exit("No voiceover lines in shots.json")
        n = len(inputs) // 2
        mix = "".join(f"[a{i}]" for i in range(n))
        graph = ";".join(filters) + f";{mix}amix=inputs={n}:normalize=0,apad,atrim=0:{total},pan=mono|c0=c0[out]"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", *inputs, "-filter_complex", graph,
                        "-map", "[out]", "-ar", "48000", args.out], check=True)

    script_path = os.path.splitext(args.out)[0] + "_script.txt"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("SCRATCH VOICEOVER (synthetic stand-in: replace with a recorded human take)\n\n")
        f.write("\n".join(script_lines) + "\n")
    if args.voice.startswith("kokoro:"):
        engine = f"kokoro-82m/{args.voice.split(':', 1)[1]}"
    else:
        engine = f"piper-tts/{os.path.splitext(os.path.basename(args.voice))[0]}"
    append_provenance(prov, asset_id=os.path.basename(args.out), stage="dialogue",
                      tool_or_model=f"{engine} (SCRATCH stand-in for human VO)",
                      prompt_or_input=" / ".join(s["voiceover_line"] for s in shots if s["voiceover_line"]))
    say("ok", f"{args.out} written ({total:.1f}s), script in {script_path}")
    say(">", "Replace with the recorded human take before release (anti-slop check 7).")


if __name__ == "__main__":
    main()
