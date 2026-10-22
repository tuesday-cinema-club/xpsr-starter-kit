#!/usr/bin/env python3
"""
Gate 01 helper: draft brief.json and brief.md with a local model.

The director's three answers and the room's exclusions are passed in on the
command line and copied into the brief word for word. The model only drafts
the parts a writer would: a working title, the key message and tone words.
The result is validated against schemas/brief.schema.json and held at Gate 01.

Example:
    python3 pipelines/01-pre-production/draft_brief.py \\
        --client-brief workshop-build/client-briefs/ember-and-oak.md \\
        --research-log examples/ember-and-oak-demo/research_log.csv \\
        --who "Neighbors who already walk past the new shop" \\
        --feel "Like the roastery is part of their street" \\
        --do "Visit the second shop this week" \\
        --exclusion "No slow-motion latte-art pour" \\
        --exclusion "No stock hipster barista tropes" \\
        --exclusion "No claims we cannot source" \\
        --out-dir my-project/
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import (DEFAULT_MODEL, load_schema, new_state, ollama_generate,  # noqa: E402
                    read_text, say, validate, write_json)

SYSTEM = (
    "You are the Writer on a small film crew. You draft creative briefs. "
    "You never invent facts: the key message may only use facts from the research log. "
    "You write plainly and specifically. Avoid cliches such as 'more than just', "
    "'crafted with passion', 'elevate', 'journey'."
)


def load_facts(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [(r["source_id"], r["claim"]) for r in csv.DictReader(f)]


def render_markdown(brief: dict, director: str, decision: str = "awaiting director", date: str = "") -> str:
    lines = [
        f"# Project Brief: {brief['project_title']}",
        "",
        f"Client: {brief['client']}",
        "",
        "## 1. Director's three answers",
        "",
        f"- **Who is it for?** {brief['target_audience']}",
        f"- **What should they feel?** {brief['core_feeling']}",
        f"- **What should they do next?** {brief['call_to_action']}",
        "",
        "## 2. Key message",
        "",
        brief["key_message"],
        "",
        "## 3. Runtime",
        "",
        f"{brief['runtime_sec']} seconds.",
        "",
        "## 4. Tone",
        "",
        ", ".join(brief.get("tone", [])) or "(none given)",
        "",
        "## 5. Exclusions",
        "",
        "This spot will never:",
        "",
    ]
    lines += [f"{i}. {x}" for i, x in enumerate(brief["exclusions"], 1)]
    if brief.get("references"):
        lines += ["", "## 6. References", ""] + [f"- {r}" for r in brief["references"]]
    lines += [
        "",
        "## Approval",
        "",
        f"- Gate 01 decision: {decision}",
        f"- Director: {director}",
        f"- Date: {date}",
        "",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--client-brief", required=True, help="Client brief markdown, e.g. workshop-build/client-briefs/ember-and-oak.md")
    p.add_argument("--research-log", help="research_log.csv with the facts you are allowed to claim")
    p.add_argument("--who", required=True, help="Director answer: who is it for?")
    p.add_argument("--feel", required=True, help="Director answer: what should they feel?")
    p.add_argument("--do", required=True, dest="do_next", help="Director answer: what should they do next?")
    p.add_argument("--exclusion", action="append", default=[], help="Something the spot will never do. Repeat at least 3 times.")
    p.add_argument("--director", default="(director name)", help="Name written on the approval line")
    p.add_argument("--runtime", type=int, default=30, help="Runtime in seconds (default 30)")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default {DEFAULT_MODEL})")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", default="drafts", help="Where to write brief.json, brief.md and brief_state.json")
    args = p.parse_args()

    if len(args.exclusion) < 3:
        sys.exit("Gate 01 needs at least three exclusions. Add --exclusion three times.")

    client_text = read_text(args.client_brief)
    facts = load_facts(args.research_log)
    facts_text = "\n".join(f"- {sid}: {claim}" for sid, claim in facts) or "- (no research log given: make no factual claims)"
    schema = load_schema("brief")

    prompt = f"""Draft a creative brief as JSON.

CLIENT BRIEF:
{client_text}

FACTS YOU MAY USE (and no others):
{facts_text}

DIRECTOR'S ANSWERS (copy exactly):
- target_audience: {args.who}
- core_feeling: {args.feel}
- call_to_action: {args.do_next}

EXCLUSIONS (copy exactly):
{chr(10).join('- ' + x for x in args.exclusion)}

Write: a short working project_title, the client name, a one-sentence key_message
built only from the facts above, 3 to 5 tone words, and 2 or 3 references described
in words (films, photographers or sounds). runtime_sec is {args.runtime}."""

    say("*", f"Drafting brief with {args.model} on the local Ollama daemon ...")
    brief = ollama_generate(prompt, model=args.model, schema=schema, system=SYSTEM, seed=args.seed)

    # The director's words are locked: overwrite whatever the model wrote.
    brief["target_audience"] = args.who
    brief["core_feeling"] = args.feel
    brief["call_to_action"] = args.do_next
    brief["exclusions"] = list(args.exclusion)
    brief["runtime_sec"] = args.runtime

    errors = validate(brief, schema)
    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, "brief.json")
    md_path = os.path.join(args.out_dir, "brief.md")
    state_path = os.path.join(args.out_dir, "brief_state.json")
    write_json(json_path, brief)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(brief, args.director))

    state = new_state(brief.get("project_title", "untitled"), "brief", json_path,
                      {"schema": "fail" if errors else "pass", "bible_match": "not_applicable",
                       "attempts": 1, "errors": errors})
    write_json(state_path, state)

    if errors:
        say("x", "brief.json failed schema validation:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    say("ok", f"{json_path} matches brief.schema.json")
    say("ok", f"{md_path} written for the director to read")
    say(">", "Gate 01 paused: awaiting director decision.")
    print(f"      python3 pipelines/gate.py --state {state_path} --decision Approve --by \"<director>\"")


if __name__ == "__main__":
    main()
