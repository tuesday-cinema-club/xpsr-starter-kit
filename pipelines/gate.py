#!/usr/bin/env python3
"""
Record a human decision at a gate.

Every gate has exactly four exits: Approve, Revise, Reject, Request Evidence.
Agents write state files with status "awaiting_review"; only this command,
run by a person, moves them on. Optionally it also stamps the approver's name
on pending rows in provenance.csv.

Examples:
    python3 pipelines/gate.py --state my-project/shots_state.json --decision Approve --by "Sam (director)"
    python3 pipelines/gate.py --state my-project/shots_state.json --decision Revise \\
        --by "Sam (director)" --note "Shot 2 should be a 50mm, not 85mm"
    python3 pipelines/gate.py --state my-project/frames_state.json --decision Approve \\
        --by "Sam (director)" --provenance my-project/provenance.csv
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (GATE_DECISIONS, PROVENANCE_FIELDS, load_json, load_schema,  # noqa: E402
                    say, utc_now, validate, write_json)

STATUS_FOR = {
    "Approve": "approved",
    "Revise": "revise",
    "Reject": "rejected",
    "Request Evidence": "evidence_requested",
}
# Which provenance rows each gate may stamp: a gate only decides on its own stage's assets.
STAGES_FOR_GATE = {
    "brief": set(),
    "previs": {"shot_list"},
    "produce": {"keyframe", "paint_over", "temporal"},
    "present": {"dialogue", "captions", "edit"},
}
PROVENANCE_STATUS_FOR = {
    "Approve": "APPROVED",
    "Revise": "REVISE",
    "Reject": "REJECTED",
    "Request Evidence": "EVIDENCE_REQUESTED",
}


def stamp_provenance(path: str, decision: str, by: str, gate_stage: str) -> int:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    changed = 0
    for row in rows:
        if row.get("status") == "PENDING_REVIEW" and row.get("stage") in STAGES_FOR_GATE.get(gate_stage, set()):
            row["status"] = PROVENANCE_STATUS_FOR[decision]
            row["human_approver"] = by
            changed += 1
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PROVENANCE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return changed


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--state", required=True, help="State file written by an agent")
    p.add_argument("--decision", required=True, choices=GATE_DECISIONS)
    p.add_argument("--by", required=True, help="Name of the human making the decision")
    p.add_argument("--note", default="", help="Reason or instructions, e.g. what to revise")
    p.add_argument("--provenance", help="provenance.csv: stamp this decision on this gate's rows still PENDING_REVIEW")
    args = p.parse_args()

    state = load_json(args.state)
    if state["checks"].get("schema") == "fail" and args.decision == "Approve":
        sys.exit("Refusing to approve: this draft failed its schema check. Choose Revise or Reject.")

    state["decision"] = args.decision
    state["status"] = STATUS_FOR[args.decision]
    state["decided_by"] = args.by
    state["decided_at"] = utc_now()
    state["notes"] = args.note
    state["history"].append({"at": state["decided_at"], "event": args.decision, "by": args.by, "note": args.note})

    errors = validate(state, load_schema("state"))
    if errors:
        sys.exit(f"State file would become invalid: {errors}")
    write_json(args.state, state)
    say("ok", f"{state['stage']} gate: {args.decision} by {args.by}")

    if args.provenance and os.path.exists(args.provenance):
        n = stamp_provenance(args.provenance, args.decision, args.by, state["stage"])
        say("ok", f"{n} provenance row(s) marked {PROVENANCE_STATUS_FOR[args.decision]}")

    if args.decision == "Approve":
        say(">", "Commit the approved work before the next stage:")
        print(f"      git add -A && git commit -m \"Gate ({state['stage']}): approved by {args.by}\"")
    elif args.decision == "Request Evidence":
        say(">", "Add the missing rows to research_log.csv, then rerun the agent.")
    else:
        say(">", "Rerun the agent with the director's note, or start this stage again.")


if __name__ == "__main__":
    main()
