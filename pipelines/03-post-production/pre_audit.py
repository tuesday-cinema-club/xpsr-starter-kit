#!/usr/bin/env python3
"""
Pre-fill the 7-point anti-slop audit with everything a script can verify.

Machines can check evidence links, provenance coverage and technical QC.
They cannot judge intent, specificity, visual continuity or sign a release.
This script fills in the first kind and leaves the second kind clearly marked
for the human Auditor and Director. It never fills in check 7.

Writes audit.md (from workshop-build/templates/audit_template.md's layout).

Example:
    python3 pipelines/03-post-production/pre_audit.py --project my-project \\
        --bible templates/ember-and-oak-bible.json --cut my-project/cut.mp4
"""

import argparse
import csv
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import load_json, say  # noqa: E402

HUMAN = "To be scored by the Auditor"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", required=True, help="Project folder (brief.json, shots.json, provenance.csv, ...)")
    p.add_argument("--bible", required=True)
    p.add_argument("--cut", required=True, help="The cut being audited")
    p.add_argument("--out", help="audit.md path (default: <project>/audit.md)")
    args = p.parse_args()

    proj = args.project
    brief = load_json(os.path.join(proj, "brief.json"))
    shots = load_json(os.path.join(proj, "shots.json"))["shots"]
    bible = load_json(args.bible)
    rows = []

    # 2. Evidence
    log_path = os.path.join(proj, "research_log.csv")
    sources = set()
    if os.path.exists(log_path):
        with open(log_path, newline="", encoding="utf-8") as f:
            sources = {r["source_id"] for r in csv.DictReader(f)}
    missing = [(s["shot_number"], sid) for s in shots for sid in s["source_ids"] if sid not in sources]
    unsourced = [s["shot_number"] for s in shots if s["voiceover_line"].strip() and not s["source_ids"]]
    ev_ok = not missing and not unsourced
    cited = sorted({sid for s in shots for sid in s["source_ids"]})
    ev_note = (f"All {sum(1 for s in shots if s['voiceover_line'].strip())} spoken lines cite research_log.csv "
               f"({', '.join(cited)}). Auditor: confirm no on-screen claim is missing a source."
               if ev_ok else f"Missing sources: {missing}; lines with no citation: shots {unsourced}")

    # 3. Continuity (ids are machine-checkable; the look is not)
    char_ids = {c["id"] for c in bible["characters"]}
    bad_ids = [(s["shot_number"], c) for s in shots for c in s["characters"] if c not in char_ids]
    cont_note = ("Machine: every character id in shots.json exists in bible.json. "
                 "Auditor: compare faces, wardrobe and light against each visual_lock." if not bad_ids
                 else f"Unknown character ids: {bad_ids}")

    # 5. Technical QC
    qc_path = os.path.join(os.path.dirname(os.path.abspath(args.cut)), "qc.json")
    if os.path.exists(qc_path):
        qc = load_json(qc_path)
        qc_ok = qc["passed"]
        qc_note = "; ".join(f"{c['check']} {c['measured']}" for c in qc["checks"])
    else:
        qc_ok, qc_note = False, "qc.json not found: run qc_check.py first"

    # 6. Provenance
    prov_path = os.path.join(proj, "provenance.csv")
    with open(prov_path, newline="", encoding="utf-8") as f:
        prov = list(csv.DictReader(f))
    logged = {r["asset_id"] for r in prov}
    assets = [os.path.splitext(os.path.basename(x))[0] for x in sorted(glob.glob(os.path.join(proj, "frames", "shot_*_keyframe.png")))]
    assets += [os.path.basename(x) for x in sorted(glob.glob(os.path.join(proj, "audio", "*.wav")))]
    for name in ("captions.srt", os.path.basename(args.cut)):
        if os.path.exists(os.path.join(proj, name)):
            assets.append(name)
    unlogged = [a for a in assets if a not in logged]
    used = [r for r in prov if r["asset_id"] in assets and r["stage"] in ("keyframe",)]
    unapproved = [r["asset_id"] for r in used if r["status"] != "APPROVED"]
    prov_ok = not unlogged and not unapproved
    prov_note = (f"{len(assets)} delivered assets, all logged; {len(prov)} rows including rejected takes."
                 if prov_ok else f"Unlogged: {unlogged}; keyframes not approved: {unapproved}")
    scratch = [r["asset_id"] for r in prov if "SCRATCH" in r["tool_or_model"]]

    rows = [
        (1, "Intent: honors the brief and every exclusion", HUMAN,
         "Exclusions to check: " + "; ".join(brief["exclusions"])),
        (2, "Evidence: every claim cites research_log.csv", "Pass" if ev_ok else "Fail", ev_note),
        (3, "Continuity: matches bible.json", HUMAN, cont_note),
        (4, "Specificity: could only be this brand", HUMAN, "Auditor: name the details only this client has."),
        (5, "Technical QC", "Pass" if qc_ok else "Fail", qc_note),
        (6, "Provenance: every asset logged", "Pass" if prov_ok else "Fail", prov_note),
        (7, "Human signature (non-negotiable)", "Director only",
         "Not machine-checkable. Unsigned until a named human signs below."
         + (f" Note: {', '.join(scratch)} is a SCRATCH stand-in and must be replaced by a human take." if scratch else "")),
    ]

    out = args.out or os.path.join(proj, "audit.md")
    lines = [
        f"# Anti-Slop Audit: {brief['project_title']}",
        "",
        f"Cut reviewed: `{os.path.basename(args.cut)}`",
        "",
        "Checks 2, 5 and 6 were pre-filled by `pre_audit.py`. Checks 1, 3, 4 and 7 need a person.",
        "",
        "| Number | Check | Result | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {n} | {name} | {res} | {note} |" for n, name, res, note in rows]
    lines += [
        "",
        "Score: (number passed) of 7. Release needs 7 of 7.",
        "",
        "## Release",
        "",
        "Director signature:",
        "",
        "Date:",
        "",
    ]
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    for n, name, res, _ in rows:
        say("ok" if res == "Pass" else ("x" if res == "Fail" else "!"), f"{n}. {name}: {res}")
    say(">", f"{out} written. Hand it to the Auditor; the Director signs check 7.")


if __name__ == "__main__":
    main()
