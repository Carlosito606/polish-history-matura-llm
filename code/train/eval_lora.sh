#!/usr/bin/env bash
# Evaluate a GGUF LoRA on a dev file through the harness, on a SEPARATE server pair, then stop it.
#
#   train/eval_lora.sh --lora bielik11b-r16 --base-gguf bielik-11b-v3/Bielik-11B-v3.0-Instruct.Q4_K_M.gguf \
#                      --dev devset/dev-a.jsonl --label r16-e1 --ab
#
# - llama-server :18082 = the untouched official GGUF + --lora-scaled adapter.gguf:SCALE (base file only read)
# - harness      :18002 -> :18082 (same KB and code as the main pair)
# - devset/eval.py --endpoint answer, one row per run appended to devset/experiments.csv with label
#       lora=<name>@<scale>|base=<gguf>|<--label>
# - --ab   : second pass on the SAME server with the adapter scale set to 0 via POST /lora-adapters
#            (= base model, identical harness), label ...|lora-off; prints how many answers changed
# - --raw  : also evaluate the raw model without harness (eval.py --endpoint openai), LoRA on (and off with --ab)
# - both servers are stopped on exit (trap); the main pair :18080/:18000 is never touched
#
# Options:
#   --lora NAME|PATH     adapter GGUF (NAME -> /workspace/loras/NAME.gguf)                          [required]
#   --base-gguf PATH     base GGUF (absolute or relative to /workspace/models)                      [required]
#   --dev FILE[,FILE]    dev jsonl file(s), repo-relative or absolute        [devset/smoke.jsonl]
#   --label TEXT         free-text suffix for the experiments.csv label
#   --scale S            LoRA scale [1.0]
#   --workers N          eval.py workers [8]
#   --chat-template-kwargs JSON   e.g. '{"enable_thinking":false}' for Qwen3 hybrids (same as in training)
#   --harness-env "K=V ..."       extra harness env, e.g. "CHRONO_MODE=hybrid QTYPE_V2=1"
#   --eval-args "..."             extra args for devset/eval.py (e.g. "--limit 20 --show 5")
#   --keep                        leave the :18082/:18002 pair running
# Env: LLM_PORT [18082] HARNESS_PORT [18002] CTX [16384] NP [8] ROOT [/workspace/wmt-matura]
set -euo pipefail

ROOT=${ROOT:-/workspace/wmt-matura}
VENV=${VENV:-/workspace/venvs/wmt}
LORA_DIR=${LORA_DIR:-/workspace/loras}
MODELS_DIR=${MODELS_DIR:-/workspace/models}
LOGS=${LOGS:-/workspace/logs}
export LLM_PORT=${LLM_PORT:-18082} HARNESS_PORT=${HARNESS_PORT:-18002}
export CTX=${CTX:-16384} NP=${NP:-8}
LORA="" BASE_GGUF="" DEV=devset/smoke.jsonl LABEL="" SCALE=1.0 WORKERS=8 CTK="" HENV="" EARGS="" AB=0 RAW=0 KEEP=0

while [ $# -gt 0 ]; do
  case "$1" in
    --lora) LORA=$2; shift 2 ;;
    --base-gguf) BASE_GGUF=$2; shift 2 ;;
    --dev) DEV=$2; shift 2 ;;
    --label) LABEL=$2; shift 2 ;;
    --scale) SCALE=$2; shift 2 ;;
    --workers) WORKERS=$2; shift 2 ;;
    --chat-template-kwargs) CTK=$2; shift 2 ;;
    --harness-env) HENV=$2; shift 2 ;;
    --eval-args) EARGS=$2; shift 2 ;;
    --ab) AB=1; shift ;;
    --raw) RAW=1; shift ;;
    --keep) KEEP=1; shift ;;
    -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
[ -n "$LORA" ] && [ -n "$BASE_GGUF" ] || { echo "need --lora and --base-gguf" >&2; exit 2; }
case "$LORA" in /*|*/*) ;; *) LORA=$LORA_DIR/${LORA%.gguf}.gguf ;; esac
case "$BASE_GGUF" in /*) ;; *) BASE_GGUF=$MODELS_DIR/$BASE_GGUF ;; esac
[ -f "$LORA" ] || { echo "LoRA not found: $LORA" >&2; exit 1; }
[ -f "$BASE_GGUF" ] || { echo "base GGUF not found: $BASE_GGUF" >&2; exit 1; }
if [ "$LLM_PORT" = 18080 ] || [ "$HARNESS_PORT" = 18000 ]; then echo "refusing to use the main ports" >&2; exit 2; fi
if curl -sf -m 3 "http://127.0.0.1:$LLM_PORT/health" >/dev/null 2>&1 || curl -sf -m 3 "http://127.0.0.1:$HARNESS_PORT/health" >/dev/null 2>&1; then
  echo "something already listens on :$LLM_PORT or :$HARNESS_PORT; stop it first (LLM_PORT=$LLM_PORT HARNESS_PORT=$HARNESS_PORT bash scripts/l40s_serve.sh stop)" >&2
  exit 1
fi

LNAME=$(basename "$LORA" .gguf)
BNAME=$(basename "$BASE_GGUF" .gguf)
TAG="lora=$LNAME@$SCALE|base=$BNAME${LABEL:+|$LABEL}"
FILES=()
IFS=',' read -ra _d <<< "$DEV"
for f in "${_d[@]}"; do case "$f" in /*) FILES+=("$f") ;; *) FILES+=("$ROOT/$f") ;; esac; done
cd "$ROOT"
export MODEL_FILE=$BASE_GGUF LORA_FILE=$LORA LORA_SCALE=$SCALE CHAT_TEMPLATE_KWARGS=$CTK
export BASE_LLM_BASE_URL=http://127.0.0.1:$LLM_PORT/v1 REQUEST_LOG=$LOGS/harness-$HARNESS_PORT-requests.jsonl
ALIAS=$(basename "$(dirname "$BASE_GGUF")"); export ALIAS
if [ -n "$CTK" ] && [ -z "${LLM_EXTRA_BODY:-}" ]; then export LLM_EXTRA_BODY="{\"chat_template_kwargs\": $CTK}"; fi
# shellcheck disable=SC2086
[ -n "$HENV" ] && export $HENV

cleanup() {
  if [ "$KEEP" = 1 ]; then echo "--keep: :$LLM_PORT/:$HARNESS_PORT left running"; return; fi
  bash "$ROOT/scripts/l40s_serve.sh" stop || true
  rm -rf "${TMP:-/nonexistent}"
}
trap cleanup EXIT

echo "== $TAG  dev=${FILES[*]}"
bash "$ROOT/scripts/l40s_serve.sh" start

LLOG=$LOGS/llama-$LLM_PORT.log
echo "-- llama-server LoRA evidence ($LLOG):"
if grep -qiE "lora|adapter" "$LLOG"; then grep -iE "lora|adapter" "$LLOG" | head -8
else echo "   (b11185 logs no LoRA lines at the default verbosity; rely on /lora-adapters + the probe below)"; fi
echo "-- GET /lora-adapters: $(curl -s -m 5 "http://127.0.0.1:$LLM_PORT/lora-adapters")"

# deterministic probe: first dev question, raw chat, adapter at SCALE vs 0 (per-request "lora" override)
"$VENV/bin/python" - "${FILES[0]}" "$LLM_PORT" "$ALIAS" "$SCALE" <<'EOF' || true
import json, sys, httpx
f, port, alias, scale = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
q = json.loads(open(f, encoding="utf-8").readline())["question"]
out = {}
for s in (scale, 0.0):
    r = httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions", timeout=120, json={
        "model": alias, "messages": [{"role": "user", "content": q}], "temperature": 0, "max_tokens": 40,
        "lora": [{"id": 0, "scale": s}]}).json()
    out[s] = r["choices"][0]["message"]["content"]
print(f"-- probe (raw, 1st dev question): lora@{scale}={out[scale][:80]!r}  lora@0={out[0.0][:80]!r}  "
      f"{'DIFFERENT' if out[scale] != out[0.0] else 'identical'}")
EOF

TMP=$(mktemp -d)
run_eval() {  # endpoint label -> prints the per-question run file (absolute) on stdout; eval output -> stderr
  local ep=$1 lab=$2 out
  local extra=()
  if [ "$ep" = openai ]; then extra=(--url "http://127.0.0.1:$LLM_PORT/v1" --model "$ALIAS"); else extra=(--url "http://127.0.0.1:$HARNESS_PORT"); fi
  # (never `tee /dev/stderr`: reopening the log file truncates it)
  # shellcheck disable=SC2086
  "$VENV/bin/python" devset/eval.py --endpoint "$ep" "${extra[@]}" --files "${FILES[@]}" --workers "$WORKERS" \
      --label "$lab" $EARGS 2>&1 | tee "$TMP/eval.out" >&2
  out=$(grep -E '^per-question results -> ' "$TMP/eval.out" | sed 's/^per-question results -> //' | tail -1)
  case "$out" in /*) ;; ?*) out=$ROOT/$out ;; esac
  echo "$out"
}
set_scale() { curl -s -m 10 -X POST "http://127.0.0.1:$LLM_PORT/lora-adapters" -H 'Content-Type: application/json' \
                -d "[{\"id\": 0, \"scale\": $1}]" >/dev/null; echo "-- adapter scale -> $1: $(curl -s -m 5 "http://127.0.0.1:$LLM_PORT/lora-adapters")"; }

changed() {  # runA runB
  "$VENV/bin/python" - "$1" "$2" <<'EOF'
import json, sys
a = {json.loads(l)["id"]: json.loads(l) for l in open(sys.argv[1], encoding="utf-8")}
b = {json.loads(l)["id"]: json.loads(l) for l in open(sys.argv[2], encoding="utf-8")}
ids = sorted(set(a) & set(b))
ch = [i for i in ids if a[i]["pred"].strip() != b[i]["pred"].strip()]
fx = sum(1 for i in ids if a[i]["extract"] and not b[i]["extract"])
br = sum(1 for i in ids if b[i]["extract"] and not a[i]["extract"])
print(f"-- answers changed LoRA vs off: {len(ch)}/{len(ids)}  (LoRA fixed {fx}, LoRA broke {br})")
for i in ch[:8]:
    print(f"   {i}: lora={a[i]['pred'][:50]!r} off={b[i]['pred'][:50]!r} gold={a[i]['gold']!r}")
EOF
}

R_ON=$(run_eval answer "$TAG" | tail -1)
if [ "$RAW" = 1 ]; then RAW_ON=$(run_eval openai "$TAG|raw" | tail -1); fi
if [ "$AB" = 1 ]; then
  set_scale 0
  R_OFF=$(run_eval answer "lora=$LNAME@0(off)|base=$BNAME${LABEL:+|$LABEL}" | tail -1)
  if [ "$RAW" = 1 ]; then RAW_OFF=$(run_eval openai "lora=$LNAME@0(off)|base=$BNAME${LABEL:+|$LABEL}|raw" | tail -1); fi
  set_scale "$SCALE"
  echo "== harness:"; changed "$R_ON" "$R_OFF"
  if [ "$RAW" = 1 ]; then echo "== raw (no harness):"; changed "$RAW_ON" "$RAW_OFF"; fi
fi
echo "== done: rows appended to $ROOT/devset/experiments.csv (label prefix lora=$LNAME)"
