#!/usr/bin/env bash
# Copy results of the /scratch/ovl run back to persistent NFS /workspace (retries: NFS returns EACCES at times).
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
retry bash -c "cp -n $S/loras/final-bielik-4.5b-v3-r16-e2.gguf* /workspace/loras/"
retry cp -a $S/runs/final-bielik-4.5b-v3-r16-e2 /workspace/runs/
retry mkdir -p /workspace/data/overnight/scratch_copy
retry bash -c "cp /scratch/overnight/*.sh /scratch/overnight/*.py /scratch/overnight/*.status /workspace/data/overnight/scratch_copy/"
echo "$(date -u +%H:%M:%S) SYNC DONE"
