"""Build a dense index (kb/dense.py layout) over a subset of the KB chunks.

1) choose chunk ids (global KB chunk ids = row order of kb_data/chunks/part-*.parquet = kb_data/index store order)
   python -m kb.dense_build select --chunks kb_data/chunks --index kb_data/index --out ids.npy \
          [--min-hist 2] [--min-inlinks 50] [--all] \
          [--sample-devsets devset/dev-a.jsonl ... --target 150000 --seed 0]   # bake-off sample
2) embed them (llama-server --embedding, concurrent batched requests; resumable)
   python -m kb.dense_build embed --preset qwen3-emb-0.6b --url http://127.0.0.1:18093 \
          --ids ids.npy --index kb_data/index --out kb_data/dense/qwen3-emb-0.6b [--batch 32 --conc 4] [--resume]
   (--backend st uses in-process sentence-transformers instead, e.g. for sdadas/mmlw-retrieval-roberta-large)
3) optional FAISS index for big N (flat fp32 needs 4 GB RAM per 1M x 1024)
   python -m kb.dense_build faiss --out kb_data/dense/qwen3-emb-0.6b --kind ivfsq|hnsw|ivfpq|flat
4) optional: concatenate several embed outputs (e.g. core scope + extension, or a stopped partial run)
   python -m kb.dense_build merge DIR1 DIR2 --out kb_data/dense/<preset> [--block 8192]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kb.dense import PRESETS, format_doc, make_embedder  # noqa: E402


def _chunk_table(chunks_dir: str, cols: list[str]):
    import pyarrow as pa
    import pyarrow.parquet as pq
    shards = sorted(glob.glob(os.path.join(chunks_dir, "part-*.parquet")))
    tabs = [pq.read_table(s, columns=cols) for s in shards]
    return pa.concat_tables(tabs)


def load_gold_titles(paths: list[str]) -> set[str]:
    out = set()
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for ln in f:
                if not ln.strip():
                    continue
                g = json.loads(ln).get("source_title")
                if not g:
                    continue
                for t in ([g] if isinstance(g, str) else g):
                    if not t.startswith("~"):
                        out.add(t)
    return out


def cmd_select(a):
    from kb.search import KB
    kb = KB(a.index)
    t0 = time.time()
    tab = _chunk_table(a.chunks, ["title", "hist_score", "incoming_links"])
    n = tab.num_rows
    assert n == kb.n_chunks, f"parquet rows {n} != KB chunks {kb.n_chunks}"
    hist = tab.column("hist_score").to_numpy()
    inl = tab.column("incoming_links").to_numpy()
    print(f"loaded {n} rows in {time.time()-t0:.1f}s", flush=True)
    stats = {"n_all": int(n)}
    for h in (1, 2, 3):
        stats[f"hist>={h}"] = int((hist >= h).sum())
    for L in (20, 50, 100, 200, 500):
        stats[f"inlinks>={L}"] = int((inl >= L).sum())
        stats[f"hist>=2|inlinks>={L}"] = int(((hist >= 2) | (inl >= L)).sum())
    print(json.dumps(stats), flush=True)
    if a.sample_devsets:
        titles = tab.column("title").to_numpy(zero_copy_only=False)
        golds = load_gold_titles(a.sample_devsets)
        golds |= {kb.resolve_title(g) for g in golds}
        gmask = np.fromiter((t in golds for t in titles), bool, count=n)
        found = set(titles[gmask])
        print(f"gold titles {len(golds)}, found as articles {len(found)}; missing: {sorted(golds - found)[:20]}")
        gold_ids = np.flatnonzero(gmask)
        pool = np.flatnonzero((hist >= a.min_hist_distractor) & ~gmask)
        rng = np.random.default_rng(a.seed)
        nd = max(0, min(len(pool), a.target - len(gold_ids)))
        dis = rng.choice(pool, nd, replace=False)
        ids = np.sort(np.concatenate([gold_ids, dis])).astype(np.int32)
        print(f"sample: gold chunks {len(gold_ids)} + distractors {nd} (hist>={a.min_hist_distractor}) = {len(ids)}")
    elif a.all:
        ids = np.arange(n, dtype=np.int32)
    else:
        m = np.zeros(n, bool)
        if a.min_hist is not None:
            m |= hist >= a.min_hist
        if a.min_inlinks is not None:
            m |= inl >= a.min_inlinks
        ids = np.flatnonzero(m).astype(np.int32)
        print(f"scope: {len(ids)} chunks")
    np.save(a.out, ids)
    print("saved", a.out, len(ids))


def cmd_embed(a):
    from kb.search import KB
    kb = KB(a.index)
    ids = np.load(a.ids)
    N = len(ids)
    os.makedirs(a.out, exist_ok=True)
    preset = a.preset
    dim = PRESETS.get(preset, {}).get("dim", a.dim)
    st = (a.backend or ("llama" if a.url else "st")) == "st"
    vpath = os.path.join(a.out, "vectors.f16.npy")
    ppath = os.path.join(a.out, "progress.json")
    B = a.block if st else a.batch   # st: big blocks, length-sorted inside encode() -> little padding
    nblocks = (N + B - 1) // B
    start_block = 0
    if a.resume and os.path.exists(vpath) and os.path.exists(ppath):
        vec = np.lib.format.open_memmap(vpath, mode="r+")
        assert vec.shape == (N, dim), (vec.shape, N, dim)
        start_block = json.load(open(ppath))["blocks_done"]
        print(f"resume from block {start_block}/{nblocks}", flush=True)
    else:
        vec = np.lib.format.open_memmap(vpath, mode="w+", dtype=np.float16, shape=(N, dim))
    np.save(os.path.join(a.out, "ids.npy"), ids.astype(np.int32))
    kw = {}
    if st:
        kw = {"batch_size": a.batch, "max_seq_length": a.max_seq, "model_path": a.model}
    emb = make_embedder(preset, url=a.url, backend="st" if st else "llama", **kw)

    def texts(b):
        rows = ids[b * B:(b + 1) * B]
        return [format_doc(preset, kb._record(int(i))["text"]) for i in rows]

    def job(b):
        for attempt in range(5):
            try:
                return b, emb.embed(texts(b))
            except Exception as e:  # transient server errors
                if attempt == 4:
                    raise
                print(f"block {b} retry {attempt}: {e}", flush=True)
                time.sleep(2 + 3 * attempt)

    t0 = time.time()
    done = set(range(start_block))
    contig = start_block
    lock = threading.Lock()
    last = t0
    conc = a.conc if not st else 1
    with ThreadPoolExecutor(conc) as ex:
        it = iter(range(start_block, nblocks))
        pending = set()
        for _ in range(conc * 2):
            b = next(it, None)
            if b is not None:
                pending.add(ex.submit(job, b))
        while pending:
            fin = next(f for f in _as_completed(pending))
            pending.remove(fin)
            b, v = fin.result()
            if v.shape[1] != dim:
                raise SystemExit(f"dim mismatch {v.shape} vs {dim}")
            vec[b * B:b * B + len(v)] = v.astype(np.float16)
            with lock:
                done.add(b)
                while contig in done:
                    contig += 1
            nb = next(it, None)
            if nb is not None:
                pending.add(ex.submit(job, nb))
            now = time.time()
            if now - last > 30 or not pending:
                last = now
                vec.flush()
                json.dump({"blocks_done": contig, "nblocks": nblocks}, open(ppath, "w"))
                rows = min(N, contig * B) - start_block * B
                rate = rows / max(1e-6, now - t0)
                eta = (N - min(N, contig * B)) / max(rate, 1e-6)
                print(f"[{now-t0:7.1f}s] {min(N, contig*B)}/{N} rows  {rate:.1f} chunks/s  eta {eta/60:.1f} min",
                      flush=True)
    vec.flush()
    secs = time.time() - t0
    meta = {"preset": preset, "hf": PRESETS.get(preset, {}).get("hf"), "gguf": PRESETS.get(preset, {}).get("gguf"),
            "backend": "st" if st else "llama", "model_path": a.model if st else None,
            "url": a.url if not st else None, "max_seq": a.max_seq if st else None, "dim": dim, "n": int(N),
            "query_tpl": PRESETS.get(preset, {}).get("query_tpl"), "doc_tpl": PRESETS.get(preset, {}).get("doc_tpl"),
            "kb_index": os.path.abspath(a.index), "ids_from": os.path.abspath(a.ids),
            "embed_seconds": round(secs, 1), "chunks_per_s": round((N - start_block * B) / max(secs, 1e-6), 1),
            "vectors_bytes": os.path.getsize(vpath), "host": os.uname().nodename if hasattr(os, "uname") else "",
            "built": time.strftime("%Y-%m-%d %H:%M:%S")}
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"), indent=1)
    print("DONE", json.dumps(meta), flush=True)


def _as_completed(fs):
    from concurrent.futures import FIRST_COMPLETED, wait
    d, _ = wait(fs, return_when=FIRST_COMPLETED)
    return d


def cmd_faiss(a):
    import faiss  # type: ignore
    vec = np.load(os.path.join(a.out, "vectors.f16.npy"), mmap_mode="r")
    N, d = vec.shape
    t0 = time.time()
    if a.kind == "flat":
        idx = faiss.IndexFlatIP(d)
    elif a.kind == "hnsw":
        idx = faiss.IndexHNSWFlat(d, a.hnsw_m, faiss.METRIC_INNER_PRODUCT)
        idx.hnsw.efConstruction = 80
        idx.hnsw.efSearch = 128
    elif a.kind == "ivfsq":   # IVF + fp16 scalar quantizer: ~exact scores, visits nprobe/nlist of the rows
        nlist = a.nlist or int(4 * np.sqrt(N))
        idx = faiss.IndexIVFScalarQuantizer(faiss.IndexFlatIP(d), d, nlist, faiss.ScalarQuantizer.QT_fp16,
                                            faiss.METRIC_INNER_PRODUCT)
    elif a.kind == "sq8":
        idx = faiss.IndexScalarQuantizer(d, faiss.ScalarQuantizer.QT_8bit, faiss.METRIC_INNER_PRODUCT)
    else:  # ivfpq
        nlist = a.nlist or int(4 * np.sqrt(N))
        q = faiss.IndexFlatIP(d)
        idx = faiss.IndexIVFPQ(q, d, nlist, a.pq_m, 8, faiss.METRIC_INNER_PRODUCT)
    if not idx.is_trained:
        rng = np.random.default_rng(0)
        tr = np.asarray(vec[np.sort(rng.choice(N, min(N, 200_000), replace=False))], np.float32)
        idx.train(tr)
        print(f"trained in {time.time()-t0:.1f}s", flush=True)
    step = 200_000
    for s in range(0, N, step):
        idx.add(np.asarray(vec[s:s + step], np.float32))
    faiss.write_index(idx, os.path.join(a.out, "index.faiss"))
    print(f"faiss {a.kind} N={N} d={d} built in {time.time()-t0:.1f}s, "
          f"{os.path.getsize(os.path.join(a.out, 'index.faiss'))/1e9:.2f} GB")


def cmd_merge(a):
    """Concatenate several embed outputs (same preset) into one index dir; a part without meta.json (stopped
    early) contributes its first progress.json blocks_done*block rows."""
    ids_l, vec_l, metas = [], [], []
    for d in a.parts:
        ids = np.load(os.path.join(d, "ids.npy"))
        vec = np.load(os.path.join(d, "vectors.f16.npy"), mmap_mode="r")
        mp = os.path.join(d, "meta.json")
        if os.path.exists(mp):
            m = json.load(open(mp))
            n = len(ids)
        else:
            pr = json.load(open(os.path.join(d, "progress.json")))
            n = min(len(ids), pr["blocks_done"] * a.block)
            m = {"partial": True}
        print(f"{d}: {n}/{len(ids)} rows", flush=True)
        ids_l.append(ids[:n])
        vec_l.append(vec[:n])
        metas.append(m)
    ids = np.concatenate(ids_l).astype(np.int32)
    assert len(np.unique(ids)) == len(ids), "duplicate chunk ids across parts"
    os.makedirs(a.out, exist_ok=True)
    out = np.lib.format.open_memmap(os.path.join(a.out, "vectors.f16.npy"), mode="w+", dtype=np.float16,
                                    shape=(len(ids), vec_l[0].shape[1]))
    o = 0
    for v in vec_l:
        for s in range(0, len(v), 200_000):
            blk = np.asarray(v[s:s + 200_000])
            out[o:o + len(blk)] = blk
            o += len(blk)
    out.flush()
    np.save(os.path.join(a.out, "ids.npy"), ids)
    base = next(m for m in metas if not m.get("partial"))
    meta = dict(base)
    meta.update({"n": int(len(ids)), "parts": [{"dir": os.path.abspath(d), "rows": int(len(i)),
                                                "embed_seconds": m.get("embed_seconds")}
                                               for d, i, m in zip(a.parts, ids_l, metas)],
                 "embed_seconds": round(sum(m.get("embed_seconds") or 0 for m in metas), 1),
                 "vectors_bytes": os.path.getsize(os.path.join(a.out, "vectors.f16.npy")),
                 "kb_index": a.kb_index or base.get("kb_index"), "scope": a.scope or base.get("scope"),
                 "built": time.strftime("%Y-%m-%d %H:%M:%S")})
    meta.pop("ids_from", None)
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"), indent=1)
    print("merged", len(ids), "rows ->", a.out, flush=True)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("select")
    s.add_argument("--chunks", required=True)
    s.add_argument("--index", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--min-hist", type=int, default=None)
    s.add_argument("--min-inlinks", type=int, default=None)
    s.add_argument("--all", action="store_true")
    s.add_argument("--sample-devsets", nargs="*", default=None)
    s.add_argument("--target", type=int, default=150_000)
    s.add_argument("--min-hist-distractor", type=int, default=2)
    s.add_argument("--seed", type=int, default=0)
    e = sp.add_parser("embed")
    e.add_argument("--preset", required=True)
    e.add_argument("--url", default=None)
    e.add_argument("--backend", default=None, choices=[None, "llama", "st"])
    e.add_argument("--ids", required=True)
    e.add_argument("--index", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--batch", type=int, default=32)
    e.add_argument("--conc", type=int, default=4)
    e.add_argument("--dim", type=int, default=1024)
    e.add_argument("--max-seq", type=int, default=512)
    e.add_argument("--block", type=int, default=4096, help="st backend: rows per encode() call")
    e.add_argument("--model", default=None, help="st backend: local HF model dir (default: preset hub id)")
    e.add_argument("--resume", action="store_true")
    f = sp.add_parser("faiss")
    f.add_argument("--out", required=True)
    f.add_argument("--kind", default="ivfsq", choices=["flat", "hnsw", "ivfpq", "ivfsq", "sq8"])
    f.add_argument("--hnsw-m", type=int, default=32)
    f.add_argument("--nlist", type=int, default=0)
    f.add_argument("--pq-m", type=int, default=64)
    m = sp.add_parser("merge")
    m.add_argument("parts", nargs="+")
    m.add_argument("--out", required=True)
    m.add_argument("--block", type=int, default=4096, help="block size the partial parts were embedded with")
    m.add_argument("--kb-index", default=None, help="KB index dir to record in meta.json")
    m.add_argument("--scope", default=None, help="free-text description of the chunk scope")
    a = ap.parse_args()
    {"select": cmd_select, "embed": cmd_embed, "faiss": cmd_faiss, "merge": cmd_merge}[a.cmd](a)


if __name__ == "__main__":
    main()
