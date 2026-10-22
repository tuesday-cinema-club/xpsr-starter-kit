# OpenClaw Workspace Files

Plain-text instructions for an always-on background agent. They are written for [OpenClaw](https://github.com/openclaw/openclaw), which reads Markdown files from its workspace folder (by default `~/.openclaw/workspace`), but any agent runner that reads instruction files can use them.

This folder is **optional**. Every pipeline in this kit runs from the command line without a background agent.

## Files

| File | Purpose |
| --- | --- |
| `AGENTS.md` | Which agents exist, the command each runs, and where each may read and write. |
| `SOUL.md` | The studio's voice and non-negotiables: plain words, no filler, no unsourced claims. |
| `HEARTBEAT.md` | Read-only checks to run every 30 minutes: schemas, bible match, waiting gates, provenance, disk. |
| `MEMORY.md` | Decisions the director has approved, so later drafts do not undo them. |

## Install

```bash
mkdir -p ~/.openclaw/workspace
cp agents/openclaw-workspace/{AGENTS,SOUL,HEARTBEAT,MEMORY}.md ~/.openclaw/workspace/
```

File names and loading rules can change between OpenClaw versions. Check its documentation for the version you install.

## Safety

A background agent with file access can do real damage. Before you start one:

- Run it in its own user account or container with access to the project folder only.
- Keep the "never delete" and "never call cloud APIs" rules in `AGENTS.md`.
- Keep the gates human. The agent may run checks; it may not run `pipelines/gate.py`.
