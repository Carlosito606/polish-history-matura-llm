#!/bin/bash
# run_all.sh: candidates smallest first; a candidate that does not fit in free VRAM is retried every 5 min.
V=/scratch/vlm
PENDING="${*:-qwen3vl-4b-q8 gemma4-e4b-q5km gemma4-12b-qat qwen35-9b-q5km qwen3vl-8b-q6k}"
while [ -n "$PENDING" ]; do
  LEFT=""
  for n in $PENDING; do
    $V/run_one.sh $n; rc=$?
    [ $rc = 3 ] && LEFT="$LEFT $n"
  done
  PENDING=$(echo $LEFT)
  [ -n "$PENDING" ] && { echo "$(date +%T) waiting 5 min for VRAM: $PENDING"; sleep 300; }
done
echo "$(date +%T) ALL DONE"
