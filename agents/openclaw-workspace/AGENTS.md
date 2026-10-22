# Registered Agents

This file tells a background agent (for example OpenClaw) which jobs it may run in this project and where it may read and write. Copy the whole `openclaw-workspace` folder into your agent's workspace, then edit the paths.

## Global rules

- Read the project bible before any task. Never edit it.
- Never delete files. Never overwrite a file that a human approved; write a new draft beside it.
- Never call cloud APIs. The only network targets are `127.0.0.1:11434` (Ollama) and `127.0.0.1:8188` (ComfyUI).
- Every draft stops at a gate with status `awaiting_review`. Only a human runs `pipelines/gate.py`.

## Agent: Brief Writer

- Job: draft `brief.json` and `brief.md` from a client brief and the director's three answers.
- Command: `python3 pipelines/01-pre-production/draft_brief.py`
- Card: `agents/brief_writer.yaml`
- May read: `workshop-build/client-briefs/`, `research_log.csv`
- May write: `brief.json`, `brief.md`, `brief_state.json`

## Agent: Shot Breakdown

- Job: split an approved brief into a shot list.
- Command: `python3 pipelines/01-pre-production/run_breakdown.py`
- Card: `agents/shot_breakdown.yaml`
- May read: `brief.json` (approved only), `bible.json`, `research_log.csv`
- May write: `shots.json`, `shots_state.json`; append to `provenance.csv`

## Agent: Pre-Auditor

- Job: measure the cut and pre-fill audit checks 2, 5 and 6.
- Commands: `python3 pipelines/03-post-production/qc_check.py`, then `pre_audit.py`
- Card: `agents/auditor.yaml`
- May write: `qc.json`, `audit.md`
- May never mark checks 1, 3, 4 or 7.
