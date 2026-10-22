#!/usr/bin/env python3
"""
Write an OpenTimelineIO rough cut (timeline.otio) for Kdenlive.

Lays the approved keyframes on a video track at the durations in shots.json,
puts the voiceover on an audio track, and adds one marker per caption cue so
the editor can see where lines land. Open the result in Kdenlive with
File > Open (Kdenlive 23.04 or newer reads .otio files).

Standard library only: the file is written as plain OTIO JSON. If the
`opentimelineio` package is installed, the result is also loaded back with it
as a check.

Example:
    python3 pipelines/03-post-production/generate_timeline.py \\
        --shots my-project/shots.json --frames my-project/frames \\
        --audio my-project/audio/vo.wav --captions my-project/captions.srt \\
        --fps 24 --out my-project/timeline.otio
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import load_json, say, write_json  # noqa: E402


def rt(value: float, rate: float) -> dict:
    return {"OTIO_SCHEMA": "RationalTime.1", "rate": rate, "value": float(value)}


def trange(start: float, duration: float, rate: float) -> dict:
    return {"OTIO_SCHEMA": "TimeRange.1", "start_time": rt(start, rate), "duration": rt(duration, rate)}


def media_ref(path: str, duration_frames: float, rate: float, base_dir: str) -> dict:
    return {
        "OTIO_SCHEMA": "ExternalReference.1",
        "name": os.path.basename(path),
        "target_url": os.path.relpath(path, base_dir),
        "available_range": trange(0, duration_frames, rate),
        "available_image_bounds": None,
        "metadata": {},
    }


def clip(name: str, ref: dict, duration_frames: float, rate: float, metadata=None, markers=None) -> dict:
    return {
        "OTIO_SCHEMA": "Clip.1",
        "name": name,
        "source_range": trange(0, duration_frames, rate),
        "media_reference": ref,
        "effects": [],
        "markers": markers or [],
        "enabled": True,
        "metadata": metadata or {},
    }


def track(name: str, kind: str, children: list) -> dict:
    return {"OTIO_SCHEMA": "Track.1", "name": name, "kind": kind, "children": children,
            "source_range": None, "effects": [], "markers": [], "enabled": True, "metadata": {}}


def parse_srt(path: str):
    def secs(ts):
        h, m, rest = ts.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    cues = []
    with open(path, encoding="utf-8") as f:
        for block in f.read().strip().split("\n\n"):
            lines = block.strip().splitlines()
            if len(lines) >= 3:
                m = re.match(r"(\S+)\s+-->\s+(\S+)", lines[1])
                if m:
                    cues.append((secs(m.group(1)), secs(m.group(2)), " ".join(lines[2:])))
    return cues


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--shots", required=True)
    p.add_argument("--frames", required=True, help="Folder with shot_NN_keyframe.png")
    p.add_argument("--audio", help="Voiceover audio for the audio track")
    p.add_argument("--captions", help="captions.srt: one marker per cue")
    p.add_argument("--fps", type=float, default=24.0)
    p.add_argument("--name", default="Rough cut")
    p.add_argument("--out", default="timeline.otio")
    args = p.parse_args()

    rate = args.fps
    shots = load_json(args.shots)["shots"]
    base_dir = os.path.dirname(os.path.abspath(args.out))
    video, total = [], 0
    for s in shots:
        n = s["shot_number"]
        frames = round(s["duration_sec"] * rate)
        img = os.path.join(args.frames, f"shot_{n:02d}_keyframe.png")
        if not os.path.exists(img):
            sys.exit(f"Missing keyframe {img}")
        video.append(clip(f"Shot {n}: {s['framing']} {s['lens_mm']}mm", media_ref(img, frames, rate, base_dir),
                          frames, rate, metadata={"tcc": {"camera_move": s["camera_move"],
                                                          "action": s["action_description"],
                                                          "voiceover_line": s["voiceover_line"]}}))
        total += frames

    tracks = [track("V1 Keyframes", "Video", video)]
    if args.audio:
        markers = []
        if args.captions:
            for start, end, text in parse_srt(args.captions):
                markers.append({"OTIO_SCHEMA": "Marker.2", "name": text, "color": "GREEN", "comment": "caption",
                                "marked_range": trange(round(start * rate), round((end - start) * rate), rate),
                                "metadata": {}})
        tracks.append(track("A1 Voiceover", "Audio",
                            [clip("Voiceover", media_ref(args.audio, total, rate, base_dir), total, rate,
                                  markers=markers)]))

    timeline = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": args.name,
        "global_start_time": rt(0, rate),
        "tracks": {"OTIO_SCHEMA": "Stack.1", "name": "tracks", "children": tracks, "source_range": None,
                   "effects": [], "markers": [], "enabled": True, "metadata": {}},
        "metadata": {"generator": "tuesday-cinema-club/xpsr-starter-kit generate_timeline.py"},
    }
    write_json(args.out, timeline)
    say("ok", f"{args.out}: {len(video)} clips, {total / rate:.1f}s at {rate:g} fps")

    try:
        import opentimelineio as otio
    except ImportError:
        say("!", "opentimelineio not installed; skipped the read-back check")
    else:
        tl = otio.adapters.read_from_file(args.out)
        say("ok", f"Read back with OpenTimelineIO {otio.__version__}: duration {tl.duration().to_seconds():.1f}s, "
            f"{len(tl.video_tracks())} video / {len(tl.audio_tracks())} audio track(s)")
    say(">", "Open timeline.otio in Kdenlive (File > Open) to cut, grade and mix by hand.")


if __name__ == "__main__":
    main()
