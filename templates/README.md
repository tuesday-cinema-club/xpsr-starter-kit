# Project Templates

Starting points for your own project. Copy a file, rename it, and edit it by hand. Agents read these files; only humans change them.

## Files in this folder

| File | What it is | Checked by |
| --- | --- | --- |
| `ember-and-oak-bible.json` | Project bible for the Ember & Oak Coffee brief: characters, locations, palette, lighting, exclusions. | `schemas/bible.schema.json` |
| `spoke-coop-bible.json` | Project bible for the Spoke Co-op brief. | `schemas/bible.schema.json` |
| `research_log.csv` | Empty evidence log. Every factual claim in a script or shot list needs a row here. | Read by `pipelines/01-pre-production/run_breakdown.py` |

## What goes in a project bible

A bible is the single source of truth for continuity. It has five parts:

1. **Characters.** Each has an `id` (lowercase, used by agents), a `name`, and a `visual_lock`: a fixed description of age range, hair, wardrobe and props that every frame must match. Set `consent_on_file` to `true` only if you are using a real person's face or voice and have their written consent.
2. **Locations.** Each has an `id`, a `name` and a short physical `description`.
3. **Visual rules.** Palette as hex colors (with plain-language `palette_names` so the palette is readable without seeing color), lighting key, aspect ratio, frame rate, and the `style_prompt` and `negative_prompt` appended to every image generation.
4. **Exclusions.** Things this project will never show or say.
5. **Project id and title.**

## Make your own

```bash
cp templates/ember-and-oak-bible.json my-project/bible.json
# edit my-project/bible.json in any text editor, then check it:
python3 schemas/validate.py bible my-project/bible.json
```

## Research log columns

| Column | Meaning |
| --- | --- |
| `source_id` | Short id such as `SRC-001`. Shot lists cite these ids. |
| `claim` | The fact, in one sentence. |
| `source` | Where it came from: client email, interview, public record, and so on. |
| `verified_by` | The person who checked it. |
| `verified_on` | Date checked, `YYYY-MM-DD`. |

A claim with no row here fails check 2 (Evidence) of the anti-slop audit.
