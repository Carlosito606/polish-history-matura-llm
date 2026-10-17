"""Dense (embedding) retrieval over the KB chunks, next to the BM25 index in kb/search.py.

    from kb.dense import DenseIndex
    di = DenseIndex("kb_data/dense/bge-m3", url="http://127.0.0.1:18096")   # llama-server --embedding --pooling cls
    di.search("Kto był pierwszym koronowanym królem Polski?", k=8)
    # -> [{"title","section","text","score","url","chunk_id"}, ...]   same format as kb.search.KB

Index directory layout (written by kb/dense_build.py):
    meta.json         model preset name, dim, query/doc templates, kb_index dir, build stats
    ids.npy           int32 KB chunk ids (row i of the vectors = chunk ids[i] of kb_data/index store)
    vectors.f16.npy   float16 (N, dim), L2-normalised
    index.faiss       optional FAISS index over the same rows (IVF/HNSW for big N); used when present

Query embedding: llama-server `--embedding` endpoint (POST {url}/v1/embeddings, GGUF model, no torch needed)
or in-process sentence-transformers (backend="st"). The query template of the model preset is applied here,
so callers pass the raw question.
Search backends: "numpy" (fp32 matrix in RAM, brute-force inner product), "torch" (fp16 matrix on CUDA/MPS),
"faiss" (index.faiss), "mmap" (exact, blocked over the fp16 memmap: ~0.5 GB RAM, slow per query, meant for
search_batch()). Default "auto": faiss if index.faiss exists, else torch-cuda if available, else numpy.
"""
from __future__ import annotations

import json
import os
import threading
import time

import numpy as np

QWEN_TASK = "Given a question about history, retrieve Wikipedia passages that answer the question"

# Recommended query/passage formatting per model (model cards).
PRESETS: dict[str, dict] = {
    # Qwen3-Embedding: instruction on the query side only, "Query:" without a space; last-token pooling (+EOS).
    "qwen3-emb-0.6b": {"hf": "Qwen/Qwen3-Embedding-0.6B",
                       "gguf": "Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf",
                       "query_tpl": "Instruct: " + QWEN_TASK + "\nQuery:{q}", "doc_tpl": "{d}", "dim": 1024},
    # BGE-M3 dense: no prefixes, CLS pooling.
    "bge-m3": {"hf": "BAAI/bge-m3", "gguf": "gpustack/bge-m3-GGUF/bge-m3-Q8_0.gguf",
               "query_tpl": "{q}", "doc_tpl": "{d}", "dim": 1024},
    # MMLW (sdadas): queries prefixed with "zapytanie: ", passages as-is.
    "mmlw-roberta-large": {"hf": "sdadas/mmlw-retrieval-roberta-large",
                           "query_tpl": "zapytanie: {q}", "doc_tpl": "{d}", "dim": 1024},
    # multilingual-e5-large-instruct: "Instruct: ...\nQuery: " on queries, passages as-is.
    "e5-large-instruct": {"hf": "intfloat/multilingual-e5-large-instruct",
                          "query_tpl": "Instruct: Given a question, retrieve Wikipedia passages that answer the "
                                       "question\nQuery: {q}", "doc_tpl": "{d}", "dim": 1024},
}


def _norm(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, np.float32)
    n = np.linalg.norm(x, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return x / n


class LlamaEmbedder:
    """Client for llama-server --embedding (OpenAI-compatible /v1/embeddings). Thread-safe."""

    def __init__(self, url: str, model: str = "emb", timeout: float | None = None, max_chars: int = 2400):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout or float(os.environ.get("DENSE_TIMEOUT", "120"))
        self.max_chars = max_chars
        self._client = None
        self._lock = threading.Lock()

    def _c(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    import httpx
                    self._client = httpx.Client(timeout=self.timeout,
                                                limits=httpx.Limits(max_connections=32, max_keepalive_connections=16))
        return self._client

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), np.float32)
        inp = [t[: self.max_chars] if self.max_chars else t for t in texts]
        r = self._c().post(self.url + "/v1/embeddings", json={"model": self.model, "input": inp})
        r.raise_for_status()
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        return _norm(np.array([d["embedding"] for d in data], np.float32))


class STEmbedder:
    """In-process sentence-transformers encoder (CUDA fp16 / MPS / CPU)."""

    def __init__(self, model: str, device: str | None = None, max_seq_length: int = 512, batch_size: int = 32):
        import torch  # type: ignore
        from sentence_transformers import SentenceTransformer  # type: ignore
        if device is None:
            device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        if device == "cuda" and os.environ.get("DENSE_VRAM_GB"):   # stay inside a shared GPU's budget
            tot = torch.cuda.get_device_properties(0).total_memory / 2**30
            torch.cuda.set_per_process_memory_fraction(min(1.0, float(os.environ["DENSE_VRAM_GB"]) / tot))
        kw = {"model_kwargs": {"torch_dtype": torch.float16}} if device in ("cuda", "mps") else {}
        self.m = SentenceTransformer(model, device=device, **kw)
        self.m.max_seq_length = max_seq_length
        self.batch_size = batch_size

    def embed(self, texts: list[str]) -> np.ndarray:
        v = self.m.encode(texts, batch_size=self.batch_size, normalize_embeddings=True, convert_to_numpy=True,
                          show_progress_bar=False)
        return np.asarray(v, np.float32)


def make_embedder(preset: str, url: str | None = None, backend: str | None = None, model_path: str | None = None,
                  **kw):
    """backend "llama" (needs url) or "st"; model_path = local HF dir overriding the preset's hub id."""
    backend = backend or ("llama" if url else "st")
    if backend == "llama":
        if not url:
            raise ValueError("llama backend needs url (llama-server --embedding)")
        return LlamaEmbedder(url, **kw)
    return STEmbedder(model_path or os.environ.get("DENSE_MODEL_PATH")
                      or (PRESETS[preset]["hf"] if preset in PRESETS else preset), **kw)


def format_query(preset: str, q: str) -> str:
    return PRESETS.get(preset, {}).get("query_tpl", "{q}").replace("{q}", q)


def format_doc(preset: str, d: str) -> str:
    return PRESETS.get(preset, {}).get("doc_tpl", "{d}").replace("{d}", d)


class DenseIndex:
    def __init__(self, index_dir: str, url: str | None = None, backend: str | None = None,
                 kb=None, kb_index_dir: str | None = None, search_backend: str = "auto",
                 device: str | None = None, nprobe: int = 64, per_article: int = 3):
        self.dir = index_dir
        with open(os.path.join(index_dir, "meta.json"), encoding="utf-8") as f:
            self.meta = json.load(f)
        self.preset = self.meta["preset"]
        self.ids = np.asarray(np.load(os.path.join(index_dir, "ids.npy"), mmap_mode="r"), np.int64)
        self.per_article = per_article
        url = url or os.environ.get("DENSE_URL") or self.meta.get("url")
        if backend is None:
            backend = "llama" if url else "st"
        self.embedder = make_embedder(self.preset, url=url, backend=backend,
                                      model_path=self.meta.get("model_path") if backend == "st" else None)
        if kb is None:
            from kb.search import KB
            kb = KB(kb_index_dir or os.environ.get("KB_INDEX_DIR") or self.meta.get("kb_index"))
        self.kb = kb
        fpath = os.path.join(index_dir, "index.faiss")
        if search_backend == "auto":
            if os.path.exists(fpath):
                search_backend = "faiss"
            else:
                search_backend = "numpy"
                try:
                    import torch  # type: ignore
                    if torch.cuda.is_available():
                        search_backend = "torch"
                except Exception:
                    pass
        self.search_backend = search_backend
        vec = np.load(os.path.join(index_dir, "vectors.f16.npy"), mmap_mode="r")
        if search_backend == "faiss":
            import faiss  # type: ignore
            self.faiss = faiss.read_index(fpath)
            try:
                faiss.extract_index_ivf(self.faiss).nprobe = nprobe
            except Exception:
                pass
            self.mat = None
        elif search_backend == "torch":
            import torch  # type: ignore
            dev = device or ("cuda" if torch.cuda.is_available() else "mps")
            self.mat = torch.from_numpy(np.ascontiguousarray(vec)).to(dev)
            self._torch_dev = dev
        elif search_backend == "mmap":
            self.mat = vec
        else:
            self.mat = np.ascontiguousarray(vec, dtype=np.float32)
        self.last_ms = {}

    def __len__(self) -> int:
        return len(self.ids)

    def embed_query(self, query: str) -> np.ndarray:
        return self.embedder.embed([format_query(self.preset, query)])[0]

    def search_vec(self, qv: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        """-> (scores, row indices) for the top-k rows (best first)."""
        k = min(k, len(self.ids))
        if self.search_backend == "faiss":
            D, I = self.faiss.search(np.asarray(qv, np.float32)[None, :], k)
            m = I[0] >= 0
            return D[0][m], I[0][m]
        if self.search_backend == "torch":
            import torch  # type: ignore
            q = torch.from_numpy(np.asarray(qv, np.float16)).to(self._torch_dev)
            s = self.mat @ q
            v, i = torch.topk(s.float(), k)
            return v.cpu().numpy(), i.cpu().numpy()
        if self.search_backend == "mmap":
            S, I = self.search_batch(np.asarray(qv, np.float32)[None, :], k)
            return S[0], I[0]
        s = self.mat @ np.asarray(qv, np.float32)
        top = np.argpartition(-s, k - 1)[:k]
        top = top[np.argsort(-s[top])]
        return s[top], top

    def search_batch(self, Q: np.ndarray, k: int, block: int = 131072) -> tuple[np.ndarray, np.ndarray]:
        """Exact top-k for many query vectors in one pass over the vectors -> (scores, rows), each (nq, k)."""
        if self.search_backend != "mmap":
            out = [self.search_vec(q, k) for q in Q]
            return np.stack([o[0] for o in out]), np.stack([o[1] for o in out])
        Q = np.asarray(Q, np.float32)
        k = min(k, len(self.ids))
        best_s = np.full((len(Q), 0), -np.inf, np.float32)
        best_i = np.zeros((len(Q), 0), np.int64)
        for s0 in range(0, len(self.ids), block):
            sc = Q @ np.asarray(self.mat[s0:s0 + block], np.float32).T
            kk = min(k, sc.shape[1])
            part = np.argpartition(-sc, kk - 1, axis=1)[:, :kk]
            cs = np.concatenate([best_s, np.take_along_axis(sc, part, 1)], 1)
            ci = np.concatenate([best_i, part + s0], 1)
            keep = np.argpartition(-cs, min(k, cs.shape[1]) - 1, axis=1)[:, :k]
            best_s, best_i = np.take_along_axis(cs, keep, 1), np.take_along_axis(ci, keep, 1)
        o = np.argsort(-best_s, axis=1)
        return np.take_along_axis(best_s, o, 1), np.take_along_axis(best_i, o, 1)

    def search(self, query: str, k: int = 8, per_article: int | None = None, depth: int | None = None) -> list[dict]:
        t0 = time.perf_counter()
        qv = self.embed_query(query)
        t1 = time.perf_counter()
        out = self.search_records(qv, k, per_article, depth)
        self.last_ms = {"embed": round(1000 * (t1 - t0), 1), "search": round(1000 * (time.perf_counter() - t1), 1)}
        return out

    def search_records(self, qv: np.ndarray, k: int = 8, per_article: int | None = None,
                       depth: int | None = None) -> list[dict]:
        """Top-k KB records (kb.search.KB dicts + score, chunk_id) for an already embedded query vector,
        at most `per_article` chunks per article among the first `depth` rows."""
        per_article = self.per_article if per_article is None else per_article
        depth = depth or max(k * 4, 50)
        scores, rows = self.search_vec(qv, depth)
        out, seen = [], {}
        for s, r in zip(scores, rows):
            cid = int(self.ids[int(r)])
            art = int(self.kb.chunk_article[cid])
            if per_article and seen.get(art, 0) >= per_article:
                continue
            seen[art] = seen.get(art, 0) + 1
            rec = self.kb._record(cid)
            rec["score"] = float(s)
            rec["chunk_id"] = cid
            out.append(rec)
            if len(out) >= k:
                break
        return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="dense search over plwiki chunks")
    ap.add_argument("query", nargs="+")
    ap.add_argument("--dense", default=os.environ.get("DENSE_INDEX_DIR"), help="dense index dir")
    ap.add_argument("--url", default=os.environ.get("DENSE_URL"), help="llama-server --embedding base URL")
    ap.add_argument("--index", default=os.environ.get("KB_INDEX_DIR"), help="KB (BM25) index dir, for the records")
    ap.add_argument("-k", type=int, default=8)
    a = ap.parse_args(argv)
    di = DenseIndex(a.dense, url=a.url, kb_index_dir=a.index)
    for i, h in enumerate(di.search(" ".join(a.query), k=a.k), 1):
        print(f"{i}. [{h['score']:.3f}] {h['title']} — {h['section']}")
        print("   " + h["text"].replace("\n", " ")[:240])
    print(di.last_ms)


if __name__ == "__main__":
    main()
