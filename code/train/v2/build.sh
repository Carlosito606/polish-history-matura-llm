#!/usr/bin/env bash
# Stage A: SFT v2 = current verified data (claude_verified + zpe_verified + CKE train) through the exam-time harness
# prompts (QTYPE_V2=1, RERANK=1), decontaminated vs devset; then the train view (pf numbered, meta.type) + token stats.
#   setsid nohup bash /scratch/v2/build.sh > /scratch/v2/build.out 2>&1 < /dev/null &
set -uo pipefail
source /scratch/v2/env.sh
KEY=build
SRC=$S/data/src_v2
mkdir -p "$SRC"
cp -a /workspace/data/src/. "$SRC/" || { say "copy src FAILED"; exit 1; }
say "src: $(for d in claude_verified zpe_verified cke_items devset; do printf '%s=%s ' $d "$(cat $SRC/$d/*.jsonl | grep -c .)"; done)"
rerank_up
cd "$ROOT" || exit 1
OUT=$S/data/sft_v2.jsonl
"$PY" train/build_sft.py build --claude-dir $SRC/claude_verified $SRC/zpe_verified --cke-dir $SRC/cke_items \
  --dev-dir $SRC/devset --kb "$KB_INDEX_DIR" --rerank-url http://127.0.0.1:18092 --out "$OUT" \
  --samples-md $S/data/sft_v2_samples.md --workers 4 > "$V2/build_sft.log" 2>&1
say "build exit $? rows=$(grep -c . "$OUT" 2>/dev/null)"
[ -s "$OUT" ] || exit 1
"$PY" - "$OUT" "$S/data/sft_v2_train.jsonl" <<'PY'
import json, re, sys
PF = re.compile(r"^\s*[PF](\s*,\s*[PF])*\s*$")
n = k = 0
with open(sys.argv[1], encoding="utf-8") as fi, open(sys.argv[2], "w", encoding="utf-8") as fo:
    for ln in fi:
        r = json.loads(ln); m = r["meta"]; m["type"] = m["qtype"]; a = r["messages"][-1]
        if m["qtype"] == "pf" and PF.match(a["content"]):
            a["content"] = "\n".join(f"{i}: {v}" for i, v in enumerate(re.findall(r"[PF]", a["content"]), 1)); k += 1
        fo.write(json.dumps(r, ensure_ascii=False) + "\n"); n += 1
print(f"train view rows={n} pf_numbered={k}")
PY
say "train view rows=$(grep -c . $S/data/sft_v2_train.jsonl)"
"$TPY" train/build_sft.py stats --data "$OUT" --tokenizer speakleash/Bielik-4.5B-v3.0-Instruct > "$V2/stats_bielik.log" 2>&1
say "stats bielik: $(tail -1 "$V2/stats_bielik.log")"
for f in sft_v2.jsonl sft_v2.jsonl.stats.json sft_v2_train.jsonl sft_v2_samples.md; do
  for i in 1 2 3 4 5; do cp "$S/data/$f" /workspace/data/ && break; sleep 30; done
done
say "BUILD DONE"
