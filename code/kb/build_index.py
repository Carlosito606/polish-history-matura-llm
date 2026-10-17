"""Build a memory-mappable BM25 index (chunk level + article level) from chunk parquet shards.

Usage (Mac, from ~/wmt-matura):
  # full index over all chunks
  python -m kb.build_index --chunks kb_data/chunks --out kb_data/index --workers 8
  # history subset / mini index for smoke tests (~40k chunks)
  python -m kb.build_index --chunks kb_data/chunks --out kb_data/index_mini --target-chunks 40000 --max-chunks-per-article 5

Index dir layout (all numpy files are loaded with mmap_mode='r'):
  tokenizer.json            tokenizer config + BM25 params + stats
  chunks.{indptr,indices,weights,vocab}.npy     CSR (term -> chunk ids, BM25 weight as float16)
  articles.{indptr,indices,weights,vocab}.npy   same for the article-level index
                             (title x2 + redirects + headings + opening_text)
  store.bin / store_off.npy  chunk records "title\\x1fsection\\x1ftext\\x1furl" (utf-8)
  chunk_article.npy          int32 article row of each chunk
  art_store.bin / art_off.npy  article records "title\\x1furl\\x1fopening_text"
  art_pop.npy / art_inlinks.npy / art_first_chunk.npy
  redirects.tsv              "redirect title<TAB>article title" (from CirrusSearch `redirect`)
No neural models; pure numpy.
"""
from __future__ import annotations

import argparse
import glob
import json
import multiprocessing as mp
import os
import shutil
import time
from collections import Counter

import numpy as np
import pyarrow.parquet as pq

from kb.textnorm import Tokenizer

K1, B = 1.2, 0.75
MAXB = 16  # vocab entries are stored as fixed-width bytes (S16)

_TK = None


def _init(cfg):
    global _TK
    _TK = Tokenizer.from_config(cfg)


def _tok_batch(texts):
    local: dict[str, int] = {}
    terms, docs, tfs = [], [], []
    dl = np.zeros(len(texts), np.int32)
    for i, t in enumerate(texts):
        toks = _TK.tokens(t)
        dl[i] = len(toks)
        for w, n in Counter(toks).items():
            j = local.get(w)
            if j is None:
                j = local[w] = len(local)
            terms.append(j)
            docs.append(i)
            tfs.append(n)
    return (list(local.keys()), np.asarray(terms, np.int32), np.asarray(docs, np.int32),
            np.minimum(np.asarray(tfs, np.int32), 65535).astype(np.uint16), dl)


def vkey(w: str) -> bytes:
    return w.encode("utf-8")[:MAXB]


class BM25Builder:
    """Streaming CSR builder: pass 1 tokenises in a pool and spills COO batches to disk,
    pass 2 scatters them into term-major CSR with precomputed BM25 weights."""

    def __init__(self, tmp: str, pool, batch_docs: int = 4000):
        self.tmp = tmp
        os.makedirs(tmp, exist_ok=True)
        self.pool = pool
        self.vocab: dict[bytes, int] = {}
        self.df = np.zeros(1 << 20, np.int64)
        self.dls: list[np.ndarray] = []
        self.nb = 0
        self.ndocs = 0
        self.batch_docs = batch_docs
        self.pending = []

    def _absorb(self, res):
        keys, t, d, tf, dl = res
        vocab = self.vocab
        g = np.fromiter((vocab.setdefault(vkey(w), len(vocab)) for w in keys), np.int64, len(keys))
        tg = g[t].astype(np.int32)
        if len(vocab) > len(self.df):
            self.df = np.concatenate([self.df, np.zeros(max(len(vocab), 2 * len(self.df)) - len(self.df), np.int64)])
        # one doc may map two local terms to the same S16 key (very long tokens) -> dedupe (term, doc)
        pair = tg.astype(np.int64) * (1 << 32) + d
        u, idx = np.unique(pair, return_index=True)
        if len(u) != len(pair):
            tg, d, tf = tg[idx], d[idx], tf[idx]
        bc = np.bincount(tg, minlength=len(vocab))
        self.df[: len(bc)] += bc
        np.savez(os.path.join(self.tmp, f"b{self.nb:06d}.npz"), t=tg, d=d + self.ndocs, tf=tf)
        self.nb += 1
        self.ndocs += len(dl)
        self.dls.append(dl)

    def add(self, texts: list[str]):
        """texts must arrive in doc-id order; submitted async, absorbed in order."""
        for i in range(0, len(texts), self.batch_docs):
            self.pending.append(self.pool.apply_async(_tok_batch, (texts[i:i + self.batch_docs],)))
        while len(self.pending) > 24:
            self._absorb(self.pending.pop(0).get())

    def finish(self, out_prefix: str):
        while self.pending:
            self._absorb(self.pending.pop(0).get())
        V = len(self.vocab)
        df = self.df[:V]
        N = self.ndocs
        dl = np.concatenate(self.dls).astype(np.float32) if self.dls else np.zeros(0, np.float32)
        avgdl = float(dl.mean()) if N else 1.0
        idf = np.log1p((N - df + 0.5) / (df + 0.5)).astype(np.float32)
        # final term ids = sorted byte order, so the query side can binary-search a mmapped S16 array
        keys = np.array(list(self.vocab.keys()), dtype=f"S{MAXB}")
        order = np.argsort(keys, kind="stable")
        new_id = np.empty(V, np.int64)
        new_id[order] = np.arange(V)
        df_new = df[order]
        indptr = np.zeros(V + 1, np.int64)
        np.cumsum(df_new, out=indptr[1:])
        nnz = int(indptr[-1])
        cursor = indptr[:-1].copy()
        indices = np.lib.format.open_memmap(out_prefix + ".indices.npy", mode="w+", dtype=np.int32, shape=(nnz,))
        weights = np.lib.format.open_memmap(out_prefix + ".weights.npy", mode="w+", dtype=np.float16, shape=(nnz,))
        norm = (K1 * (1 - B + B * dl / avgdl)).astype(np.float32)
        for bi in range(self.nb):
            p = os.path.join(self.tmp, f"b{bi:06d}.npz")
            z = np.load(p)
            t, d, tf = z["t"], z["d"], z["tf"].astype(np.float32)
            w = idf[t] * tf * (K1 + 1) / (tf + norm[d])
            tn = new_id[t]
            o = np.argsort(tn, kind="stable")
            tn, d, w = tn[o], d[o], w[o]
            uniq, start, cnt = np.unique(tn, return_index=True, return_counts=True)
            pos = np.arange(len(tn)) - np.repeat(start, cnt)
            dest = cursor[tn] + pos
            indices[dest] = d
            weights[dest] = w.astype(np.float16)
            cursor[uniq] += cnt
            os.remove(p)
        indices.flush()
        weights.flush()
        del indices, weights
        np.save(out_prefix + ".indptr.npy", indptr)
        np.save(out_prefix + ".vocab.npy", keys[order])
        np.save(out_prefix + ".idf.npy", idf[order])
        return {"docs": N, "vocab": V, "nnz": nnz, "avgdl": avgdl}


def write_store(path_bin: str, path_off: str, records):
    offs = [0]
    with open(path_bin, "wb") as f:
        pos = 0
        for r in records:
            b = r.encode("utf-8")
            f.write(b)
            pos += len(b)
            offs.append(pos)
    np.save(path_off, np.asarray(offs, np.int64))


def select_pages(shards, min_hist, target_chunks, min_pop, cap=0):
    """Return set of page_ids to include (None = all)."""
    if min_hist is None and not target_chunks and min_pop is None:
        return None
    import pandas as pd
    parts = [pq.read_table(s, columns=["page_id", "hist_score", "popularity_score", "incoming_links"]).to_pandas()
             for s in shards]
    df = pd.concat(parts)
    g = df.groupby("page_id").agg(h=("hist_score", "first"), pop=("popularity_score", "first"),
                                  inl=("incoming_links", "first"), n=("hist_score", "size"))
    if min_hist is not None:
        g = g[g.h >= min_hist]
    if min_pop is not None:
        g = g[g["pop"] >= min_pop]
    if cap:
        g = g.assign(n=np.minimum(g.n, cap))
    if target_chunks:
        g = g.assign(key=np.log1p(g.inl) + 0.5 * np.clip(g.h, 0, 10)).sort_values("key", ascending=False)
        g = g[g.n.cumsum() <= target_chunks]
    print(f"selected {len(g)} articles, {int(g.n.sum())} chunks", flush=True)
    return set(g.index.tolist())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--mode", default="stem", choices=["stem", "trunc", "none"])
    ap.add_argument("--prefix", type=int, default=7)
    ap.add_argument("--min-hist", type=int, default=None)
    ap.add_argument("--min-pop", type=float, default=None)
    ap.add_argument("--target-chunks", type=int, default=0)
    ap.add_argument("--max-chunks-per-article", type=int, default=0, help="keep only first N chunks of each article")
    ap.add_argument("--max-shards", type=int, default=0, help="debug")
    a = ap.parse_args()
    t0 = time.time()
    shards = sorted(glob.glob(os.path.join(a.chunks, "part-*.parquet")))
    if a.max_shards:
        shards = shards[: a.max_shards]
    keep = select_pages(shards, a.min_hist, a.target_chunks, a.min_pop, a.max_chunks_per_article)
    cap = a.max_chunks_per_article
    os.makedirs(a.out, exist_ok=True)
    tmp = os.path.join(a.out, "_tmp")
    tk = Tokenizer(mode=a.mode, prefix=a.prefix)
    cfg = tk.config()
    ctx = mp.get_context("spawn")
    cols = ["page_id", "title", "section", "text", "url", "aliases", "popularity_score",
            "incoming_links", "chunk_idx", "opening_text", "headings"]
    with ctx.Pool(a.workers, initializer=_init, initargs=(cfg,)) as pool:
        cb = BM25Builder(os.path.join(tmp, "c"), pool)
        ab = BM25Builder(os.path.join(tmp, "a"), pool, batch_docs=8000)
        f_store = open(os.path.join(a.out, "store.bin"), "wb")
        f_art = open(os.path.join(a.out, "art_store.bin"), "wb")
        f_red = open(os.path.join(a.out, "redirects.tsv"), "w", encoding="utf-8")
        store_off, art_off = [0], [0]
        chunk_article, art_pop, art_inl, art_first = [], [], [], []
        last_pid = None
        n_art = -1
        for si, s in enumerate(shards):
            t = pq.read_table(s, columns=cols).to_pydict()
            idx_texts, art_texts = [], []
            for i in range(len(t["title"])):
                pid = t["page_id"][i]
                if keep is not None and pid not in keep:
                    continue
                if cap and t["chunk_idx"][i] >= cap:
                    continue
                title = t["title"][i]
                if pid != last_pid:
                    last_pid = pid
                    n_art += 1
                    art_pop.append(t["popularity_score"][i])
                    art_inl.append(t["incoming_links"][i])
                    art_first.append(len(store_off) - 1)
                    aliases = (t["aliases"][i] or "").replace("|", " ; ")
                    heads = (t["headings"][i] or "").replace("|", " ; ")
                    op = t["opening_text"][i] or ""
                    art_texts.append(f"{title} ; {title} ; {aliases} ; {heads} ; {op}")
                    for al in (t["aliases"][i] or "").split("|"):
                        if al and chr(9) not in al:
                            f_red.write(al + chr(9) + title + chr(10))
                    b = f"{title}\x1f{t['url'][i]}\x1f{op}".encode("utf-8")
                    f_art.write(b)
                    art_off.append(art_off[-1] + len(b))
                text = t["text"][i]
                itext = text
                if t["chunk_idx"][i] == 0 and t["aliases"][i]:
                    itext = text + "\n" + t["aliases"][i].replace("|", " ; ")
                idx_texts.append(itext)
                b = f"{title}\x1f{t['section'][i]}\x1f{text}\x1f{t['url'][i]}".encode("utf-8")
                f_store.write(b)
                store_off.append(store_off[-1] + len(b))
                chunk_article.append(n_art)
            if idx_texts:
                cb.add(idx_texts)
            if art_texts:
                ab.add(art_texts)
            if si % 50 == 0:
                print(f"[{time.time()-t0:7.1f}s] shard {si+1}/{len(shards)} chunks={len(chunk_article)} "
                      f"articles={n_art+1} vocab={len(cb.vocab)}", flush=True)
        f_store.close()
        f_art.close()
        f_red.close()
        print(f"[{time.time()-t0:7.1f}s] pass1 done; building CSR", flush=True)
        cst = cb.finish(os.path.join(a.out, "chunks"))
        ast = ab.finish(os.path.join(a.out, "articles"))
    np.save(os.path.join(a.out, "store_off.npy"), np.asarray(store_off, np.int64))
    np.save(os.path.join(a.out, "art_off.npy"), np.asarray(art_off, np.int64))
    np.save(os.path.join(a.out, "chunk_article.npy"), np.asarray(chunk_article, np.int32))
    np.save(os.path.join(a.out, "art_pop.npy"), np.asarray(art_pop, np.float32))
    np.save(os.path.join(a.out, "art_inlinks.npy"), np.asarray(art_inl, np.int32))
    np.save(os.path.join(a.out, "art_first_chunk.npy"), np.asarray(art_first, np.int32))
    meta = {"tokenizer": cfg, "k1": K1, "b": B, "maxb": MAXB, "chunks": cst, "articles": ast,
            "source": "plwiki-20251229-cirrussearch-content", "filter": {"min_hist": a.min_hist,
            "min_pop": a.min_pop, "target_chunks": a.target_chunks, "max_chunks_per_article": cap}, "build_seconds": round(time.time() - t0, 1)}
    with open(os.path.join(a.out, "tokenizer.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    print("DONE", json.dumps(meta, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
