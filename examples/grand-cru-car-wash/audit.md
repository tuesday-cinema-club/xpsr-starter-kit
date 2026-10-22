# Anti-Slop Audit: The Sommelier of Suds

Cut reviewed: `cut.mp4`

Checks 2, 5 and 6 were pre-filled by `pre_audit.py`. Checks 1, 3, 4 and 7 need a person.

| Number | Check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Intent: honors the brief and every exclusion | To be scored by the Auditor | Exclusions to check: No naming or mocking real wineries or businesses; No water-waste or drought jokes; No bikini car-wash tropes |
| 2 | Evidence: every claim cites research_log.csv | Pass | All 3 spoken lines cite research_log.csv (SRC-001, SRC-002, SRC-003, SRC-004, SRC-005). Auditor: confirm no on-screen claim is missing a source. |
| 3 | Continuity: matches bible.json | To be scored by the Auditor | Machine: every character id in shots.json exists in bible.json. Auditor: compare faces, wardrobe and light against each visual_lock. |
| 4 | Specificity: could only be this brand | To be scored by the Auditor | Auditor: name the details only this client has. |
| 5 | Technical QC | Pass | Aspect ratio 1920x1080; Frame rate 24 fps; Runtime 30.00s; Audio stream aac; Integrated loudness -15.5 LUFS; True peak -1.4 dBTP |
| 6 | Provenance: every asset logged | Pass | 6 delivered assets, all logged; 9 rows including rejected takes. |
| 7 | Human signature (non-negotiable) | Director only | Not machine-checkable. Unsigned until a named human signs below. Note: vo_scratch.wav is a SCRATCH stand-in and must be replaced by a human take. |

Score: (number passed) of 7. Release needs 7 of 7.

## Demo auditor notes

> These notes were written during the demo run by Claude (the AI assistant that built and ran this kit), standing in for the human Auditor so the example is complete. They are not a sign-off. Check 7 is left blank on purpose: only a named human director can sign.

| Number | Stand-in result | Notes |
| --- | --- | --- |
| 1 Intent | Pass, with a note | No real wineries or businesses named, no drought or water jokes, no bikini tropes. The call to action is spoken. Note: the generated car grilles carry badges that look like real carmakers' logos; blur or paint them out before release to stay clear of the first exclusion. |
| 3 Continuity | **Fail** | The driver matches across shots 1 and 3, but the Wash Sommelier gains a dark fedora in shot 3 that the bible does not include and shot 2 does not show. A shape in the back seat of the shot 1 car may be a person. |
| 4 Specificity | Pass, with a note | The sommelier swirling foam, the tastevin and the package names are specific to this client. The shot 1 car does not look dusty, which undercuts the line about vineyard dust. |
| 7 Human signature | Not signed | The voiceover is still the synthetic SCRATCH track. |

**Stand-in verdict: Revise, 5 of 7.** Next steps: paint out the fedora in shot 3 (or rerender with the hat named in the prompt as absent), add dust to the shot 1 car in GIMP, blur grille badges, record a human voiceover.

## Release

Director signature:

Date:
