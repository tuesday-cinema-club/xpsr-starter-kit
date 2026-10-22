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
| 6 | Provenance: every asset logged | Pass | 6 delivered assets, all logged; 12 rows including rejected takes. |
| 7 | Human signature (non-negotiable) | Director only | Not machine-checkable. Unsigned until a named human signs below. Note: vo_scratch.wav is a SCRATCH stand-in and must be replaced by a human take. |

Score: (number passed) of 7. Release needs 7 of 7.

## Demo auditor notes

> These notes were written during the demo run by Claude (the AI assistant that built and ran this kit), standing in for the human Auditor so the example is complete. They are not a sign-off. Check 7 is left blank on purpose: only a named human director can sign.

| Number | Stand-in result | Notes |
| --- | --- | --- |
| 1 Intent | Pass | No latte-art pour, no forced smiles, no unsourced superlatives. The call to action ("Stop in this week") is spoken and the end card names the shop. |
| 3 Continuity | **Fail** | The roaster's face and build differ between shot 1 and shot 3. In shot 1 the apron reads as a flat board (an artifact of the grey-box figure). Shot 3 has a third person in the background who is not in the bible. The hand in shot 2 has no burn scar, which the bible locks. |
| 4 Specificity | Pass, with a note | The dated bag and the back-room roaster are specific to this client. The shop interior in shot 3 could belong to any café. |
| 7 Human signature | Not signed | The voiceover is still the synthetic SCRATCH track and must be replaced by a recorded human take. |

**Stand-in verdict: Revise.** Score with stand-in notes: 5 of 7 (checks 1, 2, 4, 5 and 6). Not cleared for release. Next steps: lock the roaster's look (a character reference image or a LoRA), paint the scar onto the shot 2 hand in GIMP, regenerate shot 3 with one background figure removed, and record the human voiceover.

## Release

Director signature:

Date:
