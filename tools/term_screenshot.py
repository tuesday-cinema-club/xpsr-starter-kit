#!/usr/bin/env python3
"""
Turn captured terminal output into a PNG screenshot for the docs.

Used to make the images in docs/images/. The text in each image is the real
output of a command run on a real machine (saved with `tee`), not retyped.
Rendering goes through headless Chrome or Chromium, so no desktop session is
needed.

Usage:
    some-command 2>&1 | tee run.log
    python3 tools/term_screenshot.py --log run.log --command "some-command" \\
        --title "Pipeline 01" --out docs/images/run.png
"""

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\r")

COLORS = {
    "[pass]": "#7ee787", "[fail]": "#ff7b72", "[warn]": "#e3b341",
    "[working]": "#79c0ff", "[next]": "#d2a8ff", "READY": "#7ee787",
    "MISSING": "#ff7b72", "OPTIONAL": "#e3b341",
}


def colorize(line: str) -> str:
    out = html.escape(line)
    for token, color in COLORS.items():
        esc = html.escape(token)
        out = out.replace(esc, f'<span style="color:{color};font-weight:600">{esc}</span>')
    return out


def find_chrome():
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if os.path.exists(mac) else None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", required=True, help="Captured output")
    p.add_argument("--command", required=True, help="Command line shown at the prompt")
    p.add_argument("--title", default="Terminal")
    p.add_argument("--out", required=True)
    p.add_argument("--width", type=int, default=1200)
    p.add_argument("--prompt", default="~/starter-kit $")
    args = p.parse_args()

    with open(args.log, encoding="utf-8", errors="replace") as f:
        raw = ANSI.sub("", f.read())
    lines = [ln for ln in raw.splitlines() if "frames/s]" not in ln]
    cmd_lines = args.command.split("\n")
    body = "\n".join(
        [f'<span style="color:#7ee787">{html.escape(args.prompt)}</span> {html.escape(cmd_lines[0])}']
        + [html.escape(c) for c in cmd_lines[1:]]
        + [colorize(ln) for ln in lines]
    )
    n_lines = len(cmd_lines) + len(lines)
    longest = max([len(args.prompt) + len(cmd_lines[0])] + [len(x) for x in cmd_lines[1:] + lines])
    width = max(args.width, min(2000, int(longest * 8.6) + 80))
    height = 64 + n_lines * 21 + 40

    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#0d1117;}}
.win{{margin:0;border-radius:10px;overflow:hidden;background:#161b22;}}
.bar{{height:36px;background:#21262d;display:flex;align-items:center;padding:0 14px;gap:8px;
     font:13px -apple-system,Segoe UI,Ubuntu,sans-serif;color:#c9d1d9;}}
.dot{{width:12px;height:12px;border-radius:50%;}}
.t{{flex:1;text-align:center;margin-right:52px}}
pre{{margin:0;padding:16px 18px 22px;font:14.5px/21px "DejaVu Sans Mono",Menlo,Consolas,monospace;
     color:#e6edf3;white-space:pre;}}
</style></head><body><div class="win"><div class="bar">
<span class="dot" style="background:#ff5f56"></span><span class="dot" style="background:#ffbd2e"></span>
<span class="dot" style="background:#27c93f"></span><span class="t">{html.escape(args.title)}</span></div>
<pre>{body}</pre></div></body></html>"""

    chrome = find_chrome()
    if not chrome:
        sys.exit("Chrome or Chromium is needed to render screenshots.")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "term.html")
        with open(src, "w", encoding="utf-8") as f:
            f.write(page)
        out = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--user-data-dir={os.path.join(tmp, 'profile')}",
                        f"--window-size={width},{height}", f"--screenshot={out}", f"file://{src}"],
                       check=True, capture_output=True)
    print(f"[pass] {args.out} ({width}x{height})")


if __name__ == "__main__":
    main()
