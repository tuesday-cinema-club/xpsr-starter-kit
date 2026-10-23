# Anti-Slop Audit: Agentic Workflows: Zero Cost, Infinite Potential

Cut reviewed: `cut.mp4`

Checks 2, 5 and 6 were pre-filled by `pre_audit.py`. Checks 1, 3, 4 and 7 need a person.

| Number | Check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Intent: honors the brief and every exclusion | To be scored by the Auditor | Exclusions to check: No cloud service vendor shilling; No artificial AI hype jargon or hallucinated promises; No unverified claims without human approval |
| 2 | Evidence: every claim cites research_log.csv | Pass | All 6 spoken lines cite research_log.csv (SRC-001, SRC-002, SRC-004, SRC-005, SRC-006, SRC-007). Auditor: confirm no on-screen claim is missing a source. |
| 3 | Continuity: matches bible.json | To be scored by the Auditor | Machine: every character id in shots.json exists in bible.json. Auditor: compare faces, wardrobe and light against each visual_lock. |
| 4 | Specificity: could only be this brand | To be scored by the Auditor | Auditor: name the details only this client has. |
| 5 | Technical QC | Pass | Aspect ratio 1920x1080; Frame rate 24 fps; Runtime 30.00s; Audio stream aac; Integrated loudness -14.6 LUFS; True peak -1.6 dBTP |
| 6 | Provenance: every asset logged | Pass | 13 delivered assets, all logged; 25 rows including rejected takes. |
| 7 | Human signature (non-negotiable) | Director only | Not machine-checkable. Unsigned until a named human signs below. Note: vo_scratch.wav, vo_clone.wav are SCRATCH stand-ins and must be replaced by a human take. |

Score: (number passed) of 7. Release needs 7 of 7.

## Demo auditor notes

> These notes were written during the demo run by Claude (the AI assistant that built and ran this kit), standing in for the human Auditor so the example is complete. They are not a sign-off. Check 7 is left blank on purpose: only a named human director can sign. The audit of the earlier cut, with the Kokoro voice and no music, is in [`before/audit.md`](before/audit.md).

| Number | Stand-in result | Notes |
| --- | --- | --- |
| 1 Intent | Pass | No cloud vendor named or praised. Adobe appears only as the sourced price comparison (SRC-007). No AI hype words. The call to action is spoken and the end card carries the date and the starter kit address as typed text. The music bed stays under the voice: Whisper transcribes every word of the final mix correctly. |
| 3 Continuity | **Fail** | The instructor is the most consistent person in any example so far: the same face, hair, beard and black sweater in shots 1, 3, 5 and 6, and Wan keeps the face through every move. The voice now matches the face, cloned from the instructor's own recording. The room does not hold. The screening room's projector is a single booth beam above the host in shot 3, a projector hanging inside the room in shot 4, and two booth windows on either side in shot 6. In shot 1 the vintage camera on the left turns blue halfway through the move. |
| 4 Specificity | Pass | The instructor's own face and voice, used with consent; the club's screening room; real grey-box previs from this kit on the monitors in shot 2; the $840 figure and the summit date. |
| 7 Human signature | Not signed | The voice is a synthetic clone of the instructor, not a performance: say so in the credits or record the lines for real. The music bed was picked from three MusicGen takes by measurement, not by ear; the director should listen to all three. Keyframes (FLUX.2 [dev]) and music (MusicGen) are both licensed for non-commercial use only: check both licenses before using this cut to sell anything. |

**Stand-in verdict: Revise, 5 of 7.** Next steps: retake shot 6's keyframe with "one projector beam from a single booth window at the back, centered" and animate it again; paint the shot 1 camera back to black in the first frames or crop it out; listen to the three music takes and confirm the pick; disclose the cloned voice or record a human take; settle the FLUX.2 [dev] and MusicGen licenses or rebuild those parts with Apache 2.0 models.

## Release

Director signature:

Date:
