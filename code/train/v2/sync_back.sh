#!/usr/bin/env bash
# Copy v2 results from /scratch/ovl back to NFS /workspace (retries; NFS returns EACCES at times).
set -u
S=/scratch/ovl
retry() { local i; for i in 1 2 3 4 5 6 7 8 9 10; do "$@" && return 0; echo "retry $i: $*"; sleep 60; done; return 1; }
append_rows() {
  $S/venvs/wmt/bin/python - <<'PY'
src, dst = "/scratch/ovl/wmt-matura/devset/experiments.csv", "/workspace/wmt-matura/devset/experiments.csv"
have = set(open(dst, encoding="utf-8").read().splitlines())
new = [l for l in open(src, encoding="utf-8").read().splitlines() if l and l not in have]
with open(dst, "a", encoding="utf-8") as f:
    f.write("".join(l + "\n" for l in new))
print("appended", len(new), "rows")
PY
}
retry append_rows
retry cp -rn $S/wmt-matura/devset/runs/. /workspace/wmt-matura/devset/runs/
retry mkdir -p /workspace/loras/merged
for f in $S/loras/bielik45-v2-*; do [ -f "$f" ] && retry cp -n "$f" /workspace/loras/; done
for f in $S/loras/merged/bielik45-v2-*; do [ -f "$f" ] && retry cp -n "$f" /workspace/loras/merged/; done
for d in $S/runs/bielik45-v2-*; do [ -d "$d" ] && retry cp -a "$d" /workspace/runs/; done
retry mkdir -p /workspace/data/v2_logs
retry bash -c "cp /scratch/v2/*.sh /scratch/v2/*.py /scratch/v2/*.status /scratch/v2/*.log /workspace/data/v2_logs/"
echo "$(date -u +%H:%M:%S) SYNC DONE"
