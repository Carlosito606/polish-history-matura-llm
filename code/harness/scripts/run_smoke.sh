#!/usr/bin/env bash
# base (raw passthrough) vs harness on devset/smoke.jsonl; extra args go to eval.py (e.g. --cfg use_kb=0)
cd "$(dirname "$0")/../.."
source .venv/bin/activate
python devset/eval.py --files devset/smoke.jsonl --endpoint base --label smoke-base-raw
python devset/eval.py --files devset/smoke.jsonl --endpoint answer --label smoke-harness "$@"
