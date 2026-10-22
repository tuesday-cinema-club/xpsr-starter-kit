#!/usr/bin/env bash
# Rerun the Ember & Oak build end to end into a new folder.
#
# The script runs each agent or tool, then stops at every gate and asks YOU
# for the decision. It never approves anything on its own.
#
# Needs: Ollama with llama3.2:3b, Python 3.9+, ffmpeg.
# Optional (skipped with a note if missing): Blender, a running ComfyUI with
# the SDXL depth workflow models, Whisper, Piper in .venv.
#
# Usage, from the repository root:
#   bash examples/run_demo.sh            # writes to demo-run/
#   bash examples/run_demo.sh my-run     # writes to my-run/

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

OUT="${1:-demo-run}"
BIBLE="templates/ember-and-oak-bible.json"
PY="python3"
[[ -x .venv/bin/python ]] && PY=".venv/bin/python"
mkdir -p "$OUT"
cp examples/ember-and-oak-demo/research_log.csv "$OUT/"

ask_gate() {   # ask_gate <state file> <gate name> [provenance]
  local state="$1" name="$2" prov="${3:-}"
  echo
  echo "== $name: your decision =="
  echo "Read the files above, then choose: 1 Approve, 2 Revise, 3 Reject, 4 Request Evidence"
  local choice decision who note
  read -r -p "Number: " choice || true
  case "$choice" in
    1) decision="Approve" ;; 2) decision="Revise" ;; 3) decision="Reject" ;; 4) decision="Request Evidence" ;;
    *) echo "No decision recorded. Stopping."; exit 1 ;;
  esac
  read -r -p "Your name: " who || true
  read -r -p "Note (optional): " note || true
  if [[ -n "$prov" ]]; then
    $PY pipelines/gate.py --state "$state" --decision "$decision" --by "$who" --note "$note" --provenance "$prov"
  else
    $PY pipelines/gate.py --state "$state" --decision "$decision" --by "$who" --note "$note"
  fi
  if [[ "$decision" != "Approve" ]]; then
    echo "Stopped at $name. Edit the files in $OUT/ (or rerun the stage), then run this script again."
    exit 0
  fi
}

echo "== Gate 01: Brief =="
$PY pipelines/01-pre-production/draft_brief.py \
  --client-brief workshop-build/client-briefs/ember-and-oak.md \
  --research-log "$OUT/research_log.csv" \
  --who "Neighbors who already walk past the new shop on their way to work" \
  --feel "That the roastery down the street is part of their morning, not a chain" \
  --do "Stop in at the second shop this week" \
  --exclusion "No slow-motion latte-art pour" \
  --exclusion "No stock hipster-barista tropes or forced smiles" \
  --exclusion "No claims we cannot source, such as best coffee in town" \
  --out-dir "$OUT"
echo; cat "$OUT/brief.md"
ask_gate "$OUT/brief_state.json" "Gate 01 Brief"

echo; echo "== Gate 02: Shot list =="
$PY pipelines/01-pre-production/run_breakdown.py --brief "$OUT/brief.json" --bible "$BIBLE" \
  --research-log "$OUT/research_log.csv" --out "$OUT/shots.json" || true
$PY -c "import json,sys; [print(f\"Shot {s['shot_number']}: {s['framing']} {s['lens_mm']}mm, {s['duration_sec']}s, {s['camera_move']}. {s['action_description']} VO: {s['voiceover_line']}\") for s in json.load(open(sys.argv[1]))['shots']]" "$OUT/shots.json"
ask_gate "$OUT/shots_state.json" "Gate 02 Shot list" "$OUT/provenance.csv"

if command -v blender >/dev/null 2>&1; then
  echo; echo "== Previs in Blender =="
  blender -b --python-exit-code 1 -P pipelines/02-production/blender_previs.py -- \
    --shots "$OUT/shots.json" --bible "$BIBLE" --out "$OUT/previs" 2>&1 | grep -E "^\[previs\]"
  echo "Open $OUT/previs/ and look at the grey renders before continuing."
else
  echo "[warn] Blender not found: skipping previs and keyframes."
fi

if [[ -d "$OUT/previs" ]] && curl -fsS http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
  echo; echo "== Gate 03: Keyframes in ComfyUI =="
  $PY pipelines/02-production/comfyui_client.py --shots "$OUT/shots.json" --bible "$BIBLE" \
    --previs "$OUT/previs" --out "$OUT/frames" --comfyui-dir "${COMFYUI_DIR:-../ComfyUI}" --depth-strength 0.5
  echo "Open $OUT/frames/ and review every frame."
  ask_gate "$OUT/frames/frames_state.json" "Gate 03 Keyframes" "$OUT/provenance.csv"
else
  echo "[warn] ComfyUI is not running on 127.0.0.1:8188 (or there is no previs): skipping keyframes."
  echo "Without keyframes the cut cannot be assembled. Start ComfyUI and run again."
  exit 0
fi

echo; echo "== Post-production =="
VOICE="$HOME/.local/share/piper-voices/en_US-ljspeech-high.onnx"
if [[ -f "$VOICE" ]] && $PY -c "import piper" 2>/dev/null; then
  $PY pipelines/03-post-production/scratch_vo.py --shots "$OUT/shots.json" --voice "$VOICE" --out "$OUT/audio/vo_scratch.wav"
  AUDIO="$OUT/audio/vo_scratch.wav"
else
  read -r -p "Path to your recorded voiceover (wav or m4a), or press Enter to cut without audio: " AUDIO
fi
AUDIO_ARGS=(); CAP_ARGS=()
if [[ -n "${AUDIO:-}" ]]; then
  AUDIO_ARGS=(--audio "$AUDIO")
  if command -v whisper >/dev/null 2>&1; then
    $PY pipelines/03-post-production/transcribe.py --audio "$AUDIO" --out "$OUT/captions.srt" --provenance "$OUT/provenance.csv"
    echo "Read $OUT/captions.srt against the audio and fix any mistakes now."
    read -r -p "Press Enter when the captions are correct. " || true
    CAP_ARGS=(--captions "$OUT/captions.srt")
  fi
fi
$PY pipelines/03-post-production/generate_timeline.py --shots "$OUT/shots.json" --frames "$OUT/frames" \
  ${AUDIO_ARGS[@]+"${AUDIO_ARGS[@]}"} ${CAP_ARGS[@]+"${CAP_ARGS[@]}"} --fps 24 --out "$OUT/timeline.otio"
$PY pipelines/03-post-production/assemble_animatic.py --shots "$OUT/shots.json" --frames "$OUT/frames" \
  ${AUDIO_ARGS[@]+"${AUDIO_ARGS[@]}"} ${CAP_ARGS[@]+"${CAP_ARGS[@]}"} --fps 24 --end-card "Ember & Oak / Second shop now open" --out "$OUT/cut.mp4"

echo; echo "== Gate 04: Present =="
$PY pipelines/03-post-production/qc_check.py --video "$OUT/cut.mp4" --bible "$BIBLE" --brief "$OUT/brief.json" || true
$PY pipelines/03-post-production/pre_audit.py --project "$OUT" --bible "$BIBLE" --cut "$OUT/cut.mp4"
echo
echo "Screen $OUT/cut.mp4, score checks 1, 3 and 4 in $OUT/audit.md, and sign check 7 if it earns it."
