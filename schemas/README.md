# Schemas: the Contracts Between Stages

A pipeline only stays deterministic if every hand-off has a fixed shape. These JSON Schema files (draft 2020-12) are those shapes. An agent's output must match its schema before a human ever sees it, and a model is never allowed to pass free-form chat into the next stage.

The schemas are used in two places:

1. **While generating.** The agent scripts pass the schema to Ollama as its `format`, so the model can only produce JSON of that shape.
2. **After generating.** The same schema is checked again, with no model involved, by `validate.py` and by every agent script.

## The four contracts

| Schema | Written by | Read by | Key rules |
| --- | --- | --- | --- |
| `brief.schema.json` | Brief writer (Gate 01) | Shot breakdown | Director's three answers (`target_audience`, `core_feeling`, `call_to_action`), `key_message`, `runtime_sec`, and **at least three** `exclusions`. |
| `bible.schema.json` | Humans only | Every stage | Characters with a fixed `visual_lock` and a `consent_on_file` flag, locations, palette as hex with plain-language names, lighting key, aspect ratio, frame rate, style and negative prompts, exclusions. |
| `shot_breakdown.schema.json` | Shot breakdown (Gate 02) | Previs, Frames, Edit | Per shot: framing (one of five), lens 12 to 200 mm, duration, camera move (one of eight), `location_id`, character ids, prompt, voiceover line, `source_ids`, `claims_sourced`. |
| `state.schema.json` | Every agent, then `gate.py` | Humans, `gate.py` | Stage, status, check results, the decision (`Approve`, `Revise`, `Reject`, `Request Evidence` or empty), who decided, when, and the full history. |

## Check a file

```bash
python3 schemas/validate.py brief          examples/ember-and-oak-demo/brief.json
python3 schemas/validate.py bible          templates/ember-and-oak-bible.json
python3 schemas/validate.py shot_breakdown examples/ember-and-oak-demo/shots.json
python3 schemas/validate.py state          examples/ember-and-oak-demo/shots_state.json
```

A pass prints `[pass] ... matches ...`. A fail lists every problem by field and exits with code 1, so you can use it in scripts.

`validate.py` needs no extra packages. If the `jsonschema` package is installed (the setup script puts it in `.venv`) it is used; otherwise a small built-in validator handles the keywords these schemas use.

## What a schema cannot check

A schema checks shape, not meaning. In the demo, the shot list was valid and every id existed in the bible, yet one shot dressed the roaster in "a reclaimed oak apron". The `bible_match` check in `run_breakdown.py` goes one step further (ids must exist), and the director's eye does the rest.

## Changing a schema

Schemas are contracts, so change them on purpose:

1. Edit the schema.
2. Update the agent card in `agents/` and the script that writes the file.
3. Run `validate.py` on the demo files to see what broke.
4. Commit the schema change on its own, with a message that says why.
