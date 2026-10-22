#!/usr/bin/env python3
"""
Gate 02 agent: split an approved brief into a shot list.

One agent, one job. It reads brief.json, bible.json and research_log.csv,
asks the local model for shots.json, then runs deterministic checks that need
no model at all:

  1. schema       shots.json matches schemas/shot_breakdown.schema.json
  2. bible_match  every location and character id exists in bible.json
  3. sources      every cited source_id exists in research_log.csv
  4. runtime      total duration is within the brief's runtime

If a check fails, the errors go back to the model for another attempt (up to
--retries). The result is held at Gate 02 in state.json for the director.

Agent card: agents/shot_breakdown.yaml

Example:
    python3 pipelines/01-pre-production/run_breakdown.py \\
        --brief my-project/brief.json \\
        --bible templates/ember-and-oak-bible.json \\
        --research-log my-project/research_log.csv \\
        --out my-project/shots.json
"""

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import (DEFAULT_MODEL, append_provenance, load_json, load_schema,  # noqa: E402
                    new_state, ollama_generate, say, utc_now, validate, write_json)

SYSTEM = (
    "You are a pre-production assistant on a film crew. Your only job is to split a brief "
    "into shots. Rules: use only character ids and location ids from the bible; never add "
    "characters; never invent facts; any factual claim in a voiceover line must cite a "
    "source_id from the research log, and set claims_sourced to true only when it does. "
    "Visual prompts describe what the camera sees in concrete physical detail."
)


def load_source_ids(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["source_id"]: r["claim"] for r in csv.DictReader(f)}


def deterministic_checks(shots: dict, schema: dict, bible: dict, sources: dict, runtime: float):
    errors = validate(shots, schema)
    if errors:
        return errors, {"schema": "fail", "bible_match": "fail", "unverified_sources": 0, "total_runtime_sec": 0}

    char_ids = {c["id"] for c in bible["characters"]}
    loc_ids = {loc["id"] for loc in bible["locations"]}
    bible_errors, unverified = [], 0
    for s in shots["shots"]:
        n = s["shot_number"]
        if s["location_id"] not in loc_ids:
            bible_errors.append(f"shot {n}: location_id '{s['location_id']}' is not in bible.json ({sorted(loc_ids)})")
        for c in s["characters"]:
            if c not in char_ids:
                bible_errors.append(f"shot {n}: character '{c}' is not in bible.json ({sorted(char_ids)})")
        for sid in s["source_ids"]:
            if sid not in sources:
                unverified += 1
                bible_errors.append(f"shot {n}: source_id '{sid}' is not in research_log.csv")
        if s["voiceover_line"].strip() and not s["claims_sourced"]:
            unverified += 1
            bible_errors.append(f"shot {n}: voiceover line is marked claims_sourced=false; cite a source_id or rewrite it")

    total = round(sum(s["duration_sec"] for s in shots["shots"]), 2)
    if total > runtime or total < runtime * 0.8:
        bible_errors.append(f"total runtime {total}s should be between {runtime * 0.8:.0f}s and {runtime}s")

    checks = {
        "schema": "pass",
        "bible_match": "fail" if any("bible.json" in e for e in bible_errors) else "pass",
        "unverified_sources": unverified,
        "total_runtime_sec": total,
    }
    return bible_errors, checks


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--brief", required=True, help="Approved brief.json")
    p.add_argument("--bible", required=True, help="Project bible.json")
    p.add_argument("--research-log", help="research_log.csv (claims must cite these ids)")
    p.add_argument("--out", default="drafts/shots.json", help="Where to write shots.json")
    p.add_argument("--state", help="Where to write the Gate 02 state file (default: next to --out)")
    p.add_argument("--provenance", help="provenance.csv to append a row to (default: next to --out)")
    p.add_argument("--shots", type=int, default=3, help="Number of shots (default 3)")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default {DEFAULT_MODEL})")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--retries", type=int, default=3, help="Model attempts before giving up (default 3)")
    p.add_argument("--check-only", action="store_true",
                   help="Do not call the model: re-run the checks on an existing --out file (use after a human edit)")
    args = p.parse_args()

    for path in (args.brief, args.bible):
        if not os.path.exists(path):
            sys.exit(f"Missing input: {path}")

    brief = load_json(args.brief)
    bible = load_json(args.bible)
    sources = load_source_ids(args.research_log)
    schema = load_schema("shot_breakdown")
    runtime = float(brief.get("runtime_sec", 30))
    out_dir = os.path.dirname(args.out) or "."
    state_path = args.state or os.path.join(out_dir, "shots_state.json")
    prov_path = args.provenance or os.path.join(out_dir, "provenance.csv")

    bible_view = {
        "characters": [{"id": c["id"], "visual_lock": c["visual_lock"]} for c in bible["characters"]],
        "locations": bible["locations"],
        "lighting_key": bible["visual_rules"]["lighting_key"],
        "exclusions": bible["exclusions"],
    }
    facts = "\n".join(f"- {k}: {v}" for k, v in sources.items()) or "- (none: make no factual claims)"
    base_prompt = f"""Break this brief into exactly {args.shots} shots for a {runtime:.0f}-second spot.
Durations must add up to between {runtime * 0.8:.0f} and {runtime:.0f} seconds.
Number shots from 1. Use a scene_id like "SC01".

BRIEF:
{json.dumps(brief, indent=2)}

BIBLE (the only characters and locations that exist):
{json.dumps(bible_view, indent=2)}

RESEARCH LOG (the only facts you may claim; cite their ids in source_ids):
{facts}
"""

    if args.check_only:
        shots = load_json(args.out)
        errors, checks = deterministic_checks(shots, schema, bible, sources, runtime)
        checks["attempts"] = 1
        checks["errors"] = errors
        # Keep the gate history: a re-check reopens the gate, it does not erase it.
        if os.path.exists(state_path):
            state = load_json(state_path)
            state.update({"status": "awaiting_review", "checks": checks, "decision": None,
                          "decided_by": None, "decided_at": None, "notes": ""})
        else:
            state = new_state(bible["project_id"], "previs", args.out, checks)
            state["history"] = []
        state["history"].append({"at": utc_now(), "event": "human_edit_rechecked", "by": "checker"})
        write_json(state_path, state)
        for e in errors:
            say("x", e)
        say("ok" if not errors else "x", f"Re-check of {args.out}: {'pass' if not errors else 'fail'} "
            f"(bible match {checks['bible_match']}, unverified sources {checks['unverified_sources']}, "
            f"runtime {checks['total_runtime_sec']}s)")
        say(">", "Gate 02 paused: awaiting director review.")
        sys.exit(1 if errors else 0)

    feedback, shots, errors, checks = "", None, [], {}
    for attempt in range(1, args.retries + 1):
        say("*", f"Attempt {attempt}: asking {args.model} for {args.shots} shots ...")
        prompt = base_prompt + (f"\nYOUR LAST DRAFT WAS REJECTED BY THE CHECKER:\n{feedback}\nFix every item." if feedback else "")
        shots = ollama_generate(prompt, model=args.model, schema=schema, system=SYSTEM, seed=args.seed + attempt - 1)
        errors, checks = deterministic_checks(shots, schema, bible, sources, runtime)
        if not errors:
            break
        say("!", f"Checker found {len(errors)} problem(s); sending them back to the agent.")
        for e in errors:
            print(f"      - {e}")
        feedback = "\n".join(f"- {e}" for e in errors)

    checks["attempts"] = attempt
    checks["errors"] = errors
    write_json(args.out, shots)
    state = new_state(bible["project_id"], "previs", args.out, checks)
    write_json(state_path, state)
    append_provenance(prov_path, asset_id="shots.json", stage="shot_list",
                      tool_or_model=f"ollama/{args.model}", seed=args.seed + attempt - 1,
                      prompt_or_input=f"{os.path.basename(args.brief)} + {os.path.basename(args.bible)}")

    state_errors = validate(state, load_schema("state"))
    if state_errors:
        sys.exit(f"Internal error: state file invalid: {state_errors}")

    say("ok" if checks["schema"] == "pass" else "x", f"Schema check: {checks['schema']}")
    say("ok" if checks["bible_match"] == "pass" else "x", f"Bible match: {checks['bible_match']}")
    say("ok" if checks["unverified_sources"] == 0 else "x", f"Unverified sources: {checks['unverified_sources']}")
    say("ok", f"Total runtime: {checks['total_runtime_sec']}s across {len(shots.get('shots', []))} shots")
    say("ok", f"{args.out} written ({attempt} attempt(s))")
    say(">", "Gate 02 paused: awaiting director review before previs.")
    print(f"      python3 pipelines/gate.py --state {state_path} --decision Approve --by \"<director>\"")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
