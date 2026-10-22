# Examples

| Item | What it is |
| --- | --- |
| [`ember-and-oak-demo/`](ember-and-oak-demo/README.md) | One complete run of the workshop build, with every file it produced: briefs, shot lists, previs, keyframes (including rejected takes), captions, timeline, two cuts, QC and the audit. Read its README for what broke at each gate and how it was caught. |
| `run_demo.sh` | Reruns the same build into a new folder and stops at every gate for you to choose Approve, Revise, Reject or Request Evidence. |

## Run the demo yourself

```bash
bash examples/run_demo.sh            # writes to demo-run/ (ignored by Git)
```

It needs Ollama with `llama3.2:3b`, Python and ffmpeg. Blender, ComfyUI, Whisper and Piper are used if present; the script tells you what it skipped. Your results will differ from the committed example, because local models are repeatable but not byte-identical between runs.
