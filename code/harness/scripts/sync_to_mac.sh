#!/usr/bin/env bash
# Sync harness/ and the harness-owned devset files to the Mac (run from Git Bash on the laptop).
set -euo pipefail
REPO=${REPO:-$HOME/wmt-matura}
tar -C "$REPO" --exclude=__pycache__ -cf - harness devset/eval.py devset/smoke.jsonl \
  | ssh -o BatchMode=yes baza 'tar -C ~/wmt-matura -xf - && chmod +x ~/wmt-matura/harness/scripts/*.sh'
echo synced
