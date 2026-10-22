#!/usr/bin/env python3
"""
Transcribe a voiceover locally with Whisper and write captions.srt.

Works with either engine, whichever is installed:
  - openai-whisper   (`pip install openai-whisper`, provides the `whisper` command)
  - whisper.cpp      (`whisper-cli`, faster on CPU-only laptops; pass --model-path)

No audio leaves your machine.

Examples:
    python3 pipelines/03-post-production/transcribe.py --audio my-project/audio/vo.wav \\
        --out my-project/captions.srt
    python3 pipelines/03-post-production/transcribe.py --audio vo.wav --out captions.srt \\
        --engine whisper.cpp --model-path ~/models/ggml-base.en.bin
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import append_provenance, say  # noqa: E402


def run_openai_whisper(audio, model, language, out_srt, max_width=42, max_lines=2):
    exe = shutil.which("whisper")
    cmd = [exe] if exe else [sys.executable, "-m", "whisper"]
    with tempfile.TemporaryDirectory() as tmp:
        # Word timestamps let Whisper break captions into readable lines
        # (about 42 characters, at most 2 lines per caption).
        subprocess.run(cmd + [audio, "--model", model, "--language", language, "--output_format", "srt",
                              "--output_dir", tmp, "--fp16", "False", "--verbose", "False",
                              "--word_timestamps", "True", "--max_line_width", str(max_width),
                              "--max_line_count", str(max_lines)], check=True)
        produced = os.path.join(tmp, os.path.splitext(os.path.basename(audio))[0] + ".srt")
        shutil.copyfile(produced, out_srt)
    return f"openai-whisper/{model}"


def run_whisper_cpp(audio, model_path, language, out_srt):
    exe = shutil.which("whisper-cli") or shutil.which("whisper-cpp") or shutil.which("main")
    if not exe:
        sys.exit("whisper.cpp not found on PATH (looked for whisper-cli, whisper-cpp).")
    if not model_path or not os.path.exists(model_path):
        sys.exit("whisper.cpp needs --model-path pointing at a ggml model, e.g. ggml-base.en.bin")
    with tempfile.TemporaryDirectory() as tmp:
        wav16 = os.path.join(tmp, "in16k.wav")
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", audio, "-ar", "16000", "-ac", "1", wav16], check=True)
        base = os.path.join(tmp, "out")
        subprocess.run([exe, "-m", model_path, "-l", language, "-f", wav16, "-osrt", "-of", base], check=True)
        shutil.copyfile(base + ".srt", out_srt)
    return f"whisper.cpp/{os.path.basename(model_path)}"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--audio", required=True, help="Voiceover audio file")
    p.add_argument("--out", required=True, help="Output .srt path")
    p.add_argument("--engine", choices=["auto", "openai-whisper", "whisper.cpp"], default="auto")
    p.add_argument("--model", default="base.en", help="openai-whisper model name (default base.en)")
    p.add_argument("--model-path", help="whisper.cpp ggml model file")
    p.add_argument("--language", default="en")
    p.add_argument("--max-line-width", type=int, default=42, help="Characters per caption line (default 42)")
    p.add_argument("--max-line-count", type=int, default=2, help="Lines per caption (default 2)")
    p.add_argument("--provenance", help="provenance.csv to append to")
    args = p.parse_args()

    engine = args.engine
    if engine == "auto":
        engine = "whisper.cpp" if args.model_path else "openai-whisper"
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    say("*", f"Transcribing {args.audio} with {engine} (offline) ...")
    if engine == "openai-whisper":
        tool = run_openai_whisper(args.audio, args.model, args.language, args.out,
                                  args.max_line_width, args.max_line_count)
    else:
        tool = run_whisper_cpp(args.audio, args.model_path, args.language, args.out)

    with open(args.out, encoding="utf-8") as f:
        cues = [b for b in f.read().strip().split("\n\n") if b.strip()]
    say("ok", f"{args.out}: {len(cues)} caption cue(s)")
    for cue in cues:
        lines = cue.splitlines()
        if len(lines) >= 3:
            print(f"      {lines[1]}  {' / '.join(lines[2:])}")
    if args.provenance:
        append_provenance(args.provenance, asset_id=os.path.basename(args.out), stage="captions",
                          tool_or_model=tool, prompt_or_input=os.path.basename(args.audio))
    say(">", "A human reads every caption against the audio before release.")


if __name__ == "__main__":
    main()
