#!/usr/bin/env python3
"""
Assemble an animatic cut from approved keyframes with ffmpeg.

This is the "No GPU? Cut the keyframes together as an animatic" path from the
participant guide, and the fastest way to screen something at Gate 04.

For each shot it turns the still into a clip of the right length, using the
shot's camera_move as a gentle digital move (Push In, Pull Out, Pan, Tilt;
Static stays still). Then it joins the clips, lays in the voiceover
normalized for social media loudness, and writes two deliverables:

  cut.mp4           H.264 + AAC with the captions burned in (open captions)
  cut_softsubs.mp4  same picture without burned captions, plus a selectable
                    subtitle track (closed captions) for players that support it

An optional --end-card adds typed lettering for the last seconds. Real text
belongs here, set by a person, not generated inside an image.

With --clips, shots that have an approved motion clip (shot_NN_motion.mp4
from comfyui_motion.py) use it instead of the still. The motion already holds
the camera move, so no digital move is added; a clip shorter than its shot
holds its last frame.

Example:
    python3 pipelines/03-post-production/assemble_animatic.py \\
        --shots my-project/shots.json --frames my-project/frames \\
        --audio my-project/audio/vo.wav --captions my-project/captions.srt \\
        --fps 24 --end-card "Ember & Oak / Second shop now open" --out my-project/cut.mp4
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import append_provenance, load_json, say  # noqa: E402

W, H = 1920, 1080


def move_expr(move: str, frames: int):
    """zoompan expressions (zoom, x, y) for a camera move over `frames` frames."""
    t = f"(on/{max(frames - 1, 1)})"
    centre_x, centre_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    return {
        "Push In": (f"1+0.10*{t}", centre_x, centre_y),
        "Pull Out": (f"1.10-0.10*{t}", centre_x, centre_y),
        "Pan Left": ("1.08", f"(iw-iw/zoom)*(1-{t})", centre_y),
        "Pan Right": ("1.08", f"(iw-iw/zoom)*{t}", centre_y),
        "Tilt Up": ("1.08", centre_x, f"(ih-ih/zoom)*(1-{t})"),
        "Tilt Down": ("1.08", centre_x, f"(ih-ih/zoom)*{t}"),
        "Handheld": ("1.04", f"{centre_x}+6*sin(on/7)", f"{centre_y}+4*sin(on/5)"),
    }.get(move, ("1", centre_x, centre_y))


def find_font():
    if shutil.which("fc-match"):
        out = subprocess.run(["fc-match", "-f", "%{file}", "DejaVu Sans:bold"], capture_output=True, text=True)
        if out.returncode == 0 and os.path.exists(out.stdout.strip()):
            return out.stdout.strip()
    for path in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if os.path.exists(path):
            return path
    return None


def ff(args):
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def esc_filter_path(path: str) -> str:
    return path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--shots", required=True)
    p.add_argument("--frames", required=True)
    p.add_argument("--clips", help="Folder with approved shot_NN_motion.mp4 clips (used instead of stills)")
    p.add_argument("--audio", help="Voiceover (or full mix) audio")
    p.add_argument("--captions", help="captions.srt to burn in and attach")
    p.add_argument("--fps", type=float, default=24.0)
    p.add_argument("--lufs", type=float, default=-14.0, help="Integrated loudness target (default -14 LUFS)")
    p.add_argument("--compress", action="store_true",
                   help="Gently compress the voice before normalizing; use when QC says the loudness is too low "
                        "because peaks hit the -1.5 dBTP ceiling")
    p.add_argument("--end-card", help="Text for the end card; use ' / ' for a line break")
    p.add_argument("--end-card-sec", type=float, default=3.0)
    p.add_argument("--out", default="cut.mp4")
    p.add_argument("--provenance", help="provenance.csv (default: next to --shots)")
    args = p.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is required: see environment/README.md")
    shots = load_json(args.shots)["shots"]
    prov = args.provenance or os.path.join(os.path.dirname(args.shots) or ".", "provenance.csv")
    total = sum(s["duration_sec"] for s in shots)
    font = find_font()

    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for s in shots:
            n = s["shot_number"]
            frames = round(s["duration_sec"] * args.fps)
            part = os.path.join(tmp, f"part_{n:02d}.mp4")
            clip = os.path.join(args.clips, f"shot_{n:02d}_motion.mp4") if args.clips else None
            if clip and os.path.exists(clip):
                vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
                      f"fps={args.fps},tpad=stop_mode=clone:stop_duration={s['duration_sec']},format=yuv420p")
                ff(["-i", clip, "-vf", vf, "-frames:v", str(frames), "-an",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "16", part])
                parts.append(part)
                say("ok", f"Shot {n}: {s['duration_sec']}s, motion clip {os.path.basename(clip)}")
                continue
            src = os.path.join(args.frames, f"shot_{n:02d}_keyframe.png")
            if not os.path.exists(src):
                sys.exit(f"Missing keyframe {src}")
            z, x, y = move_expr(s["camera_move"], frames)
            # Upscale before zoompan so slow moves do not judder.
            vf = (f"scale={W * 2}:-2,crop={W * 2}:{H * 2},"
                  f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={args.fps},"
                  f"format=yuv420p")
            ff(["-loop", "1", "-i", src, "-vf", vf, "-frames:v", str(frames), "-r", str(args.fps),
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", part])
            parts.append(part)
            say("ok", f"Shot {n}: {s['duration_sec']}s, {s['camera_move']}")

        concat_list = os.path.join(tmp, "list.txt")
        with open(concat_list, "w") as f:
            f.writelines(f"file '{p_}'\n" for p_ in parts)
        picture = os.path.join(tmp, "picture.mp4")
        ff(["-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", picture])

        if args.end_card and font:
            lines = [ln.strip() for ln in args.end_card.split(" / ")]
            start = total - args.end_card_sec
            draws = []
            for i, line in enumerate(lines):
                text = line.replace("\\", "\\\\").replace("'", "\u2019").replace(":", "\\:").replace("%", "\\%")
                size = 84 if i == 0 else 52
                yoff = f"(h/2)-{(len(lines) - 1) * 45}+{i * 100}"
                draws.append(f"drawtext=fontfile='{esc_filter_path(font)}':text='{text}':fontsize={size}:"
                             f"fontcolor=white:x=(w-text_w)/2:y={yoff}:enable='gte(t,{start})'")
            carded = os.path.join(tmp, "carded.mp4")
            ff(["-i", picture, "-vf",
                f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.62:t=fill:enable='gte(t,{start})'," + ",".join(draws),
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", carded])
            picture = carded
            say("ok", f"End card: {' | '.join(lines)}")

        audio_args, audio_map = [], []
        if args.audio:
            audio_args = ["-i", args.audio]
            comp = "acompressor=threshold=-24dB:ratio=3:attack=5:release=120:makeup=4dB," if args.compress else ""
            audio_map = ["-map", "1:a", "-af", f"{comp}loudnorm=I={args.lufs}:TP=-1.5:LRA=11,aresample=48000",
                         "-c:a", "aac", "-b:a", "192k"]

        soft = os.path.splitext(args.out)[0] + "_softsubs.mp4"
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        if args.captions:
            style = ("FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                     "BackColour=&H33000000,BorderStyle=4,Outline=1,Shadow=0,MarginV=36")
            ff(["-i", picture, *audio_args, "-map", "0:v",
                "-vf", f"subtitles='{esc_filter_path(os.path.abspath(args.captions))}':force_style='{style}'",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                *audio_map, "-t", str(total), "-movflags", "+faststart", args.out])
            ff(["-i", picture, *audio_args, "-i", args.captions, "-map", "0:v",
                *(audio_map[:2] if audio_map else []), "-map", f"{2 if args.audio else 1}:s",
                "-c:v", "copy", *(audio_map[2:] if audio_map else []), "-c:s", "mov_text",
                "-metadata:s:s:0", "language=eng", "-t", str(total), "-movflags", "+faststart", soft])
            say("ok", f"{args.out} (open captions) and {soft} (closed captions)")
        else:
            ff(["-i", picture, *audio_args, "-map", "0:v", "-c:v", "copy", *audio_map,
                "-t", str(total), "-movflags", "+faststart", args.out])
            say("ok", f"{args.out} written")

    append_provenance(prov, asset_id=os.path.basename(args.out), stage="edit",
                      tool_or_model="ffmpeg animatic (assemble_animatic.py)",
                      prompt_or_input=("approved motion clips + " if args.clips else "approved keyframes + ") + (os.path.basename(args.audio) if args.audio else "no audio")
                      + (" + " + os.path.basename(args.captions) if args.captions else ""))
    say(">", "Gate 04: screen the cut, then run qc_check.py and pre_audit.py.")


if __name__ == "__main__":
    main()
