# Agentic Workflows: Zero Cost, Infinite Potential

Local-first creative AI pipelines for film and video, without the slop.

This is the starter kit for the **Tuesday Cinema Club + XPSR Creator Summit** (10/24/26): the briefs, templates, schemas, agent specs and runnable scripts for building a 30-second spot with free, local, open-source tools, with a human approving every step.

You don't need to code, and a phone is enough to take part.

![Four stills from the 30-second demo spot made with this kit: a roaster beside a drum roaster, a hand at an open bag of beans, two people at a shop counter, and a typed end card reading "Ember & Oak, Second shop now open". Each has a readable caption.](docs/images/10-final-cut-stills.jpg)

## Start here

| If you are | Go to |
| --- | --- |
| Attending the summit | [The participant guide](docs/participant-guide.md) |
| Setting up a laptop | [Environment setup](environment/README.md) |
| Running the 60-minute build | [Workshop build](workshop-build/README.md) |
| Curious what the output looks like | [The worked example](examples/ember-and-oak-demo/README.md) |
| Using a screen reader | [Accessibility notes](ACCESSIBILITY.md) |

## Quickstart

### Phone

Nothing to install. Open this page, read the [two client briefs](workshop-build/client-briefs/), and join the Director or Auditor crew.

### Laptop (8 to 16 GB RAM)

1. Install Ollama from https://ollama.com/download, then download the writing model (about 2 GB):

   ```bash
   ollama pull llama3.2:3b
   ```

2. Copy the starter kit:

   ```bash
   git clone https://github.com/tuesday-cinema-club/xpsr-starter-kit
   cd xpsr-starter-kit
   ```

3. Test it. If the model replies, you're ready:

   ```bash
   ollama run llama3.2:3b "hi"
   ```

4. Check the rest of your setup and get a crew suggestion:

   ```bash
   python3 environment/check_setup.py
   ```

### Laptop with a GPU (8 GB or more VRAM)

Everything above, plus ComfyUI and one image model. See [the ComfyUI section of the setup guide](environment/README.md#laptop-with-gpu-8-gb-or-more-vram-about-40-gb-free).

## The ideas

1. **Snake versus charmer.** Stop rerolling and start directing. Cloud prompting works like a slot machine. A local pipeline gives you repeatable results that you control.
2. **One agent, one job.** Each agent does one job, with a limited set of tools and a defined output, such as a shot list held for approval.
3. **Script the chores, craft the film.** If a task has one right answer, like checking a file against a schema or measuring loudness, script it. If it needs taste, a human does it.
4. **Humans approve every gate.** At each gate you approve, revise, reject or ask for evidence. Approved work is saved to Git before the next stage.
5. **Two-pass motion.** Lock a still frame first, then animate only the frames you approved.
6. **The 7-point anti-slop audit.** Intent, Evidence, Continuity, Specificity, Technical QC, Provenance, and a Human signature, which is non-negotiable.

## How a project moves through the kit

1. **Brief.** The director answers three questions. A local model drafts `brief.md`. The room adds three exclusions. Gate 01.
2. **Shot list.** An agent writes `shots.json`. A script checks it against the schema, the project bible and the research log. Gate 02.
3. **Previs.** Blender blocks each shot in grey boxes with its real lens and renders a depth pass.
4. **Keyframes.** ComfyUI paints each shot inside its depth pass. Gate 03: the director approves frames before any motion.
5. **Post.** Voiceover, Whisper captions, an OpenTimelineIO timeline for Kdenlive, an animatic cut, and technical QC.
6. **Audit.** Scripts pre-fill the checks a machine can verify. People score the rest. The director signs. Gate 04.

## What is in this repository

| Folder | What it holds |
| --- | --- |
| [`docs/`](docs/README.md) | The participant guide, the Part 1 talk outline, the six-session series, and all screenshots. |
| [`environment/`](environment/README.md) | Setup by device, setup scripts for macOS, Linux and Windows, a read-only setup checker, and the hardware matrix with tested timings and model licenses. |
| [`schemas/`](schemas/README.md) | JSON Schema contracts for the brief, the project bible, the shot list and gate state, plus a validator. |
| [`agents/`](agents/README.md) | Declarative agent cards and optional OpenClaw workspace files. |
| [`pipelines/`](pipelines/README.md) | The runnable scripts for pre-production, production and post-production, and the gate tool. |
| [`workshop-build/`](workshop-build/README.md) | The 60-minute build: client briefs, schedule, crews, templates, and the anti-slop rubric. |
| [`templates/`](templates/README.md) | Project bibles for both clients and an empty research log. |
| [`examples/`](examples/README.md) | A complete worked run, mistakes included, and a script to rerun it yourself. |
| [`tools/`](tools/README.md) | The screenshot helper used for the docs. |

## The worked example

Everything in [`examples/ember-and-oak-demo/`](examples/ember-and-oak-demo/README.md) was produced by this kit on one machine with an 8 GB GPU, with no cloud calls. It is honest about what went wrong:

- The brief agent credited Man with a Movie Camera to the wrong filmmaker. Caught at Gate 01.
- The shot agent passed every machine check and still dressed the roaster in "a reclaimed oak apron". Caught at Gate 02.
- The first keyframes had a missing person, a missing hand and a garbled sign. Caught at Gate 03, with every rejected take kept on record.
- Whisper heard "shop" as "shot". Caught by a person reading the captions.
- The final audit scores **5 of 7**: continuity fails and the cut is not signed. That is the audit doing its job.

![Two rows of keyframes. Top row, rejected take 1: an apron where the roaster should be, a bag label with no hand, an outdoor kiosk with a garbled sign. Bottom row, approved frames: the roaster beside the drum roaster, a hand at an open bag of beans, two people at an indoor counter.](docs/images/08-keyframes-rejected-vs-approved.jpg)

## The $0 principle

The kit replaces an $840-a-year Adobe plan with free tools that run on your machine:

| Instead of | Use |
| --- | --- |
| Photoshop | GIMP |
| Firefly | ArtCraft or ComfyUI |
| After Effects (3D and camera) | Blender |
| Premiere Pro | Kdenlive |
| Audition | Ardour or Audacity |
| Cloud chat subscriptions | Ollama with a local model |

"Free," "open-source," "open-weight" and "local" mean different things. Check each model's license before you use it for paid work. The [hardware matrix](environment/hardware-matrix.md#model-licenses) lists the licenses for every model used here.

## Requirements

- **Required:** Python 3.9 or newer, Git, Ollama. The core scripts use only the Python standard library.
- **By crew:** Blender (Previs), ffmpeg (Edit, QC), ComfyUI and a GPU (Frames), Whisper (captions), Kdenlive and GIMP (finishing).
- **Optional Python helpers:** `pip install -r requirements.txt` (jsonschema, OpenTimelineIO, Piper text-to-speech). The setup scripts install these into `.venv`.

## Ethics

Get written consent before using any real person's face or voice. Tell your audience where you used AI. Keep provenance for every asset.

## License

Code and documentation are released under the [MIT License](LICENSE). Models you download have their own licenses; the MIT license does not cover them.
