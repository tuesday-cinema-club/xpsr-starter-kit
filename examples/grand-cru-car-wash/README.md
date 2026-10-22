# Worked Example: Grand Cru Car Wash (Ironic)

A second complete build: an ironic 30-second launch spot for a fictional car wash coming to the Temecula Valley, Southern California's wine country. The car wash talks about itself like a tasting room. Made on one machine on 2026-10-22 with the bigger local models (`glm-4.7-flash` for writing, FLUX.2 [klein] 4B for images), offline, for $0.

![Animated preview, no sound: a man in a straw hat inspects his sedan on a vineyard road with hot-air balloons overhead; a bearded attendant dressed as a sommelier, in blue nitrile gloves, scowls at a wine glass of pink car-wash foam; the attendant towels the gleaming car at the tunnel exit; end card "Grand Cru Car Wash, Now pouring in the Temecula Valley". Captions are burned in.](cut-preview.webp)

[Watch the full 30-second cut with sound (MP4)](cut.mp4). There is also [a version with a selectable caption track](cut_softsubs.mp4). The preview above loops without sound.

## The joke, and who it is on

The joke is on the car wash taking itself far too seriously: three wash "vintages", an attendant styled as a sommelier, foam swirled in a wine glass. It is never on Temecula, its wineries, or the people who live there. The exclusions make that a rule.

Grand Cru Car Wash is fictional. The two facts about Temecula (dozens of wineries; hot-air balloon flights) come from public sources linked in [`research_log.csv`](research_log.csv). Winery counts differ by source and year, so the script says "dozens", not a number.

## About the gate decisions in this example

As in the first example, there was no human director in the room. Gate decisions are recorded as "Workshop director (demo stand-in)", and the Revise notes and hand edits were made by Claude, the AI assistant that built and ran the kit. **The release is not signed.**

## What happened at each gate

### Gate 01: Brief

Director's answers: for **Temecula Valley drivers whose cars wear a permanent layer of vineyard dust**; they should feel **amused that a car wash talks like a tasting room, and charmed enough to try it**; they should **book a Reserve Triple Foam this weekend**. Exclusions: no naming or mocking real wineries or businesses; no water-waste or drought jokes; no bikini car-wash tropes.

- **Agent:** `glm-4.7-flash` drafted a valid brief in 58 seconds.
- **What broke:** the key message was accurate but had no irony ("offers three wash packages and a hand-towel finish"). One reference described The Godfather as using "a single, sustained note", which does not match the film.
- **Human fix:** Revise. Key message rewritten in the tasting-room voice: "Three vintages, from House Rinse to Grand Cru Ceramic, each finished by hand. Now pouring in the Temecula Valley." References replaced with The Grand Budapest Hotel and Sideways. Approve.

### Gate 02: Shot list

- **Agent:** three shots in 1 minute 48 seconds, passing every machine check first time. It found the voice on its own: "We offer three vintages: the House Rinse, the Reserve Triple Foam, and the Grand Cru Ceramic."
- **What broke:** shot 1's line made no sense ("The Temecula Valley is often mistaken for a vineyard..."). Shot 3 kept the sedan "dusty" after the wash. Shot 3's action said the camera pans while its `camera_move` said Static. The call to action was missing, and it ran 26 seconds.
- **Human fix:** Revise. New shot 1 (the driver tests the dust on the hood like the rim of a glass), the foam swirled in a wine glass, a gleaming car at the exit, camera moves, the call to action, 30 seconds. `--check-only` passed. Approve.
- **Previs:** two new grey-box sets were added to `blender_previs.py` for this brief: `vineyard_road` and `wash_tunnel`. The first render put the car deep in the tunnel instead of at the exit; the set was re-blocked and rerendered.

### Gate 03: Keyframes

![Three rows. Top: Blender depth passes for the three shots. Middle, take 1: shot 1 rejected (a person sitting in the car), shot 2 approved (the sommelier with the foam glass), shot 3 rejected (the driver is drying the car while the attendant stands aside). Bottom, approved: the driver by an empty car among vines with balloons overhead, the sommelier with the foam glass, and the attendant towelling the car while the driver watches.](../../docs/images/14-grand-cru-previs-to-keyframes.jpg)

- **Take 1:** shot 2 was right the first time. Shot 1 had a person sitting in the car and invented letters on the plate. Shot 3 swapped the roles: the driver was drying the car in the attendant's blue gloves.
- **Human fix:** Revise. Prompts tightened ("nobody inside the car", who holds the towel, who stands back with empty hands). Two seeds each for shots 1 and 3; the director picked seed 7000 for shot 1 and seed 8000 for shot 3. Rejected and unpicked takes are kept as small JPEGs with provenance rows.

### Post-production

- **Voiceover:** a SCRATCH Piper track, marked as a stand-in.
- **Captions:** Whisper misheard four words: "Temecular" (twice), "vintigence" for vintages, "grand crew" for Grand Cru, and "bulk" for Book. It also made captions that ran across shot changes. `transcribe.py` now breaks captions at 42 characters and 2 lines; a person fixed the words and re-cut the captions by sentence. The raw output is in `captions.whisper-raw.srt`.
- **Cut and QC:** 30.0 seconds, 1920 by 1080, 24 fps, minus 15.5 LUFS, minus 1.4 dBTP. Passed.

![Four stills from the cut with captions: the driver on the vineyard road with "Temecula Valley. Dozens of wineries. Balloons at sunrise."; the sommelier with the foam glass and "And, for the connoisseur, the Grand Cru Ceramic."; the tunnel exit with "Finished by hand. Now pouring in the Temecula Valley."; and the typed end card.](../../docs/images/13-grand-cru-cut-stills.jpg)

### Gate 04: Audit

[`audit.md`](audit.md): **stand-in verdict Revise, 5 of 7.** Continuity fails: the sommelier gains a fedora in shot 3 that the bible never gave him. Intent passes with a note: the generated car grilles carry badges that resemble real carmakers' logos, which must be blurred to honor the "no real businesses" exclusion. And nobody has signed.

## Run it yourself

The brief is in [`workshop-build/client-briefs/grand-cru-car-wash.md`](../../workshop-build/client-briefs/grand-cru-car-wash.md) and the bible in [`templates/grand-cru-car-wash-bible.json`](../../templates/grand-cru-car-wash-bible.json). The commands are the same as the workshop's, with two options added:

```bash
python3 pipelines/01-pre-production/run_breakdown.py --model glm-4.7-flash ...
python3 pipelines/02-production/comfyui_client.py \
    --workflow pipelines/02-production/workflows/flux2_klein_previs_reference.json \
    --lock-characters ...
```

## Files

| File or folder | Stage | What it is |
| --- | --- | --- |
| `research_log.csv` | Evidence | Three client facts and two public facts with source links. |
| `brief.agent-draft.json`, `brief.json`, `brief.md`, `brief_state.json` | Gate 01 | Agent draft, approved brief, gate record. |
| `shots.agent-draft.json`, `shots.json`, `shots_state.json` | Gate 02 | Agent draft, approved shot list, gate record. |
| `previs/` | Gate 02 | Grey renders, depth passes, `previs.blend`, `previs.json`. |
| `frames/` | Gate 03 | Approved keyframes, `frames.json`, `frames_state.json`, rejected and alternate takes. |
| `audio/` | Post | SCRATCH voiceover and its timing script. |
| `captions.whisper-raw.srt`, `captions.srt` | Post | Raw Whisper output and human-corrected captions. |
| `timeline.otio`, `cut.mp4`, `cut_softsubs.mp4`, `cut-preview.webp`, `poster.jpg` | Post | Timeline, two cuts, silent preview, still. |
| `qc.json`, `audit.md`, `provenance.csv` | Gate 04 | QC, unsigned audit, ledger including rejected takes. |
