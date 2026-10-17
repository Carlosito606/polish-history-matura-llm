#!/usr/bin/env bash
# Select RFT rows from the raw chunks on /scratch and copy dataset + stats to /workspace/data (NFS: copy, then verify).
set -uo pipefail
R=${RFT_DIR:-/scratch/rft}
PY=${PY:-/scratch/ovl/venvs/wmt/bin/python}
cd "$R/repo" || exit 1
$PY train/rft/rft_select.py --raw "$R/out/raw" --out "$R/out/rft_v3.jsonl" > "$R/out/select.log" || { cat "$R/out/select.log"; exit 1; }
mkdir -p /workspace/data/rft_v3_work/raw
for f in rft_v3.jsonl rft_v3.jsonl.stats.json; do
  cp "$R/out/$f" "/workspace/data/$f.tmp" && mv "/workspace/data/$f.tmp" "/workspace/data/$f" || echo "copy failed: $f"
done
cp "$R"/out/raw/chunk_*.jsonl "$R/out/prep_info.json" /workspace/data/rft_v3_work/raw/ 2>/dev/null || echo "raw copy failed"
cmp -s "$R/out/rft_v3.jsonl" /workspace/data/rft_v3.jsonl && echo "copied OK: $(wc -l < /workspace/data/rft_v3.jsonl) rows" || echo "VERIFY FAILED"
$PY -c "import json; d=json.load(open('$R/out/rft_v3.jsonl.stats.json')); a=d['per_qtype']['ALL']; print('raw', d['raw_rows'], 'rows', d['rows'], 'q_kept', a['q_kept'], 'keep', a['keep_rate'], 'greedy', a['greedy_acc'])"
