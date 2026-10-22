#!/usr/bin/env bash
# Tuesday Cinema Club starter kit: local studio setup for macOS and Linux.
#
# What it does (and nothing else):
#   1. Installs Ollama if it is missing (asks first).
#   2. Pulls the workshop writing model, llama3.2:3b (about 2 GB).
#   3. Creates a Python virtual environment in .venv with the optional helpers
#      (jsonschema, opentimelineio, piper-tts). The pipeline scripts also run
#      without them using only the Python standard library.
#   4. Runs environment/check_setup.py.
#
# Usage, from the repository root:
#   bash environment/setup-mac-linux.sh
#   bash environment/setup-mac-linux.sh --yes      # do not ask before installing Ollama
#   TCC_MODEL=qwen2.5:7b bash environment/setup-mac-linux.sh

set -euo pipefail

MODEL="${TCC_MODEL:-llama3.2:3b}"
ASSUME_YES="no"
[[ "${1:-}" == "--yes" ]] && ASSUME_YES="yes"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

step() { printf '\n== %s ==\n' "$1"; }

step "1 of 4: Ollama"
if command -v ollama >/dev/null 2>&1; then
  echo "[ready] Ollama is installed: $(ollama -v 2>/dev/null | head -1)"
else
  if [[ "$(uname)" == "Darwin" ]]; then
    echo "[missing] Ollama. Download the Mac app from https://ollama.com/download, open it once, then rerun this script."
    exit 1
  fi
  answer="$ASSUME_YES"
  if [[ "$answer" != "yes" ]]; then
    read -r -p "Ollama is not installed. Install it now with the official script from ollama.com? [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]] && answer="yes"
  fi
  if [[ "$answer" == "yes" ]]; then
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "Skipped. Install from https://ollama.com/download and rerun."
    exit 1
  fi
fi

step "2 of 4: Writing model ($MODEL)"
if ! curl -fsS http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  echo "[working] Starting the Ollama daemon in the background ..."
  (ollama serve >/dev/null 2>&1 &)
  sleep 3
fi
ollama pull "$MODEL"

step "3 of 4: Python helpers"
if ! command -v python3 >/dev/null 2>&1; then
  echo "[missing] Python 3. Install it from https://www.python.org/downloads/ and rerun."
  exit 1
fi
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
echo "[ready] .venv created. Use .venv/bin/python to run scripts with the optional helpers."

step "4 of 4: Check"
.venv/bin/python environment/check_setup.py || true

cat <<MSG

Next: test the model. If it replies, you are ready.
  ollama run $MODEL "hi"

GPU laptop? Install ComfyUI next: see environment/README.md, section "ComfyUI".
MSG
