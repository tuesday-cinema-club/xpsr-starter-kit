# Hardware Reality Matrix

Find the row that matches your device. Every row gets a full seat at the table.

| Tier | Typical hardware | Crews it suits | What runs locally |
| --- | --- | --- | --- |
| Phone | Any recent iPhone or Android phone, 2 GB free | Director, Auditor, voiceover recording, camera-move reference | Nothing to install. Read briefs, vote, record voice memos, film reference moves, score the audit. |
| Laptop | 8 to 16 GB RAM, no dedicated GPU, about 10 GB free disk | Writer, Previs, Edit & Sound | `llama3.2:3b` in Ollama, Blender grey-box previs, Whisper `base.en`, ffmpeg animatic, Kdenlive |
| Laptop with GPU | 8 GB or more of NVIDIA VRAM, or Apple Silicon with 16 GB or more unified memory, about 40 GB free disk | Frames, plus everything above | ComfyUI with SDXL or FLUX.2 [klein] 4B, depth ControlNet, optional Wan 2.2 5B motion |
| Studio workstation | 24 GB or more of VRAM | Frames and Motion at full quality | Larger text models (14B and up), image-to-video at higher resolution |

## Tested on

The demo in `examples/ember-and-oak-demo/` was produced on one machine on 2026-10-22:

| Part | Detail |
| --- | --- |
| GPU | NVIDIA GeForce RTX 2070 SUPER, 8 GB VRAM (the "Laptop with GPU" tier) |
| System | Ubuntu Linux, 109 GB RAM |
| Ollama | 0.18.2 with `llama3.2:3b` |
| Blender | 5.2.2 LTS, Cycles on the GPU through OptiX |
| ComfyUI | 0.42.0 with SDXL base 1.0 and `controlnet-depth-sdxl-1.0-small` |
| Whisper | openai-whisper with `base.en` |
| ffmpeg | 6.1.1 |
| Bigger models (comparison) | `glm-4.7-flash` in Ollama; FLUX.2 [klein] 4B in ComfyUI |
| Pushing the limit | `gpt-oss-120b` in Ollama; FLUX.2 [dev] 32B and Wan 2.2 5B in ComfyUI; Kokoro-82M; Whisper `turbo` |

## Timings from that run

| Step | Time |
| --- | --- |
| Brief draft (`llama3.2:3b`, first call includes loading the model) | 58 seconds |
| Shot breakdown, 3 shots | 14 seconds |
| Blender previs, 3 grey renders and 3 depth passes | 23 seconds |
| One SDXL keyframe, 1344 by 768, 30 steps, with depth ControlNet | about 22 seconds (77 seconds for the first, which loads the model) |
| Whisper transcription of 30 seconds of audio | 4 seconds |
| ffmpeg animatic, 30 seconds at 1920 by 1080 | 17 seconds |

### Bigger models on the same machine

| Step | Time |
| --- | --- |
| Brief draft with `glm-4.7-flash` (about 30B parameters, 19 GB) | 58 to 63 seconds |
| Shot breakdown with `glm-4.7-flash` | 90 to 108 seconds |
| One FLUX.2 [klein] 4B keyframe, 1344 by 768, 4 steps, with a depth reference | 37 to 48 seconds |

### Pushing the limit on the same machine

Charts of these numbers, and estimates for bigger hardware, are in [How long it takes](../docs/performance.md).

The biggest models this 8 GB card can run at all, used for [the summit pitch, pushing the limit](../examples/agentic-summit-pitch-limit/README.md). They lean on the machine's 109 GB of system RAM: none of them fit in VRAM.

| Step | Time |
| --- | --- |
| Brief draft with `gpt-oss-120b` (117B parameters, 63 GB), thinking on high | 4 minutes 35 seconds |
| Shot breakdown, 6 shots, thinking on high | 30 minutes (2 attempts) |
| One FLUX.2 [dev] 32B keyframe, 1920 by 1056, 28 steps, photo and depth references | 28 to 34 minutes (60 to 73 seconds per step) |
| One Wan 2.2 5B motion clip, 121 frames at 1280 by 704 (5 seconds), 20 steps | 24 minutes |
| Kokoro-82M scratch voiceover, 6 lines, on the CPU | under 1 minute |
| Whisper `turbo` on 30 seconds of audio, on the CPU | 60 seconds |
| Qwen3-TTS voice clone, 6 lines, on the GPU | under 1 minute |
| One 5-second music audition, MusicGen stereo large in half precision, on the GPU | 8 seconds |
| One 30-second music take, MusicGen stereo large, on the CPU (64 threads) | 18 to 20 minutes |
| The whole 30-second spot, including the failed run and the retakes | about 8 and a half hours of machine time |

Two setup notes from that run. Ollama 0.18.2 was too old for the official `gpt-oss:120b` download, so the model came from `hf.co/ggml-org/gpt-oss-120b-GGUF` with a corrected chat template. And `gpt-oss-120b` with FLUX.2 [dev] loaded at the same time would need more than 109 GB of RAM, so run `ollama stop <model>` before rendering.

A CPU-only laptop will be slower for the model steps (think minutes, not seconds) and cannot run the Frames step in workshop time. That is why the Frames crew needs a GPU laptop and everyone else does not.

## Model licenses

"Free", "open-source", "open-weight" and "local" mean different things. Check each model's license before you use it for paid work.

| Model | Used for | License to check |
| --- | --- | --- |
| Llama 3.2 3B | Writing | Llama 3.2 Community License (has an acceptable use policy and conditions for very large companies) |
| Qwen 2.5 7B | Writing | Apache 2.0 for most sizes; check the model card for the size you pull |
| SDXL base 1.0 | Keyframes | CreativeML Open RAIL++-M (use restrictions apply) |
| FLUX.2 [klein] 4B | Keyframes | Apache 2.0, per the participant guide; confirm on the model card |
| controlnet-depth-sdxl-1.0-small | Depth guidance | Open RAIL++-M, same family as SDXL |
| GLM-4.7-Flash | Writing (bigger model) | MIT, per the model's Ollama listing |
| FLUX.2 [klein] 4B (distilled) and Qwen3 4B text encoder | Keyframes (bigger model) | Apache 2.0 (the 9B klein variant uses a different, non-commercial license) |
| Wan 2.2 5B | Motion (optional) | Apache 2.0 |
| gpt-oss-120b | Writing (pushing the limit) | Apache 2.0 |
| FLUX.2 [dev] 32B | Keyframes (pushing the limit) | FLUX non-commercial license: read it before any paid use of the model or its output |
| Mistral Small 3.1 24B | FLUX.2 [dev] text encoder | Apache 2.0 |
| Kokoro-82M | Scratch voiceover (pushing the limit) | Apache 2.0 |
| Qwen3-TTS-12Hz-1.7B-Base | Voice clone of a consenting person (`scratch_vo.py --voice clone:`) | Apache 2.0 |
| MusicGen (`facebook/musicgen-stereo-medium`, `-large`) | Music bed (`music_bed.py`) | CC-BY-NC 4.0: non-commercial use only. The AudioCraft code is MIT. |
| Whisper | Captions | MIT |
| Piper voice `en_US-ljspeech-high` | Scratch voiceover | Trained on the public-domain LJ Speech dataset; Piper itself is GPL |

Licenses change. The model card on the download page is the source of truth, not this table.
