"""Retrieval: multi-query BM25 via kb.search.KB, reciprocal-rank fusion, token budget.
DENSE=1 adds a dense (bge-m3) list for the whole question, fused with the BM25 pool at article level
before the optional reranker (hybrid_scores).

Falls back to no-context mode if the kb package or index is missing (logged once).
"""
from __future__ import annotations

import dataclasses
import logging
import os
import re
import threading
import time

from .config import Settings
from .qtype import ParsedQuestion, entities, strip_boilerplate

log = logging.getLogger("harness.retrieval")

DEFAULT_INDEX_CANDIDATES = ["kb_data/index", "kb_data/index_full", "kb_data/index_mini"]
DEFAULT_DENSE_CANDIDATES = ["kb_data/dense/bge-m3"]


class Retriever:
    def __init__(self, settings: Settings):
        self.kb = None
        self.index_dir = None
        self.error = None
        self._lock = threading.Lock()
        self.reranker = None
        self.dense = None          # kb.dense.DenseIndex, loaded on first DENSE=1 use (or at start with DENSE=1)
        self.dense_error = None
        self.dense_dir = None
        self._dense_lock = threading.Lock()
        self._qv_cache: dict[str, object] = {}
        self.dense_calls, self.dense_ms, self.dense_errors = 0, 0.0, 0
        if not settings.use_kb:
            self.error = "disabled (USE_KB=0)"
            return
        cands = [settings.kb_index_dir] if settings.kb_index_dir else DEFAULT_INDEX_CANDIDATES
        idx = next((c for c in cands if c and os.path.exists(c)), None)
        if idx is None:
            self.error = f"no index dir found (tried {cands})"
            log.warning("KB unavailable: %s -> no-context mode", self.error)
            return
        try:
            from kb.search import KB  # type: ignore
            t = time.time()
            self.kb = KB(idx)
            self.index_dir = idx
            log.info("KB loaded from %s in %.1fs", idx, time.time() - t)
        except Exception as e:  # pragma: no cover
            self.error = f"{type(e).__name__}: {e}"
            log.warning("KB load failed (%s) -> no-context mode", self.error)
        self.reranker = Reranker(settings)  # lazy: nothing is contacted until RERANK=1 is used
        if self.kb is not None and settings.dense:
            self.dense_ready(settings)

    @property
    def available(self) -> bool:
        return self.kb is not None

    def status(self) -> dict:
        return {"available": self.available, "index_dir": self.index_dir, "error": self.error,
                "reranker": self.reranker.status() if self.reranker else None,
                "dense": {"loaded": self.dense is not None, "dir": self.dense_dir, "error": self.dense_error,
                          "backend": getattr(self.dense, "search_backend", None),
                          "n": len(self.dense) if self.dense is not None else 0,
                          "calls": self.dense_calls, "errors": self.dense_errors,
                          "avg_ms": round(self.dense_ms / self.dense_calls, 1) if self.dense_calls else None}}

    def dense_ready(self, settings: Settings) -> bool:
        """Load the dense index once (DENSE=1). A failed load is logged once and DENSE falls back to BM25 only."""
        if self.dense is not None:
            return True
        if self.kb is None or self.dense_error:
            return False
        with self._dense_lock:
            if self.dense is None and not self.dense_error:
                cands = [settings.dense_index_dir] if settings.dense_index_dir else DEFAULT_DENSE_CANDIDATES
                d = next((c for c in cands if c and os.path.exists(os.path.join(c, "meta.json"))), None)
                if d is None:
                    self.dense_error = f"no dense index found (tried {cands})"
                    log.warning("DENSE unavailable: %s -> BM25 only", self.dense_error)
                    return False
                try:
                    from kb.dense import DenseIndex  # type: ignore
                    t = time.time()
                    self.dense = DenseIndex(d, url=settings.dense_url, backend="llama", kb=self.kb,
                                            search_backend=settings.dense_search, nprobe=settings.dense_nprobe,
                                            per_article=settings.dense_per_article)
                    self.dense_dir = d
                    if self.dense.search_backend == "faiss" and settings.dense_faiss_threads > 0:
                        import faiss  # type: ignore  # one thread per query: requests already run in parallel
                        faiss.omp_set_num_threads(settings.dense_faiss_threads)
                    log.info("dense index %s (%d rows, %s) loaded in %.1fs", d, len(self.dense),
                             self.dense.search_backend, time.time() - t)
                except Exception as e:  # pragma: no cover
                    self.dense_error = f"{type(e).__name__}: {e}"
                    log.warning("dense index load failed (%s) -> BM25 only", self.dense_error)
        return self.dense is not None

    def dense_search(self, query: str, settings: Settings) -> list[dict]:
        """Dense top-k chunks for the whole question ([] on any failure: the caller then keeps BM25 only)."""
        q = " ".join(query.split())[: settings.dense_query_chars]
        if not q or not self.dense_ready(settings):
            return []
        t = time.time()
        try:
            qv = self._qv_cache.get(q)
            if qv is None:
                qv = self.dense.embed_query(q)
                if len(self._qv_cache) > 4096:
                    self._qv_cache.clear()
                self._qv_cache[q] = qv
            out = self.dense.search_records(qv, settings.dense_k, settings.dense_per_article,
                                            max(settings.dense_depth, settings.dense_k))
        except Exception as e:
            self.dense_errors += 1
            log.warning("dense search failed (%s: %s) -> BM25 only", type(e).__name__, e)
            return []
        self.dense_calls += 1
        self.dense_ms += (time.time() - t) * 1000
        return out

    def search(self, query: str, k: int) -> list[dict]:
        if not self.kb or not query.strip():
            return []
        with self._lock:
            try:
                return list(self.kb.search(query, k) or [])
            except Exception as e:  # pragma: no cover
                log.warning("KB search failed for %r: %s", query[:80], e)
                return []


_IMG_DESC = re.compile(r"\[Opis obrazu[^\]]*\]")


def strip_image_desc(text: str) -> str:
    """Machine-written image descriptions stay in the prompt but not in retrieval queries: their
    occasional invented names/dates pulled wrong articles into the context (mock 3, 19; 26.09).
    IMG_DESC_NO_QUERY=0 restores the old behaviour."""
    if not text or os.environ.get("IMG_DESC_NO_QUERY", "1") == "0":
        return text
    return " ".join(_IMG_DESC.sub(" ", text).split(" ")).strip()


def build_queries(pq: ParsedQuestion, v2: bool = False) -> list[tuple[str, str, float]]:
    """Returns (name, query, weight). 'item' queries get a guaranteed slot in the context.
    v2 (QTYPE_V2): abcd_parts sentences/options."""
    stem = strip_image_desc(strip_boilerplate(pq.stem) or strip_boilerplate(pq.text))
    qs: list[tuple[str, str, float]] = [("stem", stem, 1.0)]
    short_stem = " ".join(stem.split()[:30])
    if pq.qtype in ("abcd", "abj"):
        for l, o in pq.options:
            if o:
                qs.append((f"opt:{l}", f"{short_stem} {o}", 1.0))
        for l, o in pq.justifications:
            if o:
                qs.append((f"just:{l}", o, 0.7))
    elif pq.qtype == "pf":
        for l, s in pq.statements:
            qs.append((f"item:{l}", s, 1.0))
    elif pq.qtype == "chrono":
        for l, s in pq.items:
            qs.append((f"item:{l}", s, 1.0))
    elif pq.qtype == "match":
        for l, s in pq.left:
            qs.append((f"item:{l}", s, 1.0))
        for l, s in pq.right:
            qs.append((f"right:{l}", s, 0.6))
    elif pq.qtype == "abcd_parts":
        for pl, ptxt, opts in pq.parts:
            qs.append((f"item:{pl}", ptxt, 1.0))
            for l, o in opts:
                if o:
                    qs.append((f"popt:{pl}{l}", f"{ptxt} {o}", 0.6))
    ents = entities(pq.text)
    if ents:
        qs.append(("ents", " ".join(ents[:12]), 0.6))
    # (v2: sources already feed the stem query; a separate 'src' query pulled in citation noise -> removed)
    # dedupe identical queries
    seen, out = set(), []
    for name, q, w in qs:
        k = q.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append((name, q, w))
    return out


def _key(h: dict) -> str:
    return f"{h.get('title', '')}|{h.get('section', '')}|{(h.get('text') or '')[:160]}"


def _rrf(results: list[tuple[str, float, list[dict]]], rrf_k: int = 60) -> tuple[dict, dict]:
    scores: dict[str, float] = {}
    hits: dict[str, dict] = {}
    for name, w, hs in results:
        for rank, h in enumerate(hs):
            k = _key(h)
            scores[k] = scores.get(k, 0.0) + w / (rrf_k + rank + 1)
            if k not in hits:
                hits[k] = dict(h)
                hits[k]["_q"] = [name]
            else:
                hits[k].setdefault("_q", []).append(name)
    return scores, hits


def base_order(results, scores: dict) -> list[str]:
    """Guaranteed best hit of each per-item/option query (rank 0), then RRF order."""
    order: list[str] = []
    for name, w, hs in results:
        if (name.startswith("item:") or name.startswith("opt:")) and hs:
            k = _key(hs[0])
            if k not in order:
                order.append(k)
    for k in sorted(scores, key=lambda x: -scores[x]):
        if k not in order:
            order.append(k)
    return order


def pack(order: list[str], hits: dict, scores: dict, settings: Settings, keep: int,
         rr: dict | None = None) -> list[dict]:
    """Take chunks in `order` within the token budget, at most `keep`."""
    budget_chars = int(settings.ctx_tokens * settings.chars_per_token)
    out, used = [], 0
    for k in order:
        h = hits[k]
        txt = (h.get("text") or "").strip()
        if len(txt) > settings.chunk_max_chars:
            txt = txt[: settings.chunk_max_chars].rsplit(" ", 1)[0] + " …"
        cost = len(txt) + len(h.get("title", "")) + 20
        if used + cost > budget_chars and out:
            continue
        c = {"title": h.get("title", ""), "section": h.get("section", ""), "text": txt,
             "url": h.get("url", ""), "score": float(h.get("score", 0.0) or 0.0),
             "rrf": round(scores.get(k, 0.0), 5), "queries": h.get("_q", [])}
        if rr is not None and k in rr:
            c["rerank"] = round(rr[k], 4)
        out.append(c)
        used += cost
        if len(out) >= keep:
            break
    return out


def hybrid_scores(scores: dict, hits: dict, dense_hits: list[dict], settings: Settings) -> dict:
    """Article-level RRF of the BM25 pool (its chunk-RRF order) and the dense list (DENSE=1).

    score(article) = 1/(k + r_bm25) + DENSE_WEIGHT/(k + r_dense) over each list's distinct articles (ranks from 1).
    Chunks are ordered by their article's score, then by chunk-level RRF (dense adds DENSE_WEIGHT/(k + rank)),
    with at most DENSE_CAND_PER_ARTICLE chunks per article in the head and the rest after it. Dense chunks join
    `hits` (query name "dense"). Returns a new score dict whose descending order is that fused order (rank-RRF
    values), so rerank_order / base_order / pack work unchanged. Chunk-level fusion lost 3-6 R@5 points
    (docs/dense_retrieval.md)."""
    rk, w = settings.dense_rrf_k, settings.dense_weight
    art: dict[str, float] = {}
    seen: set[str] = set()
    for k in sorted(scores, key=lambda x: -scores[x]):
        t = hits[k].get("title", "")
        if t not in seen:
            seen.add(t)
            art[t] = art.get(t, 0.0) + 1.0 / (rk + len(seen))
    chunk = dict(scores)
    seen = set()
    for r, h in enumerate(dense_hits, 1):
        k = _key(h)
        chunk[k] = chunk.get(k, 0.0) + w / (rk + r)
        if k not in hits:
            hits[k] = dict(h)
            hits[k]["_q"] = ["dense"]
        else:
            hits[k].setdefault("_q", []).append("dense")
        t = h.get("title", "")
        if t not in seen:
            seen.add(t)
            art[t] = art.get(t, 0.0) + w / (rk + len(seen))
    ordered = sorted(chunk, key=lambda x: (-art.get(hits[x].get("title", ""), 0.0), -chunk[x]))
    cap = settings.dense_cand_per_article
    head, tail, n = [], [], {}
    for k in ordered:
        t = hits[k].get("title", "")
        if cap and n.get(t, 0) >= cap:
            tail.append(k)
        else:
            n[t] = n.get(t, 0) + 1
            head.append(k)
    return {k: 1.0 / (rk + i + 1) for i, k in enumerate(head + tail)}


def union_scores(scores: dict, hits: dict, dense_hits: list[dict], settings: Settings) -> tuple[dict, int]:
    """DENSE_MODE=union: the BM25 top RERANK_TOPN keep their order; the first DENSE_UNION_K dense chunks that are
    not among them follow; then the rest of the BM25 pool. Returns (score dict in that order, n dense added)."""
    rk = settings.dense_rrf_k
    order = sorted(scores, key=lambda x: -scores[x])
    head, rest = order[: settings.rerank_topn], order[settings.rerank_topn:]
    inhead = set(head)
    extra = []
    for h in dense_hits:
        k = _key(h)
        if k in inhead or k in extra:
            continue
        if k not in hits:
            hits[k] = dict(h)
            hits[k]["_q"] = ["dense"]
        else:
            hits[k].setdefault("_q", []).append("dense")
        extra.append(k)
        if len(extra) >= settings.dense_union_k:
            break
    ex = set(extra)
    full = head + extra + [k for k in rest if k not in ex]
    return {k: 1.0 / (rk + i + 1) for i, k in enumerate(full)}, len(extra)


def fuse(results: list[tuple[str, float, list[dict]]], settings: Settings, rrf_k: int = 60) -> list[dict]:
    """RRF fusion with a guaranteed top-1 slot for each item/option query, within token budget."""
    scores, hits = _rrf(results, rrf_k)
    return pack(base_order(results, scores), hits, scores, settings, settings.top_k)


# ----------------------------------------------------------------------------- reranker (RERANK=1)
class Reranker:
    """Cross-encoder relevance scores. backend 'llama': llama-server --reranking (POST /v1/rerank,
    bge-reranker-v2-m3 GGUF, 0.6 GB); backend 'st': sentence-transformers CrossEncoder (RERANK_ST_MODEL,
    MPS/CUDA/CPU) -- fallback, needs torch + the model in the local HF cache (HF_HUB_OFFLINE=1)."""

    def __init__(self, settings: Settings):
        self.backend = settings.rerank_backend
        self.url = settings.rerank_url
        self.model = settings.rerank_model
        self.timeout = settings.rerank_timeout
        self._client = None
        self._st = None
        self._lock = threading.Lock()
        self.calls, self.ms, self.errors = 0, 0.0, 0

    def status(self) -> dict:
        return {"backend": self.backend, "url": self.url, "calls": self.calls, "errors": self.errors,
                "avg_ms": round(self.ms / self.calls, 1) if self.calls else None}

    def score(self, query: str, docs: list[str]) -> list[float]:
        if not docs:
            return []
        t = time.time()
        try:
            out = self._score_st(query, docs) if self.backend == "st" else self._score_llama(query, docs)
        except Exception:
            self.errors += 1
            raise
        self.calls += 1
        self.ms += (time.time() - t) * 1000
        return out

    def _score_llama(self, query: str, docs: list[str]) -> list[float]:
        import httpx
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = httpx.Client(timeout=self.timeout,
                                                limits=httpx.Limits(max_connections=32, max_keepalive_connections=16))
        r = self._client.post(self.url + "/v1/rerank",
                              json={"model": self.model, "query": query, "documents": docs, "top_n": len(docs)})
        r.raise_for_status()
        scores = [float("-inf")] * len(docs)
        for x in r.json().get("results") or []:
            scores[int(x["index"])] = float(x.get("relevance_score", x.get("score", 0.0)))
        return scores

    def _score_st(self, query: str, docs: list[str]) -> list[float]:
        with self._lock:
            if self._st is None:
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
                import torch  # type: ignore
                from sentence_transformers import CrossEncoder  # type: ignore
                dev = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
                self._st = CrossEncoder(os.environ.get("RERANK_ST_MODEL", "BAAI/bge-reranker-v2-m3"),
                                        device=dev, max_length=512)
            return [float(x) for x in self._st.predict([(query, d) for d in docs], batch_size=16)]


def rerank_query(pq: ParsedQuestion, max_chars: int = 900) -> str:
    """Query text for the cross-encoder: the (command) stem + options/statements/items, then sources."""
    parts = [strip_boilerplate(pq.command) if pq.sources else (strip_boilerplate(pq.stem) or strip_boilerplate(pq.text))]
    if pq.qtype in ("abcd", "abj"):
        parts += [o for _, o in pq.options if o]
    elif pq.qtype == "pf":
        parts += [x for _, x in pq.statements]
    elif pq.qtype == "chrono":
        parts += [x for _, x in pq.items]
    elif pq.qtype in ("match", "abcd_parts"):
        parts += [x for _, x in pq.left]
    q = " ".join(" ".join(parts).split())
    if pq.sources and len(q) < max_chars - 50:
        q += " " + " ".join(pq.sources.split())[: max_chars - len(q)]
    return q[:max_chars]


def _doc(h: dict, n: int) -> str:
    head = h.get("title", "") + (f" — {h['section']}" if h.get("section") else "")
    return f"{head}\n{(h.get('text') or '')[:n]}"


def rerank_order(results, queries, scores: dict, hits: dict, settings: Settings, reranker: Reranker,
                 rq: str) -> tuple[list[str], dict]:
    """Rerank the top RERANK_TOPN RRF candidates against the whole question; with RERANK_ITEM_SLOTS each
    per-item query (pf statement / chrono item / match left item / parts sentence) first gets its own
    best chunk, chosen by the cross-encoder among that query's top-6 BM25 hits."""
    from concurrent.futures import ThreadPoolExecutor
    cand = sorted(scores, key=lambda x: -scores[x])[: settings.rerank_topn]
    jobs = []  # (item sub-candidates, query) -- sent concurrently with the global call (server -np batches them)
    if settings.rerank_item_slots:
        qtext = {name: q for name, q, _ in queries}
        for name, w, hs in results:
            if name.startswith("item:") and hs:
                jobs.append((list(dict.fromkeys(_key(h) for h in hs[:6])), qtext.get(name, rq)[:600]))
    n = settings.rerank_doc_chars
    with ThreadPoolExecutor(max_workers=1 + min(8, len(jobs))) as ex:
        fg = ex.submit(reranker.score, rq, [_doc(hits[k], n) for k in cand])
        fj = [ex.submit(reranker.score, q, [_doc(hits[k], n) for k in sub]) for sub, q in jobs]
        rr = dict(zip(cand, fg.result()))
        order: list[str] = []
        for (sub, _), f in zip(jobs, fj):
            sc = f.result()
            best = max(zip(sc, range(len(sub))))[1]
            if sub[best] not in order:
                order.append(sub[best])
    for k in sorted(rr, key=lambda x: -rr[x]):
        if k not in order:
            order.append(k)
    return order, rr


def _title_on(settings: Settings, pq: ParsedQuestion) -> bool:
    """V4_TITLE_RESCORE (harness/v4.py); never for essays."""
    from . import v4
    return pq.qtype != "essay" and v4.on(settings, "v4_title_rescore")


def _title_order(order: list[str], hits: dict, rr: dict | None, pq: ParsedQuestion, settings: Settings,
                 title_ref: str | None) -> list[str]:
    from . import v4
    ref = title_ref if title_ref is not None else v4.default_title_ref(pq)
    new, _ = v4.title_rescore(order, hits, rr, ref, settings.v4_title_bonus, settings.v4_title_penalty)
    return new


def retrieve(retriever: Retriever, pq: ParsedQuestion, settings: Settings,
             queries: list[tuple[str, str, float]] | None = None,
             extra_queries: list[tuple[str, str, float]] | None = None,
             rq: str | None = None, title_ref: str | None = None,
             ) -> tuple[list[dict], list[tuple[str, str, float]]]:
    """rq: reranker query (None = rerank_query(pq)); title_ref: text the V4 title re-scoring matches titles against
    (None = harness.v4.default_title_ref(pq)). Both only matter for harness v4."""
    if not retriever.available:
        return [], []
    queries = list(queries or build_queries(pq, v2=settings.qtype_v2))
    if extra_queries:  # QUERY_REWRITE
        seen = {q.strip().lower() for _, q, _ in queries}
        queries += [x for x in extra_queries if x[1].strip() and x[1].strip().lower() not in seen]
    use_rr = settings.rerank and retriever.reranker is not None and (
        not settings.rerank_types or pq.qtype in {t.strip() for t in settings.rerank_types.split(",")})
    k = max(settings.per_query_k, settings.rerank_per_query_k) if use_rr else settings.per_query_k
    results = [(name, w, retriever.search(q, k)) for name, q, w in queries]
    # DENSE=1: one dense list for the whole question (same for every call of this question -> embedding cached)
    dense_hits = retriever.dense_search(strip_boilerplate(pq.text) or pq.text, settings) if settings.dense else []
    if use_rr:
        try:
            scores, hits = _rrf(results)
            rs = settings
            if dense_hits and settings.dense_mode == "union":
                scores, extra = union_scores(scores, hits, dense_hits, settings)
                rs = dataclasses.replace(settings, rerank_topn=settings.rerank_topn + extra)
            elif dense_hits:
                scores = hybrid_scores(scores, hits, dense_hits, settings)
            order, rr = rerank_order(results, queries, scores, hits, rs, retriever.reranker,
                                     rq if rq is not None else rerank_query(pq))
            if _title_on(settings, pq):
                order = _title_order(order, hits, rr, pq, settings, title_ref)
            return pack(order, hits, scores, settings, settings.rerank_keep or settings.top_k, rr), queries
        except Exception as e:
            log.warning("rerank failed (%s: %s) -> BM25/RRF order", type(e).__name__, e)
            results = [(n, w, hs[: settings.per_query_k]) for n, w, hs in results]
    if dense_hits:
        scores, hits = _rrf(results)
        scores = hybrid_scores(scores, hits, dense_hits, settings)
        order = base_order(results, scores)
        if _title_on(settings, pq):
            order = _title_order(order, hits, None, pq, settings, title_ref)
        return pack(order, hits, scores, settings, settings.top_k), queries
    if _title_on(settings, pq):
        scores, hits = _rrf(results)
        order = _title_order(base_order(results, scores), hits, None, pq, settings, title_ref)
        return pack(order, hits, scores, settings, settings.top_k), queries
    return fuse(results, settings), queries


_WS = re.compile(r"\s+")


def approx_tokens(s: str, cpt: float = 3.3) -> int:
    return int(len(_WS.sub(" ", s)) / cpt)
