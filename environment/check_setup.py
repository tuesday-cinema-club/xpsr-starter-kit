#!/usr/bin/env python3
"""
Check which parts of the local studio are ready on this machine.

Read-only: it installs nothing and sends nothing anywhere. Every result is a
word (READY, MISSING, OPTIONAL) so the output reads well with a screen reader.

    python3 environment/check_setup.py
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request

MODEL = os.environ.get("TCC_MODEL", "llama3.2:3b")
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
if not OLLAMA.startswith("http"):
    OLLAMA = "http://" + OLLAMA
COMFY = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")

results = []


def row(name, status, detail, needed_for):
    results.append((name, status, detail, needed_for))


def http_json(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return None


def version_of(cmd, args=("--version",)):
    exe = shutil.which(cmd)
    if not exe:
        return None
    try:
        out = subprocess.run([exe, *args], capture_output=True, text=True, timeout=20)
        text = (out.stdout or out.stderr).strip().splitlines()
        return text[0].split(" Copyright")[0][:60] if text else "installed"
    except Exception:
        return "installed"


def main():
    py = sys.version_info
    row("Python 3.9+", "READY" if py >= (3, 9) else "MISSING", platform.python_version(), "every script")
    git = version_of("git")
    row("Git", "READY" if git else "MISSING", git or "https://git-scm.com/downloads", "copying the starter kit, saving gates")

    ollama = version_of("ollama", ("-v",))
    tags = http_json(f"{OLLAMA}/api/tags")
    row("Ollama app", "READY" if ollama else "MISSING", ollama or "https://ollama.com/download", "Writer crew")
    if tags is None:
        row("Ollama daemon", "MISSING", f"not answering at {OLLAMA}; open Ollama or run 'ollama serve'", "Writer crew")
    else:
        names = [m["name"] for m in tags.get("models", [])]
        has = any(n == MODEL or n.startswith(MODEL + ":") for n in names)
        row("Ollama daemon", "READY", f"{len(names)} model(s) on {OLLAMA}", "Writer crew")
        row(f"Model {MODEL}", "READY" if has else "MISSING", "pulled" if has else f"run: ollama pull {MODEL}", "Writer crew")

    blender = version_of("blender")
    if not blender and platform.system() == "Darwin" and os.path.exists("/Applications/Blender.app"):
        blender = "Blender.app"
    row("Blender", "READY" if blender else "MISSING", blender or "https://www.blender.org/download/", "Previs crew")
    ff = version_of("ffmpeg", ("-version",))
    row("ffmpeg", "READY" if ff else "MISSING", ff or "https://ffmpeg.org/download.html", "Edit crew, QC")
    whisper = shutil.which("whisper") or shutil.which("whisper-cli")
    row("Whisper", "READY" if whisper else "OPTIONAL", os.path.basename(whisper) if whisper else "pip install openai-whisper, or whisper.cpp", "captions")
    for app, url, crew in (("kdenlive", "https://kdenlive.org/download/", "Edit crew"),
                           ("gimp", "https://www.gimp.org/downloads/", "paint-over")):
        found = shutil.which(app) or (platform.system() == "Darwin" and any(
            os.path.exists(f"/Applications/{n}.app") for n in (app.capitalize(), app.upper(), "GIMP")))
        row(app.capitalize() if app != "gimp" else "GIMP", "READY" if found else "OPTIONAL",
            "installed" if found else url, crew)

    gpu = None
    if shutil.which("nvidia-smi"):
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True)
        gpu = out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else None
    elif platform.system() == "Darwin" and platform.machine() == "arm64":
        gpu = "Apple Silicon (unified memory)"
    row("GPU", "READY" if gpu else "OPTIONAL", gpu or "none found: join Writer, Previs, Edit or Auditor", "Frames crew")
    comfy = http_json(f"{COMFY}/system_stats")
    row("ComfyUI server", "READY" if comfy else "OPTIONAL",
        f"version {comfy['system'].get('comfyui_version', '?')}" if comfy else f"not running at {COMFY}", "Frames crew")

    free_gb = shutil.disk_usage(os.path.expanduser("~")).free / 1e9
    row("Free disk", "READY" if free_gb >= 10 else "MISSING", f"{free_gb:.0f} GB free (10 GB laptop, 40 GB GPU laptop)", "models")

    width = max(len(r[0]) for r in results)
    print("Tuesday Cinema Club starter kit: setup check\n")
    for name, status, detail, needed in results:
        print(f"{name:<{width}}  {status:<8}  {detail}  (for: {needed})")

    ready = {r[0] for r in results if r[1] == "READY"}
    print()
    if {"Ollama daemon", f"Model {MODEL}"} <= ready and "ComfyUI server" in ready:
        print("Suggested crew: Frames (GPU laptop). You can also run every other stage.")
    elif {"Ollama daemon", f"Model {MODEL}"} <= ready:
        print("Suggested crew: Writer, Previs or Edit & Sound (laptop).")
    else:
        print("Suggested crew: Director or Auditor (phone is fine), or pair up with a laptop.")
    missing = [r[0] for r in results if r[1] == "MISSING"]
    if missing:
        print("To fix before the workshop: " + ", ".join(missing))
        return 1
    print("Everything required is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
