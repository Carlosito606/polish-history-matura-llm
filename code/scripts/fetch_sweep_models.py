#!/usr/bin/env python
"""Download the small-model sweep GGUFs to /workspace/models/<dir>/ (L40S) and append sha256 to SHA256SUMS.

  source /workspace/env.sh && python scripts/fetch_sweep_models.py [--models-dir /workspace/models] [--only dir1,dir2]

One file per repo (exact quant, mmproj excluded). The local sha256 is compared with the HF LFS oid.
hf_hub_download writes to .cache/.../*.incomplete and renames at the end, so a *.gguf in the model dir
is always complete (devset/sweep.py relies on that to start a model as soon as it lands).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time

from huggingface_hub import HfApi, hf_hub_download

# (repo, quant, dir) in sweep order
MODELS = [
    ("unsloth/Qwen3.5-4B-GGUF", "Q8_0", "qwen35-4b"),
    ("ggml-org/gemma-3-4b-it-GGUF", "Q8_0", "gemma-3-4b"),
    ("unsloth/gemma-4-E4B-it-GGUF", "Q6_K", "gemma-4-e4b"),
    ("ggml-org/gemma-4-E2B-it-GGUF", "Q8_0", "gemma-4-e2b"),
    ("bartowski/Llama-3.2-3B-Instruct-GGUF", "Q8_0", "llama-3.2-3b"),
    ("unsloth/Qwen3.5-2B-GGUF", "Q8_0", "qwen35-2b"),
    ("Qwen/Qwen3-1.7B-GGUF", "Q8_0", "qwen3-1.7b"),
    ("speakleash/Bielik-1.5B-v3.0-Instruct-GGUF", "Q8_0", "bielik-1.5b"),
    ("bartowski/Llama-3.2-1B-Instruct-GGUF", "Q8_0", "llama-3.2-1b"),
    ("ggml-org/gemma-3-1b-it-GGUF", "Q8_0", "gemma-3-1b"),
    ("unsloth/Qwen3.5-0.8B-GGUF", "Q8_0", "qwen35-0.8b"),
    ("Qwen/Qwen3-0.6B-GGUF", "Q8_0", "qwen3-0.6b"),
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def pick(api: HfApi, repo: str, quant: str) -> tuple[str, int | None, str | None]:
    info = api.model_info(repo, files_metadata=True)
    q = quant.lower()
    cands = []
    for s in info.siblings or []:
        n = s.rfilename
        b = os.path.basename(n).lower()
        if not b.endswith(".gguf") or "mmproj" in b or b.startswith("mtp-"):
            continue
        stem = b[:-5]
        if stem.endswith("-" + q) or stem.endswith("." + q) or stem.endswith("_" + q):
            lfs = getattr(s, "lfs", None)
            sha = (lfs.get("sha256") if isinstance(lfs, dict) else getattr(lfs, "sha256", None)) if lfs else None
            cands.append((n, s.size, sha))
    if not cands:
        raise RuntimeError(f"{repo}: no {quant} gguf in {[s.rfilename for s in info.siblings or []]}")
    cands.sort(key=lambda c: (c[0].count("/"), len(c[0])))  # prefer top-level, shortest name
    return cands[0]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(16 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-dir", default="/workspace/models")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None
    api = HfApi()
    sums = os.path.join(args.models_dir, "SHA256SUMS")
    fails = []
    for repo, quant, d in MODELS:
        if only and d not in only:
            continue
        try:
            fn, size, lfs_sha = pick(api, repo, quant)
            dst_dir = os.path.join(args.models_dir, d)
            dst = os.path.join(dst_dir, os.path.basename(fn))
            if os.path.exists(dst) and (size is None or os.path.getsize(dst) == size):
                log(f"{d}: already present {dst}")
            else:
                t0 = time.time()
                log(f"{d}: downloading {repo}/{fn} ({(size or 0) / 1e9:.2f} GB)")
                p = hf_hub_download(repo, fn, local_dir=dst_dir)
                if os.path.abspath(p) != os.path.abspath(dst):  # file in a subfolder of the repo
                    os.replace(p, dst)
                dt = time.time() - t0
                log(f"{d}: done in {dt:.0f}s ({(size or 0) / 1e6 / max(dt, 1e-3):.0f} MB/s)")
            rel = f"./{d}/{os.path.basename(dst)}"
            have = open(sums, encoding="utf-8").read() if os.path.exists(sums) else ""
            if rel in have:
                log(f"{d}: sha256 already in SHA256SUMS")
                continue
            h = sha256(dst)
            ok = (lfs_sha is None) or (h == lfs_sha)
            log(f"{d}: sha256 {h} {'== LFS oid' if lfs_sha and ok else ('MISMATCH vs ' + str(lfs_sha)) if lfs_sha else '(no LFS oid)'}")
            if not ok:
                fails.append(d)
                continue
            with open(sums, "a", encoding="utf-8", newline="\n") as f:
                f.write(f"{h}  {rel}\n")
        except Exception as e:  # keep going: one broken repo must not block the rest of the sweep
            fails.append(d)
            log(f"{d}: FAILED {type(e).__name__}: {e}")
    log(f"all done; failures: {fails or 'none'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
