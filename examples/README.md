# Examples

Three complete runs, every file kept, mistakes included. Each README says what broke at each gate and how it was caught.

| Example | Models | Stand-in audit | What it shows |
| --- | --- | --- | --- |
| [`ember-and-oak-demo/`](ember-and-oak-demo/README.md) | `llama3.2:3b`, SDXL + depth ControlNet (the workshop stack) | Revise, 5 of 7 | The full workshop build on laptop-sized models: briefs, shot lists, previs, rejected takes, captions, timeline, two cuts, QC and the audit. |
| [`ember-and-oak-overpowered/`](ember-and-oak-overpowered/README.md) | `glm-4.7-flash`, FLUX.2 [klein] 4B | Revise, 6 of 7 | The same job with bigger models: timings, side-by-side frames, and what extra compute does and does not fix. |
| [`grand-cru-car-wash/`](grand-cru-car-wash/README.md) | `glm-4.7-flash`, FLUX.2 [klein] 4B | Revise, 5 of 7 | A new, ironic brief: a car wash that talks like a Temecula Valley tasting room. |
| `run_demo.sh` | Workshop stack | | Reruns the Ember & Oak build into a new folder and stops at every gate for you to decide. |

## Watch them

Each folder has a silent animated preview (`cut-preview.webp`), the full cut with sound and burned-in captions (`cut.mp4`), and the same cut with a selectable caption track (`cut_softsubs.mp4`).

## Run the demo yourself

```bash
bash examples/run_demo.sh            # writes to demo-run/ (ignored by Git)
```

It needs Ollama with `llama3.2:3b`, Python and ffmpeg. Blender, ComfyUI, Whisper and Piper are used if present; the script tells you what it skipped. Your results will differ from the committed example, because local models are repeatable but not byte-identical between runs.
