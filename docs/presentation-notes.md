# Part 1 Talk Outline: Agentic Workflows

Tuesday Cinema Club + XPSR Creator Summit, 10/24/26, 11:15 to 12:15.

> **Status:** this outline is built from the participant guide and the ideas in this repository. The slide deck itself is not in the repo yet. Add speaker notes under each section, or place an exported PDF of the deck in this folder and link it here.

Each section lists the idea, what to show live from this repository, and the handout line it matches.

## 1. Why we make things

- **Idea:** Kurt Vonnegut, in a 2006 letter to high-school students: practice any art "not to get money and fame, but to experience becoming, to find out what's inside you, to make your soul grow." Tools should clear away chores so there is more time for that, not replace it.
- **Show:** nothing yet. Let the quote land.

## 2. Snake versus charmer

- **Idea:** cloud prompting works like a slot machine: pull, reroll, pay, repeat. A charmer builds a local pipeline with fixed seeds, schemas and gates, and gets results they can repeat and control.
- **Show:** `docs/images/02-ollama-hi.png`, a model answering on localhost with no account and no meter running.
- **Handout:** "Stop rerolling and start directing."

## 3. The $0 principle

- **Idea:** replace an $840-a-year Adobe plan. Photoshop with GIMP, Firefly with ArtCraft or ComfyUI, After Effects 3D with Blender, Premiere with Kdenlive, Audition with Ardour.
- **Caveat to say aloud:** free, open-source, open-weight and local are four different things. Check every license before paid work. See `environment/hardware-matrix.md`.

## 4. One agent, one job

- **Idea:** an agent has one responsibility, declared tools, things it must never do, a typed output, and a gate.
- **Show:** `agents/shot_breakdown.yaml` beside `schemas/shot_breakdown.schema.json`.

## 5. Script the chores, craft the film

- **Idea:** one right answer means script it (schema checks, loudness, file naming, captions export). Taste means a human does it (framing, performance, the final cut).
- **Show:** `pipelines/03-post-production/qc_check.py` output in `docs/images/11-animatic-qc-audit.png`.

## 6. Humans approve every gate

- **Idea:** four exits only: Approve, Revise, Reject, Request Evidence. Approved work goes into Git before the next stage.
- **Show:** `docs/images/04-gate-02.png`. The agent's shot list passed every machine check and the director still sent it back: the roaster was wearing "a reclaimed oak apron".

## 7. Three pipelines

- **Idea:** pre-production (research, brief, shot list), production (frames and assets), post-production (cut, captions, QC).
- **Show:** `pipelines/README.md`, the seven-step flow.

## 8. Two-pass motion

- **Idea:** lock a still first, then animate only approved frames. Less warping, less face drift.
- **Show:** `docs/images/05-blender-previs.jpg` (grey box and depth) next to `docs/images/08-keyframes-rejected-vs-approved.jpg` (what the model painted inside it).

## 9. The 7-point anti-slop audit

- **Idea:** Intent, Evidence, Continuity, Specificity, Technical QC, Provenance, Human signature. Check 7 is non-negotiable.
- **Show:** `examples/ember-and-oak-demo/audit.md`. Be honest: the demo cut does not pass continuity yet, and that is the point of the audit.

## 10. Set up Part 2

- **Idea:** one 30-second spot, 60 minutes, $0, six crews, four gates. A phone is a full seat at the table.
- **Show:** `workshop-build/README.md`, the schedule table.
