"""
Shared helpers for every pipeline stage.

Standard library only, so the starter kit runs on a fresh laptop with nothing
but Python 3.9+ installed. If the optional `jsonschema` package is present it
is used for validation; otherwise a small built-in validator covers the subset
of JSON Schema that the files in schemas/ use.
"""

import csv
import datetime as _dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(REPO_ROOT, "schemas")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
if not OLLAMA_HOST.startswith("http"):
    OLLAMA_HOST = "http://" + OLLAMA_HOST
DEFAULT_MODEL = os.environ.get("TCC_MODEL", "llama3.2:3b")

PROVENANCE_FIELDS = [
    "asset_id", "timestamp", "stage", "tool_or_model", "checkpoint_hash",
    "seed", "prompt_or_input", "human_approver", "status",
]

GATE_DECISIONS = ["Approve", "Revise", "Reject", "Request Evidence"]


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------

def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_schema(name: str) -> dict:
    """Load a schema from schemas/ by short name, e.g. 'brief'."""
    return load_json(os.path.join(SCHEMA_DIR, f"{name}.schema.json"))


def say(symbol: str, message: str) -> None:
    """Print a status line. Symbols are paired with words so meaning never
    depends on the glyph alone (screen readers may skip it)."""
    labels = {"*": "[working]", "ok": "[pass]", "x": "[fail]", "!": "[warn]", ">": "[next]"}
    print(f"{labels.get(symbol, symbol)} {message}", flush=True)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "integer": int, "number": (int, float), "null": type(None),
}


def _type_ok(value, expected) -> bool:
    if isinstance(expected, list):
        return any(_type_ok(value, e) for e in expected)
    if expected in ("integer", "number") and isinstance(value, bool):
        return False
    if expected == "integer" and isinstance(value, float):
        return value.is_integer()
    return isinstance(value, _TYPES[expected])


def _mini_validate(value, schema, root, path, errors):
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"Only local $ref supported, got {ref}")
        target = root
        for part in ref[2:].split("/"):
            target = target[part]
        schema = target
    where = path or "(root)"
    if "type" in schema and not _type_ok(value, schema["type"]):
        errors.append(f"{where}: expected {schema['type']}, got {type(value).__name__}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{where}: {value} is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{where}: {value} is above maximum {schema['maximum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{where}: shorter than {schema['minLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{where}: needs at least {schema['minItems']} items, has {len(value)}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{where}: allows at most {schema['maxItems']} items, has {len(value)}")
        if "items" in schema:
            for i, item in enumerate(value):
                _mini_validate(item, schema["items"], root, f"{path}[{i}]", errors)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}: missing required field '{key}'")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in value:
                _mini_validate(value[key], sub, root, f"{path}.{key}" if path else key, errors)
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{where}: unexpected field '{key}'")


def validate(instance, schema: dict) -> list:
    """Return a list of human-readable error strings. Empty list means valid."""
    try:
        import jsonschema  # optional
    except ImportError:
        errors = []
        _mini_validate(instance, schema, schema, "", errors)
        return errors
    validator = jsonschema.Draft202012Validator(schema)
    out = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in err.path) or "(root)"
        out.append(f"{loc}: {err.message}")
    return out


# --------------------------------------------------------------------------
# Ollama (local model daemon on port 11434, no cloud calls)
# --------------------------------------------------------------------------

def _strip_for_ollama(schema: dict) -> dict:
    """Ollama turns the schema into a decoding grammar. Drop keywords it does
    not need (titles, $schema) so the grammar stays small. Validation still
    runs against the full schema afterwards."""
    if isinstance(schema, dict):
        return {k: _strip_for_ollama(v) for k, v in schema.items()
                if k not in ("$schema", "$id", "title", "description")}
    if isinstance(schema, list):
        return [_strip_for_ollama(v) for v in schema]
    return schema


def ollama_generate(prompt: str, model: str = DEFAULT_MODEL, schema: dict = None,
                    system: str = None, seed: int = 42, temperature: float = 0.0,
                    timeout: int = 600):
    """Call the local Ollama daemon. With `schema`, Ollama constrains decoding
    to that JSON Schema and the parsed object is returned. Fixed seed and zero
    temperature keep reruns repeatable."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "seed": seed},
    }
    if system:
        payload["system"] = system
    if schema is not None:
        payload["format"] = _strip_for_ollama(schema)
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        sys.exit(f"Ollama returned HTTP {exc.code}: {detail}\n"
                 f"Is the model pulled? Try: ollama pull {model}")
    except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
        sys.exit(f"Could not reach Ollama at {OLLAMA_HOST} ({exc}).\n"
                 "Start it with 'ollama serve' (or open the Ollama app) and try again.")
    text = body.get("response", "")
    if schema is None:
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned invalid JSON: {exc}\n{text[:500]}")


# --------------------------------------------------------------------------
# Provenance ledger and gate state
# --------------------------------------------------------------------------

def append_provenance(csv_path: str, **row) -> None:
    """Append one row to provenance.csv, creating it with a header if needed."""
    new_file = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    parent = os.path.dirname(csv_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    row.setdefault("timestamp", utc_now())
    row.setdefault("checkpoint_hash", "N/A")
    row.setdefault("seed", "N/A")
    row.setdefault("human_approver", "")
    row.setdefault("status", "PENDING_REVIEW")
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PROVENANCE_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in PROVENANCE_FIELDS})


def new_state(project_id: str, stage: str, draft_file: str, checks: dict) -> dict:
    """Build a state record that pauses the pipeline at a human gate."""
    return {
        "project_id": project_id,
        "stage": stage,
        "status": "awaiting_review",
        "draft_file": draft_file,
        "checks": checks,
        "decision": None,
        "decided_by": None,
        "decided_at": None,
        "notes": "",
        "history": [{"at": utc_now(), "event": "draft_written", "by": "agent"}],
    }


def file_sha256_short(path: str, length: int = 10, cache: str = None) -> str:
    """Short SHA-256 of a (possibly multi-GB) model file, cached by size+mtime."""
    import hashlib
    st = os.stat(path)
    key = f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}"
    store = {}
    if cache and os.path.exists(cache):
        try:
            store = load_json(cache)
        except (OSError, json.JSONDecodeError):
            store = {}
    if key in store:
        return store[key]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()[:length]
    if cache:
        store[key] = digest
        write_json(cache, store)
    return digest
