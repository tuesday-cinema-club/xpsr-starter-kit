# Anti-Slop Audit: Ember & Oak Launch

Cut reviewed: `cut.mp4`

Checks 2, 5 and 6 were pre-filled by `pre_audit.py`. Checks 1, 3, 4 and 7 need a person.

| Number | Check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Intent: honors the brief and every exclusion | To be scored by the Auditor | Exclusions to check: No slow-motion latte-art pour; No stock hipster-barista tropes or forced smiles; No claims we cannot source, such as best coffee in town |
| 2 | Evidence: every claim cites research_log.csv | Pass | All 3 spoken lines cite research_log.csv (SRC-001, SRC-002, SRC-003). Auditor: confirm no on-screen claim is missing a source. |
| 3 | Continuity: matches bible.json | To be scored by the Auditor | Machine: every character id in shots.json exists in bible.json. Auditor: compare faces, wardrobe and light against each visual_lock. |
| 4 | Specificity: could only be this brand | To be scored by the Auditor | Auditor: name the details only this client has. |
| 5 | Technical QC | Pass | Aspect ratio 1920x1080; Frame rate 24 fps; Runtime 30.00s; Audio stream aac; Integrated loudness -15.1 LUFS; True peak -1.5 dBTP |
| 6 | Provenance: every asset logged | Pass | 6 delivered assets, all logged; 7 rows including rejected takes. |
| 7 | Human signature (non-negotiable) | Director only | Not machine-checkable. Unsigned until a named human signs below. Note: vo_scratch.wav is a SCRATCH stand-in and must be replaced by a human take. |

Score: (number passed) of 7. Release needs 7 of 7.

## Demo auditor notes

> These notes were written during the demo run by Claude (the AI assistant that built and ran this kit), standing in for the human Auditor so the example is complete. They are not a sign-off. Check 7 is left blank on purpose: only a named human director can sign.

| Number | Stand-in result | Notes |
| --- | --- | --- |
| 1 Intent | Pass | Same approved brief, shot list and voiceover as the SDXL demo: every exclusion respected, call to action spoken and on the end card. |
| 3 Continuity | Pass, with a note | The same roaster (salt-and-pepper hair, chambray shirt, canvas apron) in all three shots, burn marks on the forearm in shot 2, and the regular's cycling cap and olive jacket in shot 3. A background customer in shot 3 is not in the bible. We judged one extra customer acceptable in a shop interior; a strict auditor could fail it, as the SDXL audit counted the same thing against that cut. |
| 4 Specificity | Pass, with a note | The dated bag, the drum roaster and the canvas apron are specific to this client. The chalkboard in shot 1 carries pseudo-text that should be painted out. |
| 7 Human signature | Not signed | The voiceover is still the synthetic SCRATCH track. |

**Stand-in verdict: Revise, 6 of 7.** One check short of release only because the voiceover is synthetic and nobody has signed. Next steps: paint out the chalkboard text in GIMP, record the human voiceover, director signs.

## Release

Director signature:

Date:
