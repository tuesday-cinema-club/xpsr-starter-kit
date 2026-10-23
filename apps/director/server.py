#!/usr/bin/env python3
"""
XPSR Director: the workshop's phone companion, served from this machine.

Serves the web app in web/ and a small JSON API behind one access code:

  /api/local/...   Ollama (writing help) and ComfyUI (first and last frames) on
                   this machine's GPU. Nothing leaves the machine.
  /api/flow/...    Google Flow through useapi.net (motion from a first frame,
                   an optional last frame and an action prompt). Off until a
                   useapi.net token is set. A daily credit budget stops jobs
                   before they spend more than the free allowance.
  /api/resources   Live CPU, memory, GPU, Ollama and ComfyUI readings for the
                   resources page.

Secrets live outside the repo, in ~/.config/xpsr-director/env (mode 600):

  XPSR_ACCESS_CODE=...     made on first start if missing
  USEAPI_TOKEN=...         useapi.net API token (optional)
  FLOW_PLAN=free           free, plus, pro, ultra
  FLOW_DAILY_CREDITS=50    hard cap on Flow credits per local day

Standard library only:

    python3 apps/director/server.py            # http://127.0.0.1:8790
    python3 apps/director/server.py --port 9000
"""

import argparse
import base64
import copy
import datetime
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(os.path.dirname(HERE))
WEB = os.path.join(HERE, "web")
WORKFLOWS = os.path.join(KIT, "pipelines", "02-production", "workflows")
ENV_FILE = os.path.expanduser(os.environ.get("XPSR_ENV", "~/.config/xpsr-director/env"))
DATA = os.path.expanduser(os.environ.get("XPSR_DATA", "~/.local/share/xpsr-director"))
MEDIA = os.path.join(DATA, "media")
USEAPI = os.environ.get("USEAPI_BASE", "https://api.useapi.net/v1/google-flow")
USEAPI_SETUP = "https://useapi.net/docs/start-here/setup-google-flow"

MAX_JSON = 1 << 20
MAX_UPLOAD = 20 << 20
SESSION_SALT = b"xpsr-director-session-v1"

# Flow credit cost per generation, from useapi.net's price table (October 2026).
# Veo on plans below Ultra makes 8-second clips only. Omni needs a paid plan.
FLOW_MODELS = {
    "veo-3.1-lite": {"label": "Veo 3.1 Lite", "cost": {"ultra": 5, "*": 10}, "plans": "all"},
    "veo-3.1-fast": {"label": "Veo 3.1 Fast", "cost": {"ultra": 10, "*": 20}, "plans": "all"},
    "veo-3.1-quality": {"label": "Veo 3.1 Quality", "cost": {"*": 100}, "plans": "all"},
    "omni-flash": {"label": "Omni 1.1 Flash 720p", "api": "omni-flash", "resolution": "720p",
                   "cost": {"*": {4: 7, 6: 10, 8: 12, 10: 15}}, "plans": "paid"},
    "omni-flash-360p": {"label": "Omni 1.1 Flash 360p", "api": "omni-flash", "resolution": "360p",
                        "cost": {"*": {4: 4, 6: 5, 8: 6, 10: 7}}, "plans": "paid"},
}
FLOW_IMAGE_MODELS = ["nano-banana-2-lite", "nano-banana-2", "nano-banana-pro"]


# ---------------------------------------------------------------- config

_env_cache = {"mtime": None, "values": {}}
_env_lock = threading.Lock()


def read_env() -> dict:
    try:
        mtime = os.path.getmtime(ENV_FILE)
    except OSError:
        return {}
    if mtime != _env_cache["mtime"]:
        values = {}
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip().strip('"').strip("'")
        _env_cache.update(mtime=mtime, values=values)
    return _env_cache["values"]


def conf(key: str, default: str = "") -> str:
    return os.environ.get(key) or read_env().get(key) or default


def write_env(key: str, value: str) -> None:
    """Set or remove one key in the env file, keeping the rest and mode 600."""
    with _env_lock:
        os.makedirs(os.path.dirname(ENV_FILE), exist_ok=True)
        lines = []
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, encoding="utf-8") as f:
                lines = [ln for ln in f.read().splitlines() if not ln.startswith(f"{key}=")]
        if value:
            lines.append(f"{key}={value}")
        fd = os.open(ENV_FILE + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(ENV_FILE + ".tmp", ENV_FILE)
        _env_cache["mtime"] = None


def ensure_access_code() -> None:
    if not conf("XPSR_ACCESS_CODE"):
        words = ["slate", "dolly", "gaffer", "grip", "boom", "reel", "frame", "lens", "cut", "take",
                 "focus", "iris", "matte", "foley", "dailies", "rushes", "splice", "mark"]
        code = "-".join(secrets.choice(words) for _ in range(3)) + "-" + str(secrets.randbelow(900) + 100)
        write_env("XPSR_ACCESS_CODE", code)
        print(f"Made an access code in {ENV_FILE}", flush=True)


def session_token() -> str:
    return hmac.new(conf("XPSR_ACCESS_CODE").encode(), SESSION_SALT, hashlib.sha256).hexdigest()


def ollama_url() -> str:
    return conf("OLLAMA_URL", "http://127.0.0.1:11434")


def comfy_url() -> str:
    return conf("COMFYUI_URL", "http://127.0.0.1:8188")


# ---------------------------------------------------------------- http helpers

def http_json(url: str, payload=None, headers=None, timeout=30, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return json.loads(body) if body else {}


def http_bytes(url: str, headers=None, timeout=120, data=None, content_type=None) -> bytes:
    h = dict(headers or {})
    if content_type:
        h["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.5):
            return True
    except Exception:
        return False


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------- store

class Store:
    """Jobs, media and the Flow credit ledger, kept as JSON in DATA."""

    def __init__(self):
        os.makedirs(MEDIA, exist_ok=True)
        self.path = os.path.join(DATA, "store.json")
        self.lock = threading.RLock()
        self.data = {"jobs": {}, "media": {}, "ledger": {}, "flow_balance": None}
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self.data.update(json.load(f))
        for job in self.data["jobs"].values():
            if job["status"] in ("queued", "running"):
                job.update(status="failed", error="The server restarted while this job was running.")

    def save(self):
        with self.lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1)
            os.replace(tmp, self.path)

    def new_job(self, kind: str, params: dict) -> dict:
        job = {"id": uuid.uuid4().hex[:12], "kind": kind, "params": params, "status": "queued",
               "created": now_iso(), "started": None, "finished": None, "media": [], "error": None,
               "note": None}
        with self.lock:
            self.data["jobs"][job["id"]] = job
            self.save()
        return job

    def update_job(self, job_id: str, **fields):
        with self.lock:
            self.data["jobs"][job_id].update(fields)
            self.save()

    def add_media(self, data: bytes, ext: str, **meta) -> dict:
        name = f"{uuid.uuid4().hex[:16]}.{ext}"
        with open(os.path.join(MEDIA, name), "wb") as f:
            f.write(data)
        item = {"name": name, "created": now_iso(), "bytes": len(data), **meta}
        with self.lock:
            self.data["media"][name] = item
            self.save()
        return item

    def media(self, name: str):
        return self.data["media"].get(name)

    def set_media(self, name: str, **fields):
        with self.lock:
            self.data["media"][name].update(fields)
            self.save()

    def spent_today(self) -> int:
        return sum(e["credits"] for e in self.data["ledger"].get(today(), []) if not e.get("refunded"))

    def charge(self, job_id: str, model: str, credits: int) -> None:
        with self.lock:
            self.data["ledger"].setdefault(today(), []).append(
                {"job": job_id, "model": model, "credits": credits, "time": now_iso()})
            self.save()

    def refund(self, job_id: str) -> None:
        with self.lock:
            for entries in self.data["ledger"].values():
                for e in entries:
                    if e["job"] == job_id:
                        e["refunded"] = True
            self.save()


STORE = None
GPU_LOCK = threading.Lock()   # one local GPU job at a time
FLOW_LOCK = threading.Lock()  # budget checks and charges happen one at a time
UPLOAD_LOCK = threading.Lock()  # two jobs sharing a frame upload it once


# ---------------------------------------------------------------- local GPU: Ollama and ComfyUI

def ollama_models() -> list:
    try:
        return [m["name"] for m in http_json(f"{ollama_url()}/api/tags", timeout=3)["models"]]
    except Exception:
        return []


def free_comfy_vram():
    try:
        http_json(f"{comfy_url()}/free", {"unload_models": True, "free_memory": True}, timeout=10)
    except Exception:
        pass


def free_ollama_vram():
    try:
        for m in http_json(f"{ollama_url()}/api/ps", timeout=3).get("models", []):
            http_json(f"{ollama_url()}/api/generate", {"model": m["name"], "keep_alive": 0}, timeout=30)
    except Exception:
        pass


def local_chat(body: dict) -> dict:
    model = body.get("model") or conf("OLLAMA_MODEL", "llama3.2:3b")
    if model not in ollama_models():
        raise ApiError(400, f"Ollama has no model called {model}. Pull it with: ollama pull {model}")
    payload = {
        "model": model, "stream": False, "keep_alive": "5m",
        "messages": [{"role": "system", "content": str(body.get("system", ""))[:8000]},
                     {"role": "user", "content": str(body.get("prompt", ""))[:24000]}],
        "options": {"temperature": float(body.get("temperature", 0.4)), "seed": int(body.get("seed", 42))},
    }
    if body.get("schema"):
        payload["format"] = body["schema"]
    with GPU_LOCK:
        free_comfy_vram()
        start = time.time()
        out = http_json(f"{ollama_url()}/api/chat", payload, timeout=900)
    text = out.get("message", {}).get("content", "")
    result = {"model": model, "text": text, "seconds": round(time.time() - start, 1), "seed": payload["options"]["seed"]}
    if body.get("schema"):
        try:
            result["json"] = json.loads(text)
        except ValueError:
            raise ApiError(502, f"{model} did not return valid JSON. Try again or pick a bigger model.")
    return result


FIRST_FRAME_REF = ("The reference image is a rough phone photo that blocks out this shot. Generate a finished "
                   "photograph that keeps its camera angle, layout and the positions of people and objects, "
                   "but none of its phone-camera look. Scene: {prompt}")
LAST_FRAME_REF = ("The reference image is the first frame of this shot. Generate the last frame of the same "
                  "shot: the same place, people, wardrobe, light and lens, a moment later. Only this changes: "
                  "{prompt}")


def comfy_upload(path: str) -> str:
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        data = f.read()
    name = os.path.basename(path)
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
            f"Content-Type: {mimetypes.guess_type(name)[0] or 'image/png'}\r\n\r\n").encode() + data + \
        f"\r\n--{boundary}--\r\n".encode()
    info = json.loads(http_bytes(f"{comfy_url()}/upload/image", data=body, timeout=60,
                                 content_type=f"multipart/form-data; boundary={boundary}"))
    return f"{info['subfolder']}/{info['name']}" if info.get("subfolder") else info["name"]


def run_keyframe(job: dict):
    """FLUX.2 [klein] 4B through ComfyUI: text only, or with a reference image
    (a phone photo for a first frame, the locked first frame for a last frame)."""
    p = job["params"]
    ref = p.get("reference")
    wf_file = "flux2_klein_previs_reference.json" if ref else "flux2_klein_txt2img.json"
    with open(os.path.join(WORKFLOWS, wf_file), encoding="utf-8") as f:
        wf = json.load(f)
    wf = copy.deepcopy(wf)
    template = (LAST_FRAME_REF if p.get("frame") == "last" else FIRST_FRAME_REF) if ref else "{prompt}"
    prompt = template.replace("{prompt}", p["prompt"])
    wf["74"]["inputs"]["text"] = prompt
    wf["73"]["inputs"]["noise_seed"] = int(p["seed"])
    w, h = int(p.get("width", 1344)), int(p.get("height", 768))
    wf["66"]["inputs"].update(width=w, height=h)
    wf["62"]["inputs"].update(width=w, height=h)
    wf["9"]["inputs"]["filename_prefix"] = "xpsr_director"
    with GPU_LOCK:
        STORE.update_job(job["id"], status="running", started=now_iso(), note="Freeing graphics memory")
        free_ollama_vram()
        if ref:
            wf["10"]["inputs"]["image"] = comfy_upload(os.path.join(MEDIA, ref))
        STORE.update_job(job["id"], note="Rendering on the local GPU")
        out = http_json(f"{comfy_url()}/prompt", {"prompt": wf, "client_id": "xpsr-director"}, timeout=60)
        prompt_id = out["prompt_id"]
        deadline = time.time() + 1800
        while time.time() < deadline:
            hist = http_json(f"{comfy_url()}/history/{prompt_id}", timeout=30).get(prompt_id)
            if hist:
                if hist.get("status", {}).get("status_str") == "error":
                    raise RuntimeError("ComfyUI reported an error: " +
                                       json.dumps(hist["status"].get("messages", []))[:600])
                if hist.get("outputs"):
                    break
            time.sleep(1)
        else:
            raise RuntimeError("Timed out after 30 minutes waiting for ComfyUI")
    images = [img for node in hist["outputs"].values() for img in node.get("images", [])]
    q = urllib.parse.urlencode({"filename": images[0]["filename"], "subfolder": images[0].get("subfolder", ""),
                                "type": images[0].get("type", "output")})
    data = http_bytes(f"{comfy_url()}/view?{q}")
    item = STORE.add_media(data, "png", kind="image", source="local", job=job["id"], frame=p.get("frame"),
                           label=p.get("label"), project=p.get("project"),
                           tool_or_model=f"ComfyUI/{wf['70']['inputs']['unet_name']}", seed=int(p["seed"]),
                           prompt=prompt, reference=ref)
    return [item["name"]]


# ---------------------------------------------------------------- Google Flow through useapi.net

def flow_token() -> str:
    return conf("USEAPI_TOKEN")


def flow_plan() -> str:
    plan = conf("FLOW_PLAN", "free").lower()
    return plan if plan in ("free", "plus", "pro", "ultra") else "free"


def flow_budget() -> int:
    try:
        return int(conf("FLOW_DAILY_CREDITS", "50"))
    except ValueError:
        return 50


def flow_cost(model: str, duration: int) -> int:
    spec = FLOW_MODELS[model]["cost"]
    cost = spec.get("ultra" if flow_plan() == "ultra" else "*", spec["*"])
    return cost[duration] if isinstance(cost, dict) else cost


def flow_call(path: str, payload=None, raw=None, content_type=None, timeout=60, method=None):
    token = flow_token()
    if not token:
        raise ApiError(400, "No useapi.net token yet. Add one on the Accounts panel.")
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{USEAPI}{path}"
    try:
        if raw is not None:
            return json.loads(http_bytes(url, headers=headers, data=raw, content_type=content_type, timeout=timeout))
        return http_json(url, payload, headers=headers, timeout=timeout, method=method)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        hints = {401: "useapi.net refused the token.",
                 402: "useapi.net says the subscription is not active.",
                 429: "No connected Google account can take a job right now (out of credits or rate limited). "
                      "Wait and try again.",
                 596: "The Google account needs to be connected again through useapi.net's setup page."}
        raise ApiError(exc.code if exc.code < 600 else 502, f"{hints.get(exc.code, 'useapi.net error')} {detail}")


def flow_account_email(body: dict) -> str:
    return str(body.get("email") or conf("FLOW_EMAIL") or "")


def flow_upload(media_name: str, email: str) -> str:
    """Upload a local frame to Flow once and remember its mediaGenerationId."""
    with UPLOAD_LOCK:
        return _flow_upload(media_name, email)


def _flow_upload(media_name: str, email: str) -> str:
    item = STORE.media(media_name)
    if not item:
        raise ApiError(404, f"No media called {media_name}")
    if item.get("flow_id"):
        return item["flow_id"]
    with open(os.path.join(MEDIA, media_name), "rb") as f:
        data = f.read()
    ctype = mimetypes.guess_type(media_name)[0] or "image/png"
    out = flow_call(f"/assets{'/' + urllib.parse.quote(email) if email else ''}", raw=data,
                    content_type=ctype, timeout=120)
    mid = out.get("mediaGenerationId")
    flow_id = mid.get("mediaGenerationId") if isinstance(mid, dict) else mid
    if not flow_id:
        raise RuntimeError(f"useapi.net did not return a mediaGenerationId: {json.dumps(out)[:300]}")
    STORE.set_media(media_name, flow_id=flow_id)
    return flow_id


def run_flow_image(job: dict):
    p = job["params"]
    STORE.update_job(job["id"], status="running", started=now_iso(), note="Waiting for Google Flow")
    payload = {"prompt": p["prompt"], "model": p["model"], "aspectRatio": p.get("aspect", "16:9"),
               "count": 1, "seed": int(p["seed"])}
    email = flow_account_email(p)
    if email:
        payload["email"] = email
    if p.get("reference"):
        payload["reference_1"] = flow_upload(p["reference"], email)
    out = flow_call("/images", payload, timeout=300)
    names = []
    for m in out.get("media", []):
        g = m.get("image", {}).get("generatedImage", {})
        if g.get("fifeUrl"):
            data = http_bytes(g["fifeUrl"], timeout=120)
        elif g.get("encodedImage"):
            data = base64.b64decode(g["encodedImage"])
        else:
            continue
        item = STORE.add_media(data, "jpg" if data[:2] == b"\xff\xd8" else "png", kind="image", source="flow",
                               job=job["id"], frame=p.get("frame"), label=p.get("label"), project=p.get("project"), tool_or_model=f"google-flow/{p['model']}",
                               seed=g.get("seed", p["seed"]), prompt=p["prompt"], reference=p.get("reference"),
                               flow_id=g.get("mediaGenerationId"))
        names.append(item["name"])
    if not names:
        raise RuntimeError(f"Flow returned no image: {json.dumps(out)[:300]}")
    return names


def run_flow_video(job: dict):
    p = job["params"]
    STORE.update_job(job["id"], status="running", started=now_iso(), note="Uploading frames to Flow")
    email = flow_account_email(p)
    spec = FLOW_MODELS[p["model"]]
    payload = {"prompt": p["prompt"], "model": spec.get("api", p["model"]), "aspectRatio": "landscape", "count": 1,
               "duration": int(p["duration"])}
    if spec.get("resolution"):
        payload["resolution"] = spec["resolution"]
    if p.get("seed") not in (None, ""):
        payload["seed"] = int(p["seed"])
    if email:
        payload["email"] = email
    payload["startImage"] = flow_upload(p["start"], email)
    if p.get("end"):
        payload["endImage"] = flow_upload(p["end"], email)
    STORE.update_job(job["id"], note="Google Flow is rendering (usually 1 to 3 minutes)")
    out = flow_call("/videos", payload, timeout=900)
    if isinstance(out.get("remainingCredits"), (int, float)):
        STORE.data["flow_balance"] = {"credits": out["remainingCredits"], "time": now_iso()}
    names = []
    for m in out.get("media", []):
        if not m.get("videoUrl"):
            continue
        data = http_bytes(m["videoUrl"], timeout=300)
        gen = m.get("video", {}).get("generatedVideo", {})
        item = STORE.add_media(data, "mp4", kind="video", source="flow", job=job["id"], frame="motion",
                               label=p.get("label"), project=p.get("project"), duration=p.get("duration"),
                               tool_or_model=f"google-flow/{p['model']}", seed=gen.get("seed", p.get("seed")),
                               prompt=p["prompt"], start=p["start"], end=p.get("end"),
                               flow_id=m.get("mediaGenerationId"), credits=job["params"]["credits"])
        names.append(item["name"])
    if not names:
        raise RuntimeError(f"Flow returned no video: {json.dumps(out)[:300]}")
    return names


def flow_status() -> dict:
    spent = STORE.spent_today()
    budget = flow_budget()
    plan = flow_plan()
    models = []
    for key, m in FLOW_MODELS.items():
        allowed = m["plans"] == "all" or plan != "free"
        durations = [4, 6, 8, 10] if key.startswith("omni") else ([4, 6, 8] if plan == "ultra" else [8])
        models.append({"id": key, "label": m["label"], "allowed": allowed, "durations": durations,
                       "costs": {d: flow_cost(key, d) for d in durations}})
    return {"configured": bool(flow_token()), "plan": plan, "daily_budget": budget, "spent_today": spent,
            "left_today": max(0, budget - spent), "balance": STORE.data.get("flow_balance"),
            "models": models, "image_models": FLOW_IMAGE_MODELS, "email": conf("FLOW_EMAIL"),
            "setup_url": USEAPI_SETUP}


# ---------------------------------------------------------------- library

def library() -> dict:
    """Every file the server has made or received, and which credits paid for which file."""
    media = sorted(STORE.data["media"].values(), key=lambda m: m["created"], reverse=True)
    jobs = STORE.data["jobs"]
    days = []
    for day, entries in sorted(STORE.data["ledger"].items(), reverse=True):
        rows = []
        for e in entries:
            j = jobs.get(e["job"], {})
            rows.append({**e, "status": j.get("status"), "media": j.get("media", []), "error": j.get("error"),
                         "prompt": j.get("params", {}).get("prompt"), "label": j.get("params", {}).get("label"),
                         "project": j.get("params", {}).get("project")})
        days.append({"day": day, "spent": sum(e["credits"] for e in entries if not e.get("refunded")), "entries": rows})
    return {"media": media, "days": days, "flow": flow_status(),
            "totals": {"credits": sum(d["spent"] for d in days),
                       "videos": sum(1 for m in media if m["kind"] == "video"),
                       "frames_local": sum(1 for m in media if m["kind"] == "image" and m["source"] == "local"),
                       "frames_flow": sum(1 for m in media if m["kind"] == "image" and m["source"] == "flow"),
                       "photos": sum(1 for m in media if m["source"] == "upload")}}


# ---------------------------------------------------------------- jobs

RUNNERS = {"keyframe": run_keyframe, "flow_image": run_flow_image}


def start_job(kind: str, params: dict) -> dict:
    job = STORE.new_job(kind, params)

    def work():
        try:
            names = RUNNERS[kind](job)
            STORE.update_job(job["id"], status="done", finished=now_iso(), media=names, note=None)
        except Exception as exc:  # report every failure to the phone
            msg = exc.message if isinstance(exc, ApiError) else str(exc)
            STORE.update_job(job["id"], status="failed", finished=now_iso(), error=msg[:900], note=None)

    threading.Thread(target=work, daemon=True).start()
    return job


# ---------------------------------------------------------------- resources

class Sampler:
    """Samples the machine every second while someone is watching."""

    def __init__(self):
        self.history = []
        self.latest = {}
        self.watched_until = 0
        self.prev_cpu = None
        self.lock = threading.Lock()
        threading.Thread(target=self.loop, daemon=True).start()

    def watch(self):
        self.watched_until = time.time() + 30

    def loop(self):
        while True:
            if time.time() < self.watched_until:
                try:
                    self.sample()
                except Exception as exc:
                    self.latest["error"] = str(exc)
                time.sleep(1)
            else:
                self.prev_cpu = None
                time.sleep(0.5)

    def cpu(self):
        with open("/proc/stat") as f:
            rows = [ln.split() for ln in f if ln.startswith("cpu")]
        now = {r[0]: [int(x) for x in r[1:9]] for r in rows}
        prev, self.prev_cpu = self.prev_cpu, now
        if not prev:
            return None, []

        def busy(a, b):
            idle = (b[3] + b[4]) - (a[3] + a[4])
            total = sum(b) - sum(a)
            return round(100 * (1 - idle / total), 1) if total else 0.0

        cores = [busy(prev[k], now[k]) for k in sorted((k for k in now if k != "cpu"), key=lambda k: int(k[3:]))]
        return busy(prev["cpu"], now["cpu"]), cores

    def sample(self):
        total, cores = self.cpu()
        if total is None:
            return
        mem = {}
        with open("/proc/meminfo") as f:
            for ln in f:
                k, v = ln.split(":")
                mem[k] = int(v.split()[0]) * 1024
        gpu = read_gpu()
        point = {"t": round(time.time(), 1), "cpu": total, "ram": mem["MemTotal"] - mem["MemAvailable"],
                 "gpu": gpu.get("util"), "vram": gpu.get("mem_used"), "temp": gpu.get("temp"),
                 "power": gpu.get("power")}
        with self.lock:
            self.history = (self.history + [point])[-180:]
            self.latest = {"cpu": {"total": total, "cores": cores, "temp": cpu_temp(),
                                   "load": open("/proc/loadavg").read().split()[:3],
                                   "model": cpu_model()},
                           "memory": {"total": mem["MemTotal"], "used": mem["MemTotal"] - mem["MemAvailable"],
                                      "cached": mem.get("Cached", 0), "swap_total": mem.get("SwapTotal", 0),
                                      "swap_used": mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)},
                           "gpu": gpu}

    def snapshot(self):
        self.watch()
        with self.lock:
            return dict(self.latest), list(self.history)


_cpu_model = None


def cpu_model():
    global _cpu_model
    if _cpu_model is None:
        _cpu_model = "CPU"
        with open("/proc/cpuinfo") as f:
            for ln in f:
                if ln.startswith("model name"):
                    _cpu_model = ln.split(":", 1)[1].strip()
                    break
    return _cpu_model


def cpu_temp():
    for hw in sorted(os.listdir("/sys/class/hwmon")) if os.path.isdir("/sys/class/hwmon") else []:
        base = f"/sys/class/hwmon/{hw}"
        try:
            if open(f"{base}/name").read().strip() in ("k10temp", "coretemp", "zenpower"):
                return round(int(open(f"{base}/temp1_input").read()) / 1000, 1)
        except OSError:
            continue
    return None


def read_gpu() -> dict:
    if not shutil.which("nvidia-smi"):
        return {}
    fields = ["name", "utilization.gpu", "memory.used", "memory.total", "temperature.gpu", "power.draw",
              "power.limit", "clocks.sm", "clocks.max.sm", "fan.speed", "pcie.link.gen.max",
              "pcie.link.width.max", "pcie.link.gen.current", "pcie.link.width.current"]
    try:
        row = subprocess.run(["nvidia-smi", f"--query-gpu={','.join(fields)}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout.strip().splitlines()[0]
        apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
    except (OSError, IndexError, subprocess.SubprocessError):
        return {}
    v = [x.strip() for x in row.split(",")]

    def num(x):
        try:
            return float(x)
        except ValueError:
            return None

    procs = []
    for ln in apps:
        parts = [x.strip() for x in ln.split(",")]
        if len(parts) == 2 and parts[0].isdigit():
            try:
                cmd = open(f"/proc/{parts[0]}/cmdline").read().replace("\0", " ").strip()
            except OSError:
                cmd = "?"
            label = "Ollama" if "ollama" in cmd else "ComfyUI" if "main.py" in cmd or "ComfyUI" in cmd else \
                os.path.basename(cmd.split(" ")[0]) or "process"
            procs.append({"pid": int(parts[0]), "name": label, "mem": num(parts[1])})
    return {"name": v[0], "util": num(v[1]), "mem_used": num(v[2]), "mem_total": num(v[3]), "temp": num(v[4]),
            "power": num(v[5]), "power_limit": num(v[6]), "clock": num(v[7]), "clock_max": num(v[8]),
            "fan": num(v[9]), "pcie": f"PCIe {v[10]}.0 x{v[11]}" + ("" if v[10:12] == v[12:14] else f" (now {v[12]}.0 x{v[13]})"),
            "processes": procs}


def resources() -> dict:
    latest, history = SAMPLER.snapshot()
    services = {"ollama": {"up": False, "loaded": []}, "comfyui": {"up": False}}
    try:
        ps = http_json(f"{ollama_url()}/api/ps", timeout=1.5)
        services["ollama"] = {"up": True, "loaded": [
            {"name": m["name"], "size": m.get("size"), "vram": m.get("size_vram"), "until": m.get("expires_at")}
            for m in ps.get("models", [])]}
    except Exception:
        pass
    try:
        q = http_json(f"{comfy_url()}/queue", timeout=1.5)
        services["comfyui"] = {"up": True, "running": len(q.get("queue_running", [])),
                               "pending": len(q.get("queue_pending", []))}
    except Exception:
        pass
    disks = []
    for label, path in (("Home", os.path.expanduser("~")), ("Director media", DATA)):
        try:
            du = shutil.disk_usage(path)
            disks.append({"label": label, "total": du.total, "used": du.used})
        except OSError:
            pass
    jobs = sorted(STORE.data["jobs"].values(), key=lambda j: j["created"], reverse=True)[:12]
    with open("/proc/uptime") as f:
        uptime = float(f.read().split()[0])
    return {"time": now_iso(), "uptime": uptime, "threads": os.cpu_count(), **latest, "history": history,
            "services": services, "disks": disks, "flow": flow_status(),
            "jobs": [{k: j[k] for k in ("id", "kind", "status", "created", "started", "finished", "note", "error")}
                     for j in jobs]}


SAMPLER = None


# ---------------------------------------------------------------- request handling

class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


FAILED_LOGINS = {}
FAILED_LOCK = threading.Lock()

CSP = ("default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
       "font-src 'self'; script-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


class Handler(BaseHTTPRequestHandler):
    server_version = "XPSRDirector/1"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.log_date_time_string()} {self.client_ip()} {fmt % args}\n")

    def client_ip(self) -> str:
        fwd = self.headers.get("X-Forwarded-For")
        return fwd.split(",")[0].strip() if fwd else self.client_address[0]

    # -- responses

    def send(self, status: int, body: bytes, ctype: str, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, status: int, obj, extra=None):
        self.send(status, json.dumps(obj).encode(), "application/json", {"Cache-Control": "no-store", **(extra or {})})

    # -- auth

    def authed(self) -> bool:
        code = conf("XPSR_ACCESS_CODE")
        if not code:
            return False
        header = self.headers.get("X-Access-Code", "")
        if header and hmac.compare_digest(header.encode(), code.encode()):
            return True
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "xpsr" and hmac.compare_digest(v.encode(), session_token().encode()):
                return True
        return False

    def login(self, body: dict):
        ip = self.client_ip()
        with FAILED_LOCK:
            recent = [t for t in FAILED_LOGINS.get(ip, []) if time.time() - t < 600]
            FAILED_LOGINS[ip] = recent
            if len(recent) >= 8:
                raise ApiError(429, "Too many wrong codes. Wait ten minutes.")
        code = str(body.get("code", "")).strip().lower()
        if not hmac.compare_digest(code.encode(), conf("XPSR_ACCESS_CODE").lower().encode()):
            with FAILED_LOCK:
                FAILED_LOGINS[ip].append(time.time())
            time.sleep(1)
            raise ApiError(401, "That code is not right.")
        https = self.headers.get("X-Forwarded-Proto") == "https" or self.headers.get("Host", "").endswith(".ts.net")
        secure = "; Secure" if https else ""
        cookie = f"xpsr={session_token()}; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000{secure}"
        self.send_json(200, {"ok": True}, {"Set-Cookie": cookie})

    # -- body

    def read_body(self, limit: int) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ApiError(413, f"Too large: the limit is {limit >> 20} MB.")
        return self.rfile.read(n) if n else b""

    def read_json(self) -> dict:
        raw = self.read_body(MAX_JSON)
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            raise ApiError(400, "The request body is not JSON.")
        if not isinstance(body, dict):
            raise ApiError(400, "Expected a JSON object.")
        return body

    # -- routing

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            if path.startswith("/api/"):
                return self.api_get(path)
            return self.static(path)
        except ApiError as exc:
            self.send_json(exc.status, {"error": exc.message})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            # A custom header cannot be sent cross-site without a CORS preflight,
            # which this server never answers, so it doubles as CSRF protection.
            if self.headers.get("X-XPSR") != "1":
                raise ApiError(403, "Missing X-XPSR header.")
            if path == "/api/login":
                return self.login(self.read_json())
            if not self.authed():
                raise ApiError(401, "Enter the access code first.")
            self.api_post(path)
        except ApiError as exc:
            self.send_json(exc.status, {"error": exc.message})
        except urllib.error.URLError as exc:
            self.send_json(502, {"error": f"A local service did not answer: {exc.reason}"})

    def static(self, path: str):
        if path in ("/", ""):
            path = "/index.html"
        elif path in ("/resources", "/resources/"):
            path = "/resources.html"
        elif path in ("/library", "/library/"):
            path = "/library.html"
        full = os.path.realpath(os.path.join(WEB, path.lstrip("/")))
        if not full.startswith(os.path.realpath(WEB) + os.sep) or not os.path.isfile(full):
            raise ApiError(404, "Not found")
        with open(full, "rb") as f:
            body = f.read()
        ctype = {".js": "text/javascript", ".webmanifest": "application/manifest+json",
                 ".woff2": "font/woff2", ".svg": "image/svg+xml"}.get(os.path.splitext(full)[1]) or \
            mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith(("json", "+xml")):
            ctype += "; charset=utf-8"
        cache = "public, max-age=604800, immutable" if "/fonts/" in path else "no-cache"
        extra = {"Cache-Control": cache}
        if path == "/sw.js":
            extra["Service-Worker-Allowed"] = "/"
        self.send(200, body, ctype, extra)

    def api_get(self, path: str):
        if path == "/api/health":
            return self.send_json(200, {"ok": True})
        if path == "/api/session":
            return self.send_json(200, {"authed": self.authed()})
        if not self.authed():
            raise ApiError(401, "Enter the access code first.")
        if path == "/api/status":
            models = ollama_models()
            return self.send_json(200, {
                "local": {"ollama": bool(models), "models": models,
                          "default_model": conf("OLLAMA_MODEL", "llama3.2:3b"),
                          "comfyui": reachable(f"{comfy_url()}/system_stats")},
                "flow": flow_status()})
        if path == "/api/resources":
            return self.send_json(200, resources())
        if path == "/api/library":
            return self.send_json(200, library())
        if path == "/api/jobs":
            jobs = sorted(STORE.data["jobs"].values(), key=lambda j: j["created"], reverse=True)[:50]
            return self.send_json(200, {"jobs": jobs})
        m = re.fullmatch(r"/api/jobs/([0-9a-f]{12})", path)
        if m:
            job = STORE.data["jobs"].get(m.group(1))
            if not job:
                raise ApiError(404, "No such job")
            return self.send_json(200, {"job": job, "media": [STORE.media(n) for n in job["media"]]})
        m = re.fullmatch(r"/api/media/([0-9a-f]{16}\.(png|jpg|mp4))", path)
        if m:
            return self.media_file(m.group(1), "download" in urllib.parse.urlparse(self.path).query)
        if path == "/api/flow/accounts":
            accounts = flow_call("/accounts", timeout=30)
            detail = {}
            for email in list(accounts)[:5]:
                try:
                    a = flow_call(f"/accounts/{urllib.parse.quote(email)}", timeout=30)
                    detail[email] = {"credits": a.get("credits"),
                                     "video_models": [{k: v for k, v in vm.items()
                                                       if k in ("key", "displayName", "creditCost", "paygateTier")}
                                                      for vm in a.get("models", {}).get("videoModels", [])]}
                    if isinstance(a.get("credits", {}).get("credits"), (int, float)):
                        STORE.data["flow_balance"] = {"credits": a["credits"]["credits"], "time": now_iso()}
                except ApiError:
                    pass
            return self.send_json(200, {"accounts": {e: {"health": a.get("health"), "error": a.get("error"),
                                                         **detail.get(e, {})} for e, a in accounts.items()},
                                        "flow": flow_status()})
        raise ApiError(404, "Not found")

    def media_file(self, name: str, download: bool = False):
        full = os.path.join(MEDIA, name)
        if not os.path.isfile(full):
            raise ApiError(404, "No such media")
        size = os.path.getsize(full)
        ctype = {"png": "image/png", "jpg": "image/jpeg", "mp4": "video/mp4"}[name.rsplit(".", 1)[1]]
        rng = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        with open(full, "rb") as f:
            if rng and (rng.group(1) or rng.group(2)):
                # Safari will not play a video without byte ranges.
                if rng.group(1):
                    start = int(rng.group(1))
                    end = min(int(rng.group(2)) if rng.group(2) else size - 1, size - 1)
                else:
                    start, end = max(0, size - int(rng.group(2))), size - 1
                if start > end:
                    return self.send(416, b"", ctype, {"Content-Range": f"bytes */{size}"})
                f.seek(start)
                return self.send(206, f.read(end - start + 1), ctype,
                                 {"Content-Range": f"bytes {start}-{end}/{size}", "Accept-Ranges": "bytes",
                                  "Cache-Control": "private, max-age=86400"})
            extra = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=86400"}
            if download:
                item = STORE.media(name) or {}
                stem = re.sub(r"[^a-z0-9]+", "-", (item.get("label") or item.get("kind") or "media").lower()).strip("-")
                extra["Content-Disposition"] = f'attachment; filename="{stem[:60] or "media"}-{name}"'
            self.send(200, f.read(), ctype, extra)

    def api_post(self, path: str):
        if path == "/api/logout":
            return self.send_json(200, {"ok": True}, {"Set-Cookie": "xpsr=; Path=/; Max-Age=0"})
        if path == "/api/local/chat":
            return self.send_json(200, local_chat(self.read_json()))
        if path == "/api/upload":
            ctype = self.headers.get("Content-Type", "")
            ext = {"image/png": "png", "image/jpeg": "jpg"}.get(ctype.split(";")[0])
            if not ext:
                raise ApiError(415, "Upload a PNG or JPEG. (The app converts phone photos before sending.)")
            data = self.read_body(MAX_UPLOAD)
            item = STORE.add_media(data, ext, kind="image", source="upload",
                                   tool_or_model="Phone camera (human)", seed="",
                                   prompt="Photographed on a phone", label=urllib.parse.unquote(self.headers.get("X-Label", ""))[:200],
                                   project=urllib.parse.unquote(self.headers.get("X-Project", ""))[:200])
            return self.send_json(200, {"media": item})
        if path == "/api/local/keyframe":
            body = self.read_json()
            prompt = str(body.get("prompt", "")).strip()
            if len(prompt) < 5:
                raise ApiError(400, "Write a visual prompt first.")
            ref = body.get("reference") or None
            if ref and not STORE.media(ref):
                raise ApiError(404, "The reference image is missing.")
            params = {"prompt": prompt[:4000], "seed": int(body.get("seed") or secrets.randbelow(10**9)),
                      "reference": ref, "frame": body.get("frame", "first"), "shot": body.get("shot"),
                      "label": str(body.get("label", ""))[:200], "project": str(body.get("project", ""))[:200]}
            return self.send_json(200, {"job": start_job("keyframe", params)})
        if path == "/api/flow/token":
            body = self.read_json()
            if "token" in body:  # absent: keep the saved token and change only the settings
                token = str(body["token"] or "").strip()
                if token and not re.fullmatch(r"[A-Za-z0-9._:\-]{16,512}", token):
                    raise ApiError(400, "That does not look like a useapi.net token.")
                write_env("USEAPI_TOKEN", token)
            if "email" in body:
                write_env("FLOW_EMAIL", str(body["email"]).strip())
            if body.get("plan") in ("free", "plus", "pro", "ultra"):
                write_env("FLOW_PLAN", body["plan"])
            if str(body.get("daily_credits", "")).isdigit():
                write_env("FLOW_DAILY_CREDITS", str(int(body["daily_credits"])))
            return self.send_json(200, {"flow": flow_status()})
        if path == "/api/flow/image":
            body = self.read_json()
            if not flow_token():
                raise ApiError(400, "No useapi.net token yet. Add one on the Accounts panel.")
            model = body.get("model") or FLOW_IMAGE_MODELS[0]
            if model not in FLOW_IMAGE_MODELS:
                raise ApiError(400, f"Unknown image model {model}")
            params = {"prompt": str(body.get("prompt", ""))[:4000], "model": model,
                      "seed": int(body.get("seed") or secrets.randbelow(10**9)), "reference": body.get("reference"),
                      "frame": body.get("frame", "first"), "shot": body.get("shot"), "email": body.get("email"),
                      "label": str(body.get("label", ""))[:200], "project": str(body.get("project", ""))[:200]}
            return self.send_json(200, {"job": start_job("flow_image", params)})
        if path == "/api/flow/video":
            return self.send_json(200, {"job": self.flow_video(self.read_json())})
        raise ApiError(404, "Not found")

    def flow_video(self, body: dict) -> dict:
        model = body.get("model", "veo-3.1-fast")
        if model not in FLOW_MODELS:
            raise ApiError(400, f"Unknown video model {model}")
        status = {m["id"]: m for m in flow_status()["models"]}[model]
        if not status["allowed"]:
            raise ApiError(400, f"{status['label']} needs a paid Flow plan.")
        duration = int(body.get("duration") or status["durations"][-1])
        if duration not in status["durations"]:
            raise ApiError(400, f"{status['label']} on this plan makes {status['durations']}-second clips.")
        start = body.get("start")
        if not start or not STORE.media(start):
            raise ApiError(400, "Lock a first frame before asking for motion (two-pass rule).")
        if body.get("end") and not STORE.media(body["end"]):
            raise ApiError(400, "The last frame is missing.")
        prompt = str(body.get("prompt", "")).strip()
        if len(prompt) < 5:
            raise ApiError(400, "Write the action: what moves between the first and last frame.")
        if not flow_token():
            raise ApiError(400, "No useapi.net token yet. Add one on the Accounts panel.")
        cost = flow_cost(model, duration)
        with FLOW_LOCK:
            left = flow_budget() - STORE.spent_today()
            if cost > left:
                raise ApiError(402, f"{status['label']} costs {cost} credits and only {max(left, 0)} are left in "
                                    f"today's budget of {flow_budget()}. "
                                    + ("Use Veo 3.1 Lite, hold the still, or wait until tomorrow." if model != "veo-3.1-lite" and left >= 10
                                       else "Hold the still, or wait until tomorrow."))
            bal = STORE.data.get("flow_balance")
            if bal and bal["time"][:10] == datetime.datetime.now(datetime.timezone.utc).date().isoformat() \
                    and bal["credits"] < cost:
                raise ApiError(402, f"The Flow account reported {bal['credits']} credits left; this clip needs {cost}.")
            params = {"prompt": prompt[:4000], "model": model, "duration": duration, "start": start,
                      "end": body.get("end") or None, "seed": body.get("seed"), "credits": cost,
                      "shot": body.get("shot"), "email": body.get("email"),
                      "label": str(body.get("label", ""))[:200], "project": str(body.get("project", ""))[:200]}
            job = STORE.new_job("flow_video", params)
            STORE.charge(job["id"], model, cost)

        def work():
            try:
                names = run_flow_video(job)
                STORE.update_job(job["id"], status="done", finished=now_iso(), media=names, note=None)
            except Exception as exc:
                msg = exc.message if isinstance(exc, ApiError) else str(exc)
                STORE.refund(job["id"])
                STORE.update_job(job["id"], status="failed", finished=now_iso(), note=None,
                                 error=(msg + " The credits were put back in the local budget; "
                                        "check the live balance on the Accounts panel.")[:900])

        threading.Thread(target=work, daemon=True).start()
        return job


def main():
    global STORE, SAMPLER
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default=os.environ.get("XPSR_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("XPSR_PORT", "8790")))
    args = p.parse_args()
    ensure_access_code()
    STORE = Store()
    SAMPLER = Sampler()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print(f"XPSR Director on http://{args.host}:{args.port}  (access code in {ENV_FILE})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
