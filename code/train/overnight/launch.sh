#!/usr/bin/env bash
cd /scratch/overnight || exit 1
bash mirror.sh > mirror.log 2>&1
grep -q "MIRROR DONE" mirror.log || { echo "$(date -u +%H:%M:%S) mirror FAILED" >> sup.status; exit 1; }
bash sup2.sh > sup2.out 2>&1
