# Worked Example: Agentic Workflows Summit Pitch

A complete promotional spot pitching the **Tuesday Cinema Club + XPSR Creator Summit: Agentic Workflows — Zero Cost, Infinite Potential** (10/24/26). Featuring the lead instructor using reference-conditioned keyframe rendering with FLUX.2 [klein] 4B and local Piper TTS.

![Animated preview: the instructor smiling in a warm studio edit suite; a cinema monitor with node trees and depth map previs; the instructor holding a film slate in front of an arthouse projector beam; end card "AGENTIC WORKFLOWS: ZERO COST, INFINITE POTENTIAL | Tuesday Cinema Club + XPSR Summit".](cut-preview.webp)

[Watch the full 30-second cut with sound (MP4)](cut.mp4) • [Watch with closed captions](cut_softsubs.mp4)

---

## The Pitch

This 30-second spot addresses indie filmmakers and creators directly: stop burning subscriptions on cloud slot machines that hallucinate random characters and camera angles. Instead, run an open-source, local-first pipeline where every agent has one job and a human director approves every gate before a single frame is animated.

## Pipeline Walkthrough

### Gate 01: Brief
* **Client:** Tuesday Cinema Club + XPSR Summit
* **Audience:** Indie filmmakers and animators
* **Exclusions:** Zero cloud vendor shilling, no ungrounded AI hype, no unverified claims.
* **Document:** [`brief.json`](brief.json)

### Gate 02: Shot List
* Three balanced shots:
  1. **Shot 01 (Medium, 50mm, 9s, Push In):** Instructor invites creators into the edit suite: *"Stop rolling the dice on cloud prompts. You do not need a hundred dollar subscription to direct AI cinema."*
  2. **Shot 02 (Close-up, 85mm, 9s, Pan Right):** Cinema monitor showing 3D wireframe previs and depth node trees: *"Every agent has one job. Every gate is approved by you. We script the chores, but you craft the film."*
  3. **Shot 03 (Wide, 35mm, 12s, Push In):** Instructor with vintage film slate in projector beam: *"Take back your cut, your voice, and your vision. Zero cost, infinite potential. Welcome to the Tuesday Cinema Club."*
* **Document:** [`shots.json`](shots.json)

### Gate 03: Keyframes
* **Model:** FLUX.2 [klein] 4B + Qwen3 4B text encoder via ComfyUI.
* **Reference Conditioning:** Conditioned on the instructor reference photo (`instructor_reference.jpg`) using `ReferenceLatent` to maintain character facial structure, beard, long wavy hair, and styling across takes.
* **Files:** [`frames/`](frames/)

### Post-Production
* **Voiceover:** Generated with Piper local TTS using the expressive male model `en_US-bryce-medium` (`audio/vo_scratch.wav`).
* **Captions:** Transcribed with local offline Whisper (`captions.srt`).
* **Timeline:** Standard OpenTimelineIO exchange file for Kdenlive (`timeline.otio`).
* **Technical QC:** 1920x1080 @ 24fps, exactly 30.00s, -15.5 LUFS loudness, -1.3 dBTP peak. Passed every check (`qc.json`).

### Gate 04: Anti-Slop Audit
* Pre-filled with `pre_audit.py` and reviewed: [`audit.md`](audit.md) (Score: 6 of 7, ready for director signature).
