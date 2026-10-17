#!/usr/bin/env bash
# One-shot exam dry run: health-check llama-server + harness, run harness/batch.py --both on a
# questions file (whatever shape the organisers hand out), and archive the results with a README
# that pins the exact settings and the model files (name + sha256) that produced them.
#
#   scripts/run_exam.sh questions.json probny
#   scripts/run_exam.sh questions.jsonl probny --concurrency 8 --timeout 90   # extra args -> batch.py
#   scripts/run_exam.sh questions.json --limit 5                             # no label -> "exam"; dry test
#
# Env (defaults in brackets):
#   HARNESS_URL  [http://127.0.0.1:18000]  harness base URL (health-checked, then passed to batch.py)
#   LLM_URL      [http://127.0.0.1:18080]  llama-server base URL, health-checked directly (repo rule:
#                                          the base benchmark must come from a separate, untouched server)
#   MODELS_DIR   [models]                  hashed into the README: every *.gguf found under it, recursively
#   PYTHON       [.venv/bin/python3 if present, else python3]
#   RESULTS_DIR  [results]
set -euo pipefail
cd "$(dirname "$0")/.."

if [ $# -lt 1 ]; then
  echo "usage: scripts/run_exam.sh <questions_file> [label] [-- extra harness.batch args]" >&2
  exit 2
fi
QUESTIONS=$1; shift
LABEL=exam
if [ $# -gt 0 ] && [[ $1 != -* ]]; then LABEL=$1; shift; fi

HARNESS_URL=${HARNESS_URL:-http://127.0.0.1:18000}
LLM_URL=${LLM_URL:-http://127.0.0.1:18080}
MODELS_DIR=${MODELS_DIR:-models}
RESULTS_DIR=${RESULTS_DIR:-results}
if [ -z "${PYTHON:-}" ]; then
  PYTHON=.venv/bin/python3; [ -x "$PYTHON" ] || PYTHON=python3
fi
[ -f "$QUESTIONS" ] || { echo "questions file not found: $QUESTIONS" >&2; exit 2; }

echo "== health checks =="
LLM_HEALTH=$(curl -sf -m 5 "$LLM_URL/health") || { echo "FAILED: llama-server /health ($LLM_URL) unreachable"; exit 1; }
echo "llama-server: $LLM_HEALTH"
HARNESS_HEALTH=$(curl -sf -m 5 "$HARNESS_URL/health") || { echo "FAILED: harness /health ($HARNESS_URL) unreachable"; exit 1; }
echo "harness:      $HARNESS_HEALTH"
case "$HARNESS_HEALTH" in
  *'"llm_ok":true'*) : ;;
  *) echo "FAILED: harness /health says llm_ok=false (harness up, llama-server not reachable from it)"; exit 1 ;;
esac

TS=$(date +%Y%m%d-%H%M%S)
OUT_DIR="$RESULTS_DIR/${TS}_${LABEL}"
mkdir -p "$OUT_DIR"
echo "== $OUT_DIR =="

echo "== harness/batch.py --both =="
"$PYTHON" -m harness.batch "$QUESTIONS" --both --url "$HARNESS_URL" --out "$OUT_DIR/answers" "$@"

echo "== hashing model files ($MODELS_DIR/**/*.gguf) =="
LIMIT_BYTES=$((8 * 1024 * 1024 * 1024))  # organisers' opening-deck rule: every model <= 8 GB on disk
SHA_ROWS=""
if [ -d "$MODELS_DIR" ]; then
  while IFS= read -r -d '' f; do
    sha=$( { shasum -a 256 "$f" 2>/dev/null || sha256sum "$f" 2>/dev/null; } | awk '{print $1}')
    size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo "")
    rel=${f#"$MODELS_DIR"/}
    human=$([ -n "$size" ] && awk -v b="$size" 'BEGIN{printf "%.2f GB", b/1024/1024/1024}' || echo "?")
    SHA_ROWS="${SHA_ROWS}| \`$rel\` | $human | \`$sha\` |
"
    echo "  $rel  $human  $sha"
    if [ -n "$size" ] && [ "$size" -gt "$LIMIT_BYTES" ]; then
      echo "  [WARNING] $rel is $human, over the 8 GB exam-time limit (CLAUDE.md)"
    fi
  done < <(find "$MODELS_DIR" -type f -name '*.gguf' -print0 | sort -z)
else
  echo "  (no $MODELS_DIR/ here -- run this on the box that serves llama-server)"
fi

cat > "$OUT_DIR/README.md" <<EOF
# Exam run: $LABEL

- when: $TS
- questions file: \`$QUESTIONS\`
- harness: $HARNESS_URL (harness/batch.py --both -> \`answers_base.*\` + \`answers_harness.*\`)
- llama-server: $LLM_URL
- extra harness.batch args: ${*:-(none)}

## Health at run time

\`\`\`
llama-server: $LLM_HEALTH
harness:      $HARNESS_HEALTH
\`\`\`

## Model files (\`$MODELS_DIR\`, \`*.gguf\`, recursive)

| file | size | sha256 |
|---|---|---|
${SHA_ROWS:-| *(none found)* | | |
}

## Output files

- \`answers_base.json\` / \`.csv\` / \`.jsonl\`    -- untouched model: no RAG, no system prompt, temperature 0
- \`answers_harness.json\` / \`.csv\` / \`.jsonl\` -- full RAG pipeline (\`/answer\`)

Grade with \`devset/eval.py\`'s grading functions once the organisers' key is out, or diff
\`answers_base.csv\` vs \`answers_harness.csv\` to sanity-check the RAG pipeline is actually helping.
EOF

echo "== done -> $OUT_DIR/README.md =="
