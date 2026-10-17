"""Lexical (BM25) retrieval over Polish Wikipedia chunks. No neural models.

Interface used by the harness:
    from kb.search import KB
    kb = KB(index_dir)                  # or KB() -> $KB_INDEX_DIR
    hits = kb.search("W którym roku podpisano pokój w Oliwie?", k=8)
    # -> [{"title","section","text","score","url"}, ...]

CLI:
    python -m kb.search --index DIR "zapytanie" [-k 8] [--json]

Scoring = BM25(chunk) + alpha * BM25(article: title x2 + redirects + headings + lead)
          + beta * log1p(incoming_links) + gamma * title_coverage(query, article title)
Candidates = top chunks by chunk BM25  U  best chunks of the top articles by article BM25.
At most `per_article` chunks per article in the output.
All index arrays are numpy memmaps -> fast startup, RSS grows only with touched pages.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import re

import numpy as np

SEP, NL, TAB = chr(31), chr(10), chr(9)
_PAREN = re.compile(r"\s*\([^)]*\)")

try:  # works both as `python -m kb.search` and when kb/ is on sys.path
    from kb.textnorm import Tokenizer
except ImportError:  # pragma: no cover
    from textnorm import Tokenizer


class _BM25:
    def __init__(self, prefix: str, maxb: int):
        self.indptr = np.load(prefix + ".indptr.npy", mmap_mode="r")
        self.indices = np.load(prefix + ".indices.npy", mmap_mode="r")
        self.weights = np.load(prefix + ".weights.npy", mmap_mode="r")
        self.vocab = np.load(prefix + ".vocab.npy", mmap_mode="r")
        self.maxb = maxb

    def term_ids(self, toks: list[str]) -> list[int]:
        out = []
        V = len(self.vocab)
        for t in dict.fromkeys(toks):  # unique, keep order
            b = t.encode("utf-8")[: self.maxb]
            i = int(np.searchsorted(self.vocab, b))
            if i < V and self.vocab[i] == b:
                out.append(i)
        return out

    def scores(self, tids: list[int], n: int, max_postings: int = 3_000_000, max_terms: int = 32) -> np.ndarray:
        acc = np.zeros(n, np.float32)
        # rarest (highest-idf) terms first; long queries keep only the `max_terms` rarest terms and
        # terms with > max_postings postings are skipped (they carry ~no idf) -> bounded latency
        spans = sorted(((int(self.indptr[t]), int(self.indptr[t + 1])) for t in tids), key=lambda s: s[1] - s[0])
        for a, b in spans[:max_terms]:
            if b - a > max_postings:
                continue
            acc[self.indices[a:b]] += self.weights[a:b]
        return acc


class KB:
    def __init__(self, index_dir: str | None = None, alpha: float = 0.35, beta: float = 0.4,
                 gamma: float = 10.0, per_article: int = 3):
        index_dir = index_dir or os.environ.get("KB_INDEX_DIR")
        if not index_dir:
            raise ValueError("index_dir not given and KB_INDEX_DIR not set")
        self.dir = index_dir
        with open(os.path.join(index_dir, "tokenizer.json"), encoding="utf-8") as f:
            self.meta = json.load(f)
        self.tk = Tokenizer.from_config(self.meta["tokenizer"])
        maxb = self.meta.get("maxb", 16)
        self.cidx = _BM25(os.path.join(index_dir, "chunks"), maxb)
        self.aidx = _BM25(os.path.join(index_dir, "articles"), maxb)
        self.store = np.memmap(os.path.join(index_dir, "store.bin"), dtype=np.uint8, mode="r")
        self.store_off = np.load(os.path.join(index_dir, "store_off.npy"), mmap_mode="r")
        self.chunk_article = np.load(os.path.join(index_dir, "chunk_article.npy"), mmap_mode="r")
        self.art_inl = np.load(os.path.join(index_dir, "art_inlinks.npy"), mmap_mode="r")
        self.n_chunks = len(self.store_off) - 1
        self.n_articles = len(self.art_inl)
        self.art_first = np.load(os.path.join(index_dir, "art_first_chunk.npy"), mmap_mode="r")
        self.art_store = np.memmap(os.path.join(index_dir, "art_store.bin"), dtype=np.uint8, mode="r")
        self.art_off = np.load(os.path.join(index_dir, "art_off.npy"), mmap_mode="r")
        self.a_idf = np.load(os.path.join(index_dir, "articles.idf.npy"), mmap_mode="r")
        self.alpha, self.beta, self.gamma, self.per_article = alpha, beta, gamma, per_article
        self._art_prior = None
        self._tcache: dict = {}
        self._redirects = None

    # ---- records -------------------------------------------------------
    def _record(self, i: int) -> dict:
        a, b = int(self.store_off[i]), int(self.store_off[i + 1])
        title, section, text, url = bytes(self.store[a:b]).decode("utf-8").split(SEP)
        return {"title": title, "section": section, "text": text, "url": url}

    def article_title(self, art: int) -> str:
        a, b = int(self.art_off[art]), int(self.art_off[art + 1])
        return bytes(self.art_store[a:b]).decode("utf-8").split(SEP, 1)[0]

    def _prior(self) -> np.ndarray:
        if self._art_prior is None:
            self._art_prior = np.log1p(np.asarray(self.art_inl, np.float32))
        return self._art_prior

    def _title_cov(self, art: int, qset: set) -> float:
        """idf-weighted share of the (parenthesis-stripped) article title covered by the query,
        damped for titles made only of very common words (e.g. 'Polska')."""
        c = self._tcache.get(art)
        if c is None:
            title = _PAREN.sub("", self.article_title(art))
            toks = list(dict.fromkeys(self.tk.tokens(title)))
            tids = [self.aidx.term_ids([t]) for t in toks]
            idf = [float(self.a_idf[x[0]]) if x else 0.0 for x in tids]
            c = (toks, idf)
            if len(self._tcache) > 200_000:
                self._tcache.clear()
            self._tcache[art] = c
        toks, idf = c
        tot = sum(idf)
        if not toks or tot <= 0:
            return 0.0
        hit = sum(w for t, w in zip(toks, idf) if t in qset)
        return (hit / tot) * min(1.0, tot / 8.0)

    # ---- search --------------------------------------------------------
    def search(self, query: str, k: int = 8, per_article: int | None = None,
               candidates: int = 300, top_articles: int = 30) -> list[dict]:
        per_article = self.per_article if per_article is None else per_article
        toks = self.tk.tokens(query, query=True)
        if not toks:
            toks = self.tk.tokens(query, query=False)
        c_tids = self.cidx.term_ids(toks)
        if not c_tids:
            return []
        qset = set(toks)
        cs = self.cidx.scores(c_tids, self.n_chunks)
        ncand = min(candidates, self.n_chunks)
        cand = np.argpartition(-cs, ncand - 1)[:ncand] if ncand < self.n_chunks else np.arange(self.n_chunks)
        cand = cand[cs[cand] > 0]
        asc = None
        a_tids = self.aidx.term_ids(toks) if (self.alpha or self.gamma) else []
        if a_tids:
            asc = self.aidx.scores(a_tids, self.n_articles)
            # union: chunks of the best articles by the article-level index (title/redirect/lead)
            na = min(top_articles, self.n_articles)
            top_a = np.argpartition(-asc, na - 1)[:na]
            top_a = top_a[asc[top_a] > 0]
            extra = []
            for art in top_a:
                a0 = int(self.art_first[art])
                a1 = int(self.art_first[art + 1]) if art + 1 < self.n_articles else self.n_chunks
                rng = np.arange(a0, min(a1, a0 + 400))
                rng = rng[cs[rng] > 0]
                if len(rng) > 20:
                    rng = rng[np.argpartition(-cs[rng], 19)[:20]]
                extra.append(rng)
            if extra:
                cand = np.unique(np.concatenate([cand] + extra))
        if len(cand) == 0:
            return []
        final = cs[cand].astype(np.float32)
        arts = np.asarray(self.chunk_article[cand])
        if asc is not None and self.alpha:
            final = final + self.alpha * asc[arts]
        if self.beta:
            final = final + self.beta * self._prior()[arts]
        if self.gamma:
            ua, inv = np.unique(arts, return_inverse=True)
            cov = np.array([self._title_cov(int(x), qset) for x in ua], np.float32)
            final = final + self.gamma * cov[inv]
        order = np.argsort(-final)
        out, seen = [], {}
        for j in order:
            art = int(arts[j])
            if per_article and seen.get(art, 0) >= per_article:
                continue
            seen[art] = seen.get(art, 0) + 1
            r = self._record(int(cand[j]))
            r["score"] = float(final[j])
            out.append(r)
            if len(out) >= k:
                break
        return out

    def search_articles(self, query: str, k: int = 10) -> list[dict]:
        """Article-level hits (title/redirect/lead index) -> [{"title","url","score"}]."""
        toks = self.tk.tokens(query, query=True)
        tids = self.aidx.term_ids(toks)
        if not tids:
            return []
        asc = self.aidx.scores(tids, self.n_articles) + self.beta * self._prior()
        top = np.argsort(-asc)[:k]
        out = []
        for a in top:
            r = self._record(int(self.art_first[a]))
            out.append({"title": r["title"], "url": r["url"], "score": float(asc[a])})
        return out

    def resolve_title(self, title: str) -> str:
        """Map a redirect title to its article title (loads redirects.tsv lazily)."""
        if self._redirects is None:
            self._redirects = {}
            p = os.path.join(self.dir, "redirects.tsv")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    for ln in f:
                        al, _, t = ln.rstrip(NL).partition(TAB)
                        self._redirects[al] = t
        return self._redirects.get(title, title)


def main(argv=None):
    ap = argparse.ArgumentParser(description="BM25 search over plwiki chunks")
    ap.add_argument("query", nargs="+")
    ap.add_argument("--index", default=os.environ.get("KB_INDEX_DIR"))
    ap.add_argument("-k", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--chars", type=int, default=300, help="text preview length (non-JSON mode)")
    a = ap.parse_args(argv)
    t0 = time.time()
    kb = KB(a.index)
    t1 = time.time()
    q = " ".join(a.query)
    hits = kb.search(q, k=a.k)
    t2 = time.time()
    if a.json:
        print(json.dumps(hits, ensure_ascii=False, indent=1))
    else:
        print(f"# load {1000*(t1-t0):.0f} ms, query {1000*(t2-t1):.0f} ms, chunks={kb.n_chunks}", file=sys.stderr)
        for i, h in enumerate(hits, 1):
            print(f"{i}. [{h['score']:.2f}] {h['title']} — {h['section']}  <{h['url']}>")
            print("   " + h["text"].replace("\n", " ")[: a.chars])


if __name__ == "__main__":
    main()
