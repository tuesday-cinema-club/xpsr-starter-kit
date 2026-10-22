# Documentation

Reference material for the Tuesday Cinema Club + XPSR Creator Summit, 10/24/26.

## Documents

| Document | What it is |
| --- | --- |
| [Participant guide](participant-guide.md) | The attendee handout: setup by device, Part 1 in one page, the 60-minute build, troubleshooting. |
| [Part 1 talk outline](presentation-notes.md) | Talk structure with what to show from this repo for each idea. The slides are in [the presentation deck on Google Slides](https://docs.google.com/presentation/d/1f4xDXcP211pzTOrO6uBBurJBfZXbqNYSe1a6GFWs85A/edit?usp=sharing). |
| [Six-session series](six-session-curriculum.md) | What each session covers and which folders it uses. |
| [Accessibility notes](../ACCESSIBILITY.md) | How this repository is written so it works with screen readers and without color. |

## Screenshots

Every image in `images/` comes from a real run of this kit on one machine (RTX 2070 SUPER, Ubuntu, 2026-10-22). Terminal images are rendered from the commands' captured output with `tools/term_screenshot.py`; nothing in them was retyped. The ComfyUI image is a browser screenshot of the running ComfyUI server.

| File | Shows |
| --- | --- |
| `01-setup-check.png` | `environment/check_setup.py` output |
| `02-ollama-hi.png` | The guide's command 3: `ollama run llama3.2:3b "hi"` |
| `03a-brief-agent.png` | Brief agent, Gate 01 |
| `03-shot-breakdown.png` | Shot breakdown agent with its four checks |
| `04-gate-02.png` | Revise, re-check, Approve at Gate 02 |
| `05a-blender-terminal.png` | Headless Blender previs |
| `05-blender-previs.jpg` | Grey renders and depth passes |
| `06-comfyui-client.png` | Keyframes through ComfyUI's API |
| `07-comfyui-ui.png` | The depth workflow in the ComfyUI web page, with a rendered frame |
| `08-keyframes-rejected-vs-approved.jpg` | Rejected take 1 next to approved frames |
| `09-vo-captions.png` | Scratch voiceover and Whisper captions, mistakes included |
| `10-final-cut-stills.jpg` | Four stills from the finished cut |
| `11-animatic-qc-audit.png` | Animatic, technical QC and pre-audit |
| `12-sdxl-vs-flux2-klein.jpg` | The same shots from SDXL and from FLUX.2 klein |
| `12a-glm-shot-breakdown.png` | The shot agent running on `glm-4.7-flash` |
| `13-grand-cru-cut-stills.jpg` | Four stills from the car wash cut |
| `13a-grand-cru-finish.png` | Car wash timeline, cut, QC and pre-audit |
| `14-grand-cru-previs-to-keyframes.jpg` | Car wash depth passes, rejected take 1 and approved frames |

The animated previews of each finished cut live in each example folder as `cut-preview.webp`.
