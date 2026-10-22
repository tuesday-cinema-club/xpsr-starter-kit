# Workshop Build: 60 Minutes, One 30-Second Spot, $0

Part 2 of the summit. Goal: one 30-second launch spot for one brand, made locally for $0.

## Deliverables

- `brief.md`: one page covering intent, audience and exclusions.
- Three previs shots, blocked in 3D and approved by the director.
- A 30-second cut.
- `audit.md`: scored on the seven anti-slop checks.
- `provenance.csv`: one row for every asset.

## Schedule and gates

| Gate | Time | What happens | Deliverable | Exit |
| --- | --- | --- | --- | --- |
| 00 Kickoff | 6 min | Vote on a client and form the crews. | Chosen brief | Every crew has people |
| 01 Brief | 9 min | Director answers three questions; Writer drafts `brief.md` with Ollama; the room adds three exclusions. | `brief.md` | Director approves; crew commits to Git |
| 02 Previs | 13 min | Agent writes `shots.json` (3 shots, each with lens, framing and length); Previs blocks them in 3D and exports depth passes. | `shots.json`, depth passes | Director approves framing |
| 03 Produce | 19 min | Shot list, then depth, keyframes, optional motion, captions, cut. | `frames/`, `captions.srt`, cut | Director approves keyframes before any motion |
| 04 Present | 13 min | Play the cut. Each crew gets 1 minute. Auditor scores the 7 checks aloud. | `audit.md`, `provenance.csv` | Director signs off |

Total: 60 minutes.

## Choose a client

| Option | Brief | Bible |
| --- | --- | --- |
| Ember & Oak Coffee: a roaster opening a second shop | [`client-briefs/ember-and-oak.md`](client-briefs/ember-and-oak.md) | `templates/ember-and-oak-bible.json` |
| Spoke Co-op: a bike-repair co-op recruiting members | [`client-briefs/spoke-coop.md`](client-briefs/spoke-coop.md) | `templates/spoke-coop-bible.json` |
| Grand Cru Car Wash (ironic): a car wash that talks like a Temecula Valley tasting room | [`client-briefs/grand-cru-car-wash.md`](client-briefs/grand-cru-car-wash.md) | `templates/grand-cru-car-wash-bible.json` |
| Your pitch: a real brand or idea from someone in the room | Copy [`templates/brief_template.md`](templates/brief_template.md) | Copy a bible from `templates/` and edit it |

All three clients are fictional businesses written for practice. The car wash brief uses two real, sourced facts about the Temecula Valley.

## Crews

| Crew | Job | Device |
| --- | --- | --- |
| Director | Owns the brief and approves each gate. | Phone OK |
| Writer | Drafts the brief and shot list with Ollama. | Laptop |
| Previs | Blocks shots in Blender or ArtCraft; can film the camera move on a phone. | Laptop or phone |
| Frames | Renders keyframes in ComfyUI. | GPU laptop |
| Edit & Sound | Cuts in Kdenlive, adds Whisper captions, records the voiceover. | Laptop and phone |
| Auditor | Scores the result on the anti-slop checklist. | Phone OK |

## Commands for each gate

Set up a project folder first:

```bash
mkdir -p my-project
cp templates/ember-and-oak-bible.json my-project/bible.json
cp examples/ember-and-oak-demo/research_log.csv my-project/research_log.csv
cp workshop-build/templates/provenance.csv my-project/provenance.csv
```

| Gate | Crew | Command (details in each pipeline README) |
| --- | --- | --- |
| 01 | Writer | `python3 pipelines/01-pre-production/draft_brief.py --client-brief ... --who ... --feel ... --do ... --exclusion ... (x3) --out-dir my-project` |
| 02 | Writer | `python3 pipelines/01-pre-production/run_breakdown.py --brief my-project/brief.json --bible my-project/bible.json --research-log my-project/research_log.csv --out my-project/shots.json` |
| 02 | Previs | `blender -b -P pipelines/02-production/blender_previs.py -- --shots my-project/shots.json --bible my-project/bible.json --out my-project/previs` |
| 03 | Frames | `python3 pipelines/02-production/comfyui_client.py --shots my-project/shots.json --bible my-project/bible.json --previs my-project/previs --out my-project/frames` |
| 03 | Edit & Sound | `transcribe.py`, then `assemble_animatic.py` or `generate_timeline.py` for Kdenlive |
| 04 | Auditor | `qc_check.py`, then `pre_audit.py`; score checks 1, 3, 4 aloud |
| Every gate | Director | `python3 pipelines/gate.py --state <state file> --decision Approve --by "<name>"` |

## The $0 rules

- No cloud calls and no API keys.
- Check the license of every model, checkpoint and plugin.
- Log every asset in `provenance.csv`.
- The director approves keyframes before any motion.
- No GPU? Cut the keyframes together as an animatic.

## Gate 04 debrief: one minute per crew

Say what the agent did, what broke, how you caught it, and where a human made it better.

## Files in this folder

| File | Use |
| --- | --- |
| `client-briefs/ember-and-oak.md` | Client A, with a fact sheet you may cite. |
| `client-briefs/spoke-coop.md` | Client B, with a fact sheet you may cite. |
| `client-briefs/grand-cru-car-wash.md` | Client C, an ironic brief, with a fact sheet you may cite. |
| `templates/brief_template.md` | Blank brief for writing by hand or your own pitch. |
| `templates/provenance.csv` | Empty provenance ledger (header row only). |
| `templates/audit_template.md` | Blank audit sheet for the Auditor. |
| `review/anti_slop_rubric.md` | The seven checks, with what pass and fail look like. |

## Provenance columns

| Column | Meaning |
| --- | --- |
| `asset_id` | File or asset name, such as `shot_01_keyframe`. |
| `timestamp` | When it was made, in UTC. |
| `stage` | `shot_list`, `keyframe`, `paint_over`, `temporal`, `dialogue`, `captions` or `edit`. |
| `tool_or_model` | What made it, such as `ComfyUI/sd_xl_base_1.0.safetensors` or `iPhone voice memo`. |
| `checkpoint_hash` | Short SHA-256 of the model file, or `N/A`. |
| `seed` | Seed used, or `N/A`. |
| `prompt_or_input` | The prompt or source file. |
| `human_approver` | Who approved or rejected it. |
| `status` | `PENDING_REVIEW`, `APPROVED`, `REVISE`, `REJECTED` or `EVIDENCE_REQUESTED`. |
