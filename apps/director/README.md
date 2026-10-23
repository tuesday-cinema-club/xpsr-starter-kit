# XPSR Director

The workshop on a phone. Four gates, the same ones the kit's scripts use, each signed by a named person before the next one opens:

1. **The brief.** The director's three answers, the key message and three exclusions.
2. **Previs.** A shot deck with lens, framing, move and timing. A phone photo or video of the blocking becomes each shot's layout reference.
3. **Production.** For every shot: a first frame, an optional last frame drawn from the first, then an action prompt that animates between them.
4. **The audit.** The seven anti-slop checks, with a human signature that the release depends on.

The **Pack** button bundles everything into the files the kit reads: `brief.md`, `brief.json`, `research_log.csv`, `shots.json`, `provenance.csv`, `audit.md`, and the picked frames and clips. `brief.json` and `shots.json` pass `schemas/validate.py`.

It is a small Python server (standard library only) and a web app with no build step and no outside scripts. It runs on the machine with the GPU; phones open it over the network.

![XPSR Director on a phone: the sticky header with GPU and Flow status lights and the Pack button, a row of crew roles with Director selected, the Gate 01 slate reading The Brief, and the client picker with Ember and Oak Coffee chosen.](../../docs/images/director/01-brief.png)

## What runs where

| Step | Engine | Where | Cost |
| --- | --- | --- | --- |
| Drafting the brief, shots, action prompts; reading shots against exclusions | Ollama (`llama3.2:3b` by default, any pulled model) | This machine's GPU | Free |
| First and last frames | FLUX.2 [klein] 4B through ComfyUI | This machine's GPU | Free, unlimited: about 30 to 40 seconds a frame on an 8 GB RTX 2070 SUPER |
| First and last frames, instead | Google Flow images (Nano Banana) through useapi.net | Google | 0 Flow credits; one captcha solve each |
| First and last frames, instead | A phone photo | The phone | Free |
| Motion: first frame, last frame and action in, a clip out | Google Flow video (Veo 3.1, Omni 1.1 Flash) through useapi.net | Google | Flow credits, inside a daily budget |

The local model only drafts. Every suggestion lands in a box with a **Use** button, and nothing is in the brief until a person presses it.

## Start it

Python 3.10 or newer, plus Ollama and ComfyUI for the GPU steps (see [environment setup](../../environment/README.md)).

```bash
python3 apps/director/server.py
```

It listens on `http://127.0.0.1:8790`. On first start it makes an access code and saves it, with mode 600, in `~/.config/xpsr-director/env`. Read it with:

```bash
grep XPSR_ACCESS_CODE ~/.config/xpsr-director/env
```

To keep it running across logouts and reboots as a systemd user service:

```bash
apps/director/install-service.sh          # port 8790
systemctl --user restart xpsr-director    # after pulling changes
```

### Open it on phones

The server only listens on this machine. To reach it from phones:

| Who should reach it | Command | Address |
| --- | --- | --- |
| Your own devices on your tailnet | `tailscale serve --bg 8790` | `https://<machine>.<tailnet>.ts.net` |
| Anyone with the link (a room full of participants) | `tailscale funnel --bg 8790` | the same address, on the public internet |

With Funnel, the page itself is public, but every GPU, Flow and media request needs the access code, and wrong codes are throttled. Share the code in the room, not in the link. Turn it off afterwards with `tailscale funnel reset`.

The page installs as an app (Add to Home Screen) and opens offline: the brief, shots and audit keep working and save on the phone, and frames and motion wait for the connection.

## The gates

### Gate 01: the brief

![The exclusions card: three red NEVER chips reading No fake latte-art close-ups, No stock smiling baristas, and No claims about taste awards, with an input to add another.](../../docs/images/director/02-exclusions.png)

Pick Ember & Oak, Spoke Co-op or a custom pitch. The facts you may claim come from the [client briefs](../../workshop-build/client-briefs/), each with its research id. The three answers start empty on purpose: the director writes them.

Each gate closes with a slide-to-sign control and the director's name. It stays blocked until the gate's list of missing pieces is empty. Changing anything in a signed gate reopens it, because the signature covered the old version.

![A signed gate: Signed, gate passed, approved by Workshop director with the date and time.](../../docs/images/director/03-sign-off.png)

### Gate 02: previs

![A shot card: Shot 01 Establishing, with framing Wide, lens 24 mm, 10 seconds, move Push In, location the original roastery, the roaster on screen, the action, visual prompt and voiceover line, source SRC-001 selected, and a Record or snap button for phone blocking.](../../docs/images/director/04-shot-card.png)

Shots use the kit's vocabulary (`schemas/shot_breakdown.schema.json`). A voiceover line with a claim cannot be signed off without a source id. **Record or snap** opens the phone camera. A photo is used as it is, and a video gives up one frame. Either becomes the layout reference for that shot's first frame.

### Gate 03: first frame, last frame, action

![Shot 01 in production: pass 1, the locked first frame of a roaster over a steaming pot of beans; pass 1b, the locked last frame of the same room and roaster a moment later; pass 2, the two frames side by side with an arrow, the action prompt, a Veo 3.1 Lite option at 10 credits, a budget bar at 0 of 50 credits, and Connect Google Flow and Hold the still buttons.](../../docs/images/director/06-first-last-action.png)

This is the kit's two-pass rule made visible:

1. **First frame.** Render takes, tap one to pick it, lock it. The source can be the local GPU, Flow images or a phone photo, set per shot or for the whole project.
2. **Last frame, optional.** Say only what has changed. It is drawn with the locked first frame as its reference, so the room, the people and the light carry over. Skip it and the video model decides where the shot ends.
3. **Action.** Describe only what moves between the two frames. The local model can write a draft. Then render on Flow, or **hold the still** and spend nothing.

Motion stays locked until the frames are locked, in the app and again on the server. Unlocking a first frame unlocks the last frame and motion built on it, and reopens picture lock.

![The free-allowance card: frames are free on the local GPU, only motion spends Flow credits; a budget bar at 0 of 50 credits; a note that 50 credits a day buys 5 Veo 3.1 Lite or 2 Veo 3.1 Fast clips; and a two-way switch between Local FLUX.2 klein and Flow Nano Banana for every unlocked frame.](../../docs/images/director/05-free-allowance.png)

### Gate 04: the audit

![The audit score: 2 of 7 passed, slop risk 71 percent, and Human signature not signed, release locked.](../../docs/images/director/08-audit-score.png)

![Check 03, Continuity, marked Fail, with a machine note and the auditor's evidence: shot 1's roaster has short hair and a grey tee; shot 2's hands are a different person; retake shot 2 with the roaster.](../../docs/images/director/09-audit-check.png)

Each check gets Pass or Fail and one line of evidence. A machine note shows what the app can count: cited lines, logged assets, last frames drawn from first frames. Check 1 can ask the local model to read every shot against the exclusions, but the auditor decides. **Slop risk** is simply the share of checks not yet passed. Check 7 cannot pass until a director's signature is typed, and the pack is marked for release only at 7 of 7.

![The pack sheet: Draft pack, a warning that the audit is not at 7 of 7, tabs for brief.md, brief.json, research_log.csv and the rest, a preview of brief.md, a checkbox to include 4 picked frames and clips, and Copy as text and Download .zip buttons.](../../docs/images/director/10-pack.png)

## Google Flow through useapi.net

Motion is the one step that does not run here. It goes to Google Flow on your own Google account, through [useapi.net](https://useapi.net/docs/api-google-flow-v1), a third-party service with a documented REST API. The app is a client of that API, written from its documentation. It does not talk to Google's private endpoints itself and it does not solve captchas: useapi.net does that, on its side.

![The accounts sheet: local writing model llama3.2:3b; Google Flow through useapi.net, not connected, with a button to connect a Google account at useapi.net, a field for the API token, the plan set to free and 50 credits per day.](../../docs/images/director/11-accounts.png)

### Connect it

1. Make a useapi.net account and subscribe. Their service is paid; the Flow credits are what's free.
2. Connect your Google account on their [Google Flow setup page](https://useapi.net/docs/start-here/setup-google-flow). You sign in on their automated browser; you do not paste cookies anywhere.
3. In the app, tap **FLOW** in the header, paste the useapi.net API token, set your plan and a daily credit budget, and save.
4. Tap **Check connected accounts** to see each Google account's health and live credit balance.

The token is written to `~/.config/xpsr-director/env` on the machine (mode 600). It is never sent to the browser and never stored in the repo. **Forget token** removes it.

### What is free, and the budget guard

From useapi.net's price table (October 2026; their figures are averages from busy accounts, not guarantees):

| Model | Clip | Credits, free to Pro plans | Plans |
| --- | --- | --- | --- |
| Veo 3.1 Lite | 8 s | 10 | All, including free |
| Veo 3.1 Fast | 8 s | 20 | All, including free |
| Veo 3.1 Quality | 8 s | 100 | All (more than a free day) |
| Omni 1.1 Flash 720p | 4, 6, 8, 10 s | 7, 10, 12, 15 | Plus and up |
| Omni 1.1 Flash 360p | 4, 6, 8, 10 s | 4, 5, 6, 7 | Plus and up |
| Nano Banana images | | 0 | All |

- **Free accounts get about 50 credits a day:** 5 Veo Lite clips or 2 Veo Fast clips. Omni needs a paid plan. On Plus (200 credits a month), 4-second Omni 360p tests cost 4 credits each.
- **Every image and clip needs one captcha solve.** useapi.net gives the first account 300 free solves, then asks for your own solving service at about $0.80 to $3.00 per 1,000. Frames made on the local GPU use none.
- **The server keeps a credit ledger per local day and refuses any clip that would go over the daily budget,** or over the live balance the account last reported. A failed job puts its credits back in the local ledger, and the live balance stays the source of truth.
- **The budget and plan live in the env file:** `FLOW_PLAN=free|plus|pro|ultra` and `FLOW_DAILY_CREDITS=50`. Change them from the accounts sheet.

![The motion panel with Omni 1.1 Flash 360p chosen, clip length 4 seconds at 4 credits, and the budget bar showing this clip 4 credits, then 46 left.](../../docs/images/director/07-omni-360p.png)

### The risk

Automating Flow through a third party may go against Google's terms. Google can limit or suspend an account that does it. Use an account you can afford to lose, and read [useapi.net's legal page](https://useapi.net/docs/legal) first.

## Library: every file, and the credits it cost

![The library on a phone: totals of clips, frames and credits used; a Where the credits went card; filters for everything, clips, Flow frames, GPU frames and phone photos; and the first frame from shot 1.](../../docs/images/director/12-library.png)

`/library` lists every frame and clip the server has made or received. Each one shows its model, seed, prompt, date and size, and a download link. Clips also show their credit cost, and frames link to the reference they were drawn from. **Where the credits went** groups every Flow charge by day, next to the clip it paid for and the shot it was for. Failed jobs are struck through and shown as refunded.

Out of credits? Every clip there is already paid for. **Use in shot** puts it back as a take in any shot of the current project. Its provenance row says it was reused and that its credits were spent earlier.

Files live in `~/.local/share/xpsr-director/media`, and the job log and ledger in `~/.local/share/xpsr-director/store.json`.

## Machine resources

![The resources page on a desktop: the GPU 100 percent busy at 53 degrees and 56 of 215 watts with a three-minute graph, graphics memory 7.3 of 8 GB almost all ComfyUI, the CPU at 2.3 percent with a 64-thread heat grid, 11.7 of 118 GB system memory in use, Ollama, ComfyUI and Flow status, disk use, and recent jobs with their times.](../../docs/images/director/13-resources-desktop.png)

`/resources` shows the machine live, refreshed every 1.5 seconds while it is open:

- **GPU:** busy share, graphics memory split between Ollama and ComfyUI, temperature, power, clocks and PCIe link.
- **CPU:** load, with a heat grid of every thread.
- **Memory:** system memory and swap.
- **Engines and disks:** which Ollama models are loaded, ComfyUI's queue, today's Flow credits, disk use, and the recent jobs with how long each took.

Every graph also has its numbers as text.

The server keeps the GPU to one job at a time. Before a frame it unloads Ollama's models, and before the writing model runs it asks ComfyUI to free its memory, so the two never fight over the 8 GB card. The resources page shows the handoff.

![The same resources page at phone width, with the cards stacked.](../../docs/images/director/14-resources-phone.png)

## Settings

All optional, in `~/.config/xpsr-director/env` or the environment:

| Key | Default | What it does |
| --- | --- | --- |
| `XPSR_ACCESS_CODE` | made on first start | The code phones enter. Change it and restart to sign everyone out. |
| `USEAPI_TOKEN` | none | useapi.net token. Set from the app. |
| `FLOW_PLAN` | `free` | `free`, `plus`, `pro` or `ultra`: which models and clip lengths are offered. |
| `FLOW_DAILY_CREDITS` | `50` | Hard cap per local day. |
| `FLOW_EMAIL` | none | Which connected Google account to use, if there are several. |
| `OLLAMA_URL`, `OLLAMA_MODEL` | `http://127.0.0.1:11434`, `llama3.2:3b` | Writing model. |
| `COMFYUI_URL` | `http://127.0.0.1:8188` | Frame renderer. Frames use `pipelines/02-production/workflows/flux2_klein_*.json`. |
| `XPSR_ENV`, `XPSR_DATA` | `~/.config/xpsr-director/env`, `~/.local/share/xpsr-director` | Where secrets and media live. |

## Security notes

- **Secrets stay out of the repo.** The env file lives in your home folder, not the repo, and is written with mode 600.
- **Every API request needs the code.** It arrives as an HttpOnly, SameSite=Strict session cookie (Secure behind Tailscale). Every POST also needs a custom header, so other sites cannot send requests on a visitor's behalf.
- **Wrong codes are throttled.** Eight wrong codes from one address lock it out for ten minutes.
- **The page loads nothing from other sites.** It sends a strict Content Security Policy. Media names are random, and the static file server refuses paths outside `web/`.

## Files

| File | What it is |
| --- | --- |
| `server.py` | The server: static files, the access code, jobs, the Ollama, ComfyUI and useapi.net clients, the credit ledger, the library and resources APIs. |
| `install-service.sh` | Installs the systemd user service. |
| `web/index.html`, `app.js`, `app.css` | The four-gate app. |
| `web/data.js` | Roles, the two clients' facts, shot vocabulary, the seven checks. |
| `web/pack.js`, `web/zip.js` | Builds the kit's files and the ZIP, with no library. |
| `web/api.js` | Server calls, and photo and video-frame conversion before upload. |
| `web/resources.*`, `web/library.*` | The resources and library pages. |
| `web/sw.js`, `manifest.webmanifest`, `icon*` | Offline shell and home-screen install. |
| `web/fonts/` | JetBrains Mono and Inter Tight, bundled (SIL Open Font License). |
