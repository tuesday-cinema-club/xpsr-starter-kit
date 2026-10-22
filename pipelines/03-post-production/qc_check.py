#!/usr/bin/env python3
"""
Technical QC for a finished cut (anti-slop check 5). Script the chores.

Measures with ffprobe and ffmpeg's EBU R128 meter, then compares against the
bible and the brief:

  - resolution and aspect ratio   (bible visual_rules.aspect_ratio)
  - frame rate                    (bible visual_rules.fps)
  - runtime                       (brief runtime_sec, with 0.5 s tolerance)
  - integrated loudness           (target -14 LUFS +/- 1.5 by default)
  - true peak                     (at or below -1.0 dBTP)
  - an audio stream exists

Writes qc.json next to the cut and exits 1 if any check fails.

Example:
    python3 pipelines/03-post-production/qc_check.py --video my-project/cut.mp4 \\
        --bible templates/ember-and-oak-bible.json --brief my-project/brief.json
"""

import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import load_json, say, write_json  # noqa: E402

ASPECTS = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1.0, "4:5": 0.8, "2.39:1": 2.39}


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def loudness(path):
    proc = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0",
                           "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    summary = proc.stderr[proc.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    return (float(i.group(1)) if i else None,
            float(tp.group(1)) if tp and tp.group(1) != "-inf" else None)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--video", required=True)
    p.add_argument("--bible", required=True)
    p.add_argument("--brief", help="brief.json for the runtime target")
    p.add_argument("--lufs", type=float, default=-14.0)
    p.add_argument("--lufs-tolerance", type=float, default=1.5)
    p.add_argument("--max-true-peak", type=float, default=-1.0)
    p.add_argument("--out", help="qc.json path (default: next to the video)")
    args = p.parse_args()

    info = probe(args.video)
    rules = load_json(args.bible)["visual_rules"]
    runtime_target = load_json(args.brief)["runtime_sec"] if args.brief else None
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if not v:
        sys.exit("No video stream found")
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    fps = num / den
    duration = float(info["format"]["duration"])
    w, h = int(v["width"]), int(v["height"])
    results = []

    def check(name, ok, measured, expected):
        results.append({"check": name, "result": "pass" if ok else "fail", "measured": measured, "expected": expected})
        say("ok" if ok else "x", f"{name}: {measured} (expected {expected})")

    want_ar = ASPECTS.get(rules["aspect_ratio"])
    check("Aspect ratio", want_ar is not None and abs(w / h - want_ar) < 0.01, f"{w}x{h}", rules["aspect_ratio"])
    check("Frame rate", abs(fps - float(rules["fps"])) < 0.01, f"{fps:g} fps", f"{rules['fps']} fps")
    if runtime_target:
        check("Runtime", duration <= runtime_target + 0.5, f"{duration:.2f}s", f"<= {runtime_target}s")
    check("Audio stream", a is not None, a["codec_name"] if a else "none", "present")
    if a:
        lufs, peak = loudness(args.video)
        check("Integrated loudness", lufs is not None and abs(lufs - args.lufs) <= args.lufs_tolerance,
              f"{lufs} LUFS", f"{args.lufs} +/- {args.lufs_tolerance} LUFS")
        check("True peak", peak is not None and peak <= args.max_true_peak, f"{peak} dBTP",
              f"<= {args.max_true_peak} dBTP")

    passed = all(r["result"] == "pass" for r in results)
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.video)), "qc.json")
    write_json(out, {"video": os.path.basename(args.video), "passed": passed, "checks": results})
    say("ok" if passed else "x", f"Technical QC {'PASSED' if passed else 'FAILED'}; report in {out}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
