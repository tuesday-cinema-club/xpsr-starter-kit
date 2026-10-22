# Agentic Workflows: Zero Cost, Infinite Potential

Tuesday Cinema Club + XPSR Creator Summit, 10/24/26. Participant guide.

Local-first creative AI pipelines, without the slop.

## 1. Welcome

In Part 1 (11:15 to 12:15) we learn to build creative pipelines with free, local, open-source AI. In Part 2 (after lunch) we build one together.

You don't need to code, and a phone is enough to take part. Look for **Phone OK** (📱) to find the steps you can do on a phone.

## 2. Before you arrive

- [ ] Sign up: forms.gle/CPfiNBCuZzs4QEXJ8 (Phone OK)
- [ ] Bookmark the starter kit (briefs, templates, agent script): github.com/tuesdaycinemaclub (Phone OK)
- [ ] Set up your device with the table below. Only do your row.

### Setup by device

| Device | What to do |
| --- | --- |
| Phone (Phone OK) | Nothing to install. Free up 2 GB of space. Test the camera and voice memos. Bookmark the starter kit. Bring a charger. |
| Laptop (8 to 16 GB RAM, about 10 GB free disk) | Ollama, then download the model (command 1 below). Blender (3D blocking). Kdenlive (video editing). GIMP (image editing). Git, then copy the starter kit (command 2). Optional: ArtCraft and Whisper. Check it works (command 3). |
| Laptop with GPU (8 GB or more VRAM, about 40 GB free disk) | Everything in the laptop row, plus: ComfyUI. One image model: SDXL or FLUX.2 [klein] 4B (Apache 2.0), both on Hugging Face. Optional motion model: Wan 2.2 5B. Render one test frame in ComfyUI. |

### Laptop commands

Open Terminal (Mac) or PowerShell (Windows), paste one line, then press Enter.

1. Download the writing model (about 2 GB):

   ```bash
   ollama pull llama3.2:3b
   ```

2. Copy the starter kit to your laptop:

   ```bash
   git clone https://github.com/tuesdaycinemaclub/starter-kit
   ```

3. Test it. If the model replies, you're ready:

   ```bash
   ollama run llama3.2:3b "hi"
   ```

> **Warning: always check each model's license.** "Free," "open-source," "open-weight" and "local" mean different things. Free costs nothing today. Open-source means you can read the code, with rules set by the license. Open-weight means you can download the model, but the terms vary. Local means it runs on your machine. Before you use a model for paid work, check whether its license allows commercial use.

## 3. Part 1 in one page

| Idea | What it means |
| --- | --- |
| Snake vs. charmer | Stop rerolling and start directing. Cloud prompting works like a slot machine. A local pipeline gives you repeatable results that you control. |
| One agent, one job | Each agent does one job, with a limited set of tools and a defined output (for example, a shot list held for approval). |
| Script the chores, craft the film | If a task has one right answer, like renaming files or exporting captions, script it. If it needs taste, a human does it. |
| Humans approve every gate | At each gate you approve, revise, reject or ask for evidence. Approved work is saved to Git before the next stage. |
| Three pipelines | Pre-production (research, brief, shot list), then Production (frames and assets), then Post-production (cut, captions, QC). |
| Two-pass motion | Lock a still frame first, then animate only the frames you approved. You get less warping and less face drift. |
| 7-point anti-slop audit | 1 Intent, 2 Evidence, 3 Continuity, 4 Specificity, 5 Technical QC, 6 Provenance, 7 Human signature (non-negotiable). |
| The $0 principle | Replace an $840-a-year Adobe plan: Photoshop with GIMP, Firefly with ArtCraft or ComfyUI, After Effects 3D with Blender, Premiere with Kdenlive, Audition with Ardour. |

## 4. Over lunch (10 minutes)

| Device | Get ready for Part 2 |
| --- | --- |
| Phone (Phone OK) | Scan the QR code. Open the starter kit. Read the two client briefs. |
| Laptop | Download the model (`ollama pull llama3.2:3b`). Open Blender and Kdenlive once. Copy the starter kit. |
| GPU laptop | Launch ComfyUI. Render one test frame. |

Stuck? Pair up with someone. A phone gets you a full seat at the table.

## 5. Part 2: The Build (60 minutes)

Goal: one 30-second launch spot for one brand, made locally for $0.

Deliverables:

- [ ] `brief.md`: one page covering intent, audience and exclusions
- [ ] 3 previs shots, blocked in 3D and approved by the director
- [ ] A 30-second cut
- [ ] `audit.md`: scored on the 7 anti-slop checks
- [ ] `provenance.csv`: one row for every asset

### Kickoff (6 min)

Vote on a client (Phone OK):

- **Ember & Oak Coffee:** a roaster opening a second shop
- **Spoke Co-op:** a bike-repair co-op recruiting members
- **Your pitch:** a real brand or idea from someone in the room

Form the crews:

| Crew | Job | Device |
| --- | --- | --- |
| Director | Owns the brief and approves each gate | Phone OK |
| Writer | Drafts the brief and shot list with Ollama | Laptop |
| Previs | Blocks shots in Blender or ArtCraft and can film the camera move on a phone | Laptop or phone |
| Frames | Renders keyframes in ComfyUI | GPU laptop |
| Edit & Sound | Cuts in Kdenlive, adds Whisper captions and records the voiceover | Laptop and phone |
| Auditor | Scores the result on the anti-slop checklist | Phone OK |

### Gate 01: Brief (9 min)

1. The director answers three questions: who is it for, what should they feel, and what should they do next?
2. The Writer crew drafts `brief.md` with Ollama.
3. The room adds three exclusions: things this spot will never do.
4. The director approves, then the crew commits the brief to Git.

Phone OK: suggest exclusions and vote.

### Gate 02: Previs (13 min)

1. The agent writes `shots.json`: 3 shots, each with a lens, framing and length.
2. The Previs crew blocks the shots in 3D (grey boxes are fine) and exports depth passes.
3. The director approves the framing.

Phone OK: film the camera move.

### Gate 03: Produce (19 min)

The flow: shot list (Ollama), then depth (Blender), then keyframes (ComfyUI), then motion (Wan 2.2 5B, optional), then captions (Whisper), then the cut (Kdenlive).

The $0 rules:

- [ ] No cloud calls and no API keys
- [ ] Check the license of every model, checkpoint and plugin
- [ ] Log every asset in `provenance.csv`
- [ ] The director approves keyframes before any motion

No GPU? Cut the keyframes together as an animatic.

Phone OK: record the voiceover.

### Gate 04: Present (13 min)

1. Play the cut.
2. Each crew gets 1 minute to say what the agent did, what broke, how they caught it and where a human made it better.
3. The Auditor scores the 7 checks out loud. (Phone OK)
4. The director signs off.

## 6. After the workshop

This week, copy the starter kit, swap in your own brand and run the pipeline again.

```bash
git clone https://github.com/tuesdaycinemaclub/starter-kit
```

### Keep going: the six-session series

| Number | Session |
| --- | --- |
| 1 | Local studio |
| 2 | Pre-production agents |
| 3 | Media pipelines |
| 4 | Agentic workflows (today) |
| 5 | Post and QC |
| 6 | Capstone |

## 7. Troubleshooting FAQ

| Problem | Quick fix |
| --- | --- |
| Ollama is slow | Use the 3B model (`llama3.2:3b`) and close other apps. |
| I don't have a GPU | Join the Writer, Edit or Auditor crew. Every stage except Frames and Motion runs on an ordinary laptop. |
| My work laptop blocks installs | Use your phone or pair up with someone. |
| I'm out of disk space | Keep one image model, not several. Remove models you don't need (commands below). Store large models on an external drive. |
| Ethics | Get written consent before using any real person's face or voice. Tell your audience where you used AI. Keep provenance for every asset. |

Free up disk space: list your models, then remove the ones you don't need.

```bash
ollama list
ollama rm <model-name>
```

Not signed up yet? forms.gle/CPfiNBCuZzs4QEXJ8 (Phone OK)
