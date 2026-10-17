"""Hybrid retrieval: reciprocal-rank fusion of BM25 (kb.search.KB) and dense (kb.dense.DenseIndex) chunk lists,
with an optional cross-encoder rerank of the fused top-N (llama-server --reranking, bge-reranker-v2-m3 GGUF).

    from kb.search import KB
    from kb.dense import DenseIndex
    from kb.hybrid import HybridRetriever
    kb = KB("kb_data/index")
    di = DenseIndex("kb_data/dense/bge-m3", url="http://127.0.0.1:18096", kb=kb)  # llama-server --embedding
    hy = HybridRetriever(kb, di, w_bm25=1.0, w_dense=1.0, rrf_k=60, depth=50,
                         rerank_url="http://127.0.0.1:18097", rerank_top=50)      # rerank_url=None -> no rerank
    hy.search("Kto był pierwszym koronowanym królem Polski?", k=8)
    # -> [{"title","section","text","score","url", "bm25_rank","dense_rank"[, "rrf"]}, ...]  (kb.search.KB format + extras)

Fusion (default level="article"): each list is turned into its ordered list of distinct articles and
score(article) = w_bm25/(rrf_k + r_bm25) + w_dense/(rrf_k + r_dense) (ranks from 1, missing -> no contribution);
the output is grouped by article in that order, chunks inside an article ordered by chunk-level RRF.
level="chunk" fuses chunks keyed by (title, text) instead; it lost 3-6 R@5 points on the bake-off because two
different chunks of the gold article split its votes. Both input lists keep at most `cand_per_article` chunks
per article.
`rerank` may also be any callable (query, [doc texts]) -> [scores] (e.g. harness.retrieval.Reranker(settings).score).
"""
from __future__ import annotations

import threading
import time
from typing import Callable


def _key(h: dict) -> tuple:
    return (h.get("title", ""), h.get("text", "")[:300])


class LlamaReranker:
    """POST {url}/v1/rerank (llama-server --reranking). Returns one relevance score per document."""

    def __init__(self, url: str, model: str = "bge-reranker-v2-m3", timeout: float = 60.0):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client = None
        self._lock = threading.Lock()

    def __call__(self, query: str, docs: list[str]) -> list[float]:
        if not docs:
            return []
        if self._client is None:
            with self._lock:
                if self._client is None:
                    import httpx
                    self._client = httpx.Client(timeout=self.timeout)
        r = self._client.post(self.url + "/v1/rerank",
                              json={"model": self.model, "query": query, "documents": docs, "top_n": len(docs)})
        r.raise_for_status()
        out = [float("-inf")] * len(docs)
        for x in r.json().get("results") or []:
            out[int(x["index"])] = float(x.get("relevance_score", x.get("score", 0.0)))
        return out


def rrf_fuse(bm25_hits: list[dict], dense_hits: list[dict], w_bm25: float = 1.0, w_dense: float = 1.0,
             rrf_k: int = 60, level: str = "article") -> list[dict]:
    """RRF of two ranked chunk lists -> fused chunk list (best first), each hit annotated with its ranks."""
    chunks = _rrf_chunks(bm25_hits, dense_hits, w_bm25, w_dense, rrf_k)
    if level == "chunk":
        return chunks
    art: dict[str, float] = {}
    for w, hs in ((w_bm25, bm25_hits), (w_dense, dense_hits)):
        if not w:
            continue
        seen: set[str] = set()
        for h in hs:
            t = h.get("title", "")
            if t not in seen:
                seen.add(t)
                art[t] = art.get(t, 0.0) + w / (rrf_k + len(seen))
    order = {t: i for i, t in enumerate(sorted(art, key=lambda x: -art[x]))}
    for h in chunks:
        h["art_rrf"] = art.get(h.get("title", ""), 0.0)
        h["score"] = h["art_rrf"]
    return sorted(chunks, key=lambda h: order.get(h.get("title", ""), len(order)))   # stable: chunk RRF inside


def _rrf_chunks(bm25_hits, dense_hits, w_bm25, w_dense, rrf_k) -> list[dict]:
    scores: dict[tuple, float] = {}
    hits: dict[tuple, dict] = {}
    for name, w, hs in (("bm25", w_bm25, bm25_hits), ("dense", w_dense, dense_hits)):
        if not w:
            continue
        for r, h in enumerate(hs, 1):
            k = _key(h)
            scores[k] = scores.get(k, 0.0) + w / (rrf_k + r)
            if k not in hits:
                hits[k] = dict(h)
                hits[k]["bm25_rank"] = None
                hits[k]["dense_rank"] = None
            hits[k][name + "_rank"] = r
    out = []
    for k in sorted(scores, key=lambda x: -scores[x]):
        h = hits[k]
        h["rrf"] = scores[k]
        h["score"] = scores[k]
        out.append(h)
    return out


def cap_per_article(hits: list[dict], per_article: int, k: int | None = None) -> list[dict]:
    if not per_article:
        return hits[:k] if k else hits
    out, seen = [], {}
    for h in hits:
        t = h.get("title", "")
        if seen.get(t, 0) >= per_article:
            continue
        seen[t] = seen.get(t, 0) + 1
        out.append(h)
        if k and len(out) >= k:
            break
    return out


class HybridRetriever:
    def __init__(self, kb, dense, w_bm25: float = 1.0, w_dense: float = 1.0, rrf_k: int = 60, depth: int = 50,
                 per_article: int = 3, cand_per_article: int = 3, bm25_candidates: int = 400,
                 rerank_url: str | None = None, rerank: Callable[[str, list[str]], list[float]] | None = None,
                 rerank_model: str = "bge-reranker-v2-m3", rerank_top: int = 50, rerank_doc_chars: int = 700,
                 rerank_query_chars: int = 1200, rerank_per_article: int = 2, fusion: str = "article"):
        self.kb, self.dense = kb, dense
        self.w_bm25, self.w_dense, self.rrf_k, self.depth = w_bm25, w_dense, rrf_k, depth
        self.per_article, self.cand_per_article, self.bm25_candidates = per_article, cand_per_article, bm25_candidates
        self.reranker = rerank or (LlamaReranker(rerank_url, rerank_model) if rerank_url else None)
        self.rerank_top, self.rerank_doc_chars, self.rerank_query_chars = rerank_top, rerank_doc_chars, rerank_query_chars
        self.rerank_per_article, self.fusion = rerank_per_article, fusion
        self.last_ms: dict = {}

    def candidates(self, query: str, depth: int | None = None) -> tuple[list[dict], list[dict]]:
        depth = depth or self.depth
        t0 = time.perf_counter()
        b = self.kb.search(query, k=depth, per_article=self.cand_per_article,
                           candidates=max(self.bm25_candidates, 8 * depth)) if self.w_bm25 else []
        t1 = time.perf_counter()
        d = self.dense.search(query, k=depth, per_article=self.cand_per_article, depth=depth * 4) \
            if (self.dense is not None and self.w_dense) else []
        t2 = time.perf_counter()
        self.last_ms = {"bm25": round(1000 * (t1 - t0), 1), "dense": round(1000 * (t2 - t1), 1)}
        return b, d

    def fuse(self, bm25_hits: list[dict], dense_hits: list[dict]) -> list[dict]:
        return rrf_fuse(bm25_hits, dense_hits, self.w_bm25, self.w_dense, self.rrf_k, level=self.fusion)

    def rerank_hits(self, query: str, hits: list[dict], top: int | None = None) -> list[dict]:
        """Rerank the first `top` hits (at most rerank_per_article chunks per article) with the cross-encoder;
        the remaining hits keep their fused order after them."""
        if self.reranker is None or not hits:
            return hits
        top = top or self.rerank_top
        head = cap_per_article(hits, self.rerank_per_article)[:top]
        ids = {id(h) for h in head}
        tail = [h for h in hits if id(h) not in ids]
        t0 = time.perf_counter()
        sc = self.reranker(query[: self.rerank_query_chars], [h["text"][: self.rerank_doc_chars] for h in head])
        self.last_ms["rerank"] = round(1000 * (time.perf_counter() - t0), 1)
        order = sorted(range(len(head)), key=lambda i: -sc[i])
        out = []
        for i in order:
            h = dict(head[i])
            h["rerank_score"] = sc[i]
            h["score"] = sc[i]
            out.append(h)
        return out + tail

    def search(self, query: str, k: int = 8, per_article: int | None = None, rerank: bool | None = None) -> list[dict]:
        per_article = self.per_article if per_article is None else per_article
        b, d = self.candidates(query)
        fused = self.fuse(b, d)
        if (self.reranker is not None) if rerank is None else rerank:
            fused = self.rerank_hits(query, fused)
        return cap_per_article(fused, per_article, k)


def main(argv=None):
    import argparse
    import os

    from kb.dense import DenseIndex
    from kb.search import KB
    ap = argparse.ArgumentParser(description="hybrid BM25 + dense search (+ rerank)")
    ap.add_argument("query", nargs="+")
    ap.add_argument("--index", default=os.environ.get("KB_INDEX_DIR"))
    ap.add_argument("--dense", default=os.environ.get("DENSE_INDEX_DIR"))
    ap.add_argument("--url", default=os.environ.get("DENSE_URL"))
    ap.add_argument("--rerank-url", default=None, help="llama-server --reranking base URL (bge-reranker-v2-m3)")
    ap.add_argument("--w-bm25", type=float, default=1.0)
    ap.add_argument("--w-dense", type=float, default=1.0)
    ap.add_argument("-k", type=int, default=8)
    a = ap.parse_args(argv)
    kb = KB(a.index)
    hy = HybridRetriever(kb, DenseIndex(a.dense, url=a.url, kb=kb), w_bm25=a.w_bm25, w_dense=a.w_dense,
                         rerank_url=a.rerank_url)
    for i, h in enumerate(hy.search(" ".join(a.query), k=a.k), 1):
        print(f"{i}. [{h['score']:.3f}] bm25#{h.get('bm25_rank')} dense#{h.get('dense_rank')} "
              f"{h['title']} — {h['section']}")
    print(hy.last_ms)


if __name__ == "__main__":
    main()
