# Agent Specifications

An agent in this kit is a small, boring, checkable thing. It has:

1. **One responsibility.** Exactly one job, such as "split a brief into shots".
2. **Declared tools.** What it may read and write, listed by folder.
3. **Negative constraints.** What it must never do: invent facts, add characters, delete files.
4. **A typed output.** JSON that must match a schema in `schemas/`.
5. **A gate.** The output waits with status `awaiting_review` until a human picks one of four exits: Approve, Revise, Reject or Request Evidence.

Each agent is described twice: once as a declarative card (the YAML files here) that a person can read in a minute, and once as the script that does the work. The card and the script must agree. If you change one, change the other.

## Agent cards

| Card | Crew | What it does | Script |
| --- | --- | --- | --- |
| `brief_writer.yaml` | Writer | Drafts `brief.json` and `brief.md`. The director's three answers and the exclusions are copied in word for word. | `pipelines/01-pre-production/draft_brief.py` |
| `shot_breakdown.yaml` | Writer | Turns an approved brief into `shots.json`, then runs four checks with no model involved. Failed checks go back to the model, up to three attempts. | `pipelines/01-pre-production/run_breakdown.py` |
| `auditor.yaml` | Auditor | Not a language model. Measures the cut and pre-fills audit checks 2, 5 and 6. It can never mark checks 1, 3, 4 or 7. | `pipelines/03-post-production/qc_check.py` and `pre_audit.py` |

## Why the checks are not done by a model

If a question has one right answer, such as "does every character id in this file exist in the bible?", a script answers it every time, in milliseconds, for free. Asking a model would add cost and a chance of being wrong. This is "script the chores, craft the film" applied to the agent itself.

## What the demo showed

In `examples/ember-and-oak-demo/` the shot-breakdown agent passed all four machine checks on its first attempt, and the director still sent it back: it had dressed the roaster in "a reclaimed oak apron" (the oak is the counter). Machine checks catch structure. Only a person catches meaning. See [the demo write-up](../examples/ember-and-oak-demo/README.md).

## Background agents (optional)

[`openclaw-workspace/`](openclaw-workspace/README.md) holds plain-text instruction files for an always-on agent such as OpenClaw: registered agents, studio voice, periodic checks and approved decisions.
