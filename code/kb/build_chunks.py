"""Stream-parse the plwiki CirrusSearch *content* dump into section-aware chunks (parquet shards).

Usage (on the Mac, from ~/wmt-matura):
  python -m kb.build_chunks --dump kb_data/raw/plwiki-20251229-cirrussearch-content.json.gz \
      --out kb_data/chunks --workers 10

Input: alternating JSON lines (index action, document). Document fields used:
  title, namespace, text (rendered plain text, no headings), source_text (wikitext; used only to
  recover section boundaries), heading, category, template, redirect, popularity_score,
  incoming_links, page_id, opening_text.

Section recovery: CirrusSearch `text` has no headings, so for every wikitext section we crudely
strip markup, take its first tokens and locate them (4-token windows) in the rendered text.
The tail (Uwagi/Przypisy/Bibliografia/Linki zewnętrzne/navboxes/authority control) is cut by
locating the *end* of the last content section.

Output columns: page_id, title, section, chunk_idx, text ("Tytuł — Sekcja\\n..."), n_words, url,
popularity_score, incoming_links, categories ("|"-joined), aliases ("|"-joined redirects,
only on chunk 0), hist_score (int heuristic of history relevance), opening_text (chunk 0 only),
headings ("|"-joined, chunk 0 only).
"""
from __future__ import annotations

import argparse
import bisect
import multiprocessing as mp
import os
import re
import subprocess
import sys
import time
import urllib.parse

import orjson
import pyarrow as pa
import pyarrow.parquet as pq

from kb.textnorm import fold

WORD = re.compile(r"\w+", re.UNICODE)
HEADING_RE = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", re.M)
TAIL_HEADINGS = {
    "uwagi", "przypisy", "bibliografia", "linki zewnętrzne", "zobacz też", "literatura",
    "literatura uzupełniająca", "bibliografia uzupełniająca", "galeria", "przypisy i uwagi",
    "uwagi i przypisy", "noty", "objaśnienia", "linki zewnętrzne i bibliografia", "zobacz także",
    "przypisy bibliograficzne", "źródła i bibliografia", "bibliografia i linki zewnętrzne",
    "przypisy i bibliografia", "publikacje", "filmografia", "dyskografia",
}
_RE_COMMENT = re.compile(r"<!--.*?-->", re.S)
_RE_REF1 = re.compile(r"<ref[^>]*/>", re.I)
_RE_REF2 = re.compile(r"<ref[^>]*>.*?</ref>", re.S | re.I)
_RE_TPL = re.compile(r"\{\{[^{}]*\}\}")
_RE_TABLE = re.compile(r"\{\|.*?\|\}", re.S)
_RE_FILE = re.compile(r"\[\[(?:Plik|File|Grafika|Image|Kategoria|Category|Media):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", re.I)
_RE_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_RE_EXT = re.compile(r"\[https?://\S+\s*([^\]]*)\]")
_RE_TAG = re.compile(r"<[^>]+>")
_RE_GALLERY = re.compile(r"<gallery.*?</gallery>", re.S | re.I)
_RE_MAINT = re.compile(
    r"(?:Ten artykuł|Ta sekcja|Ta strona|Ten fragment|Ta lista|Ten tekst)\b.{0,2500}?usunąć szablon \{\{[^}]*\}\}"
    r"(?: z te(?:go|j) (?:artykułu|sekcji|strony|fragmentu|listy))?\.?",
    re.S,
)
_RE_BRACKET_NOTES = re.compile(r"\[(?:potrzebny przypis|zarchiwizowane z tego adresu|archiwum|martwy link|przypis\?)\]?")
_RE_SEEALSO = re.compile(r"(?:Osobn[ey] artykuł[y]?|Zobacz też kategori[eęa]|Zobacz też|Zobacz więcej w artykule):\s*")


def clean_text(t: str) -> str:
    t = _RE_MAINT.sub(" ", t)
    t = _RE_BRACKET_NOTES.sub("", t)
    t = _RE_SEEALSO.sub("", t)
    return re.sub(r"\s{2,}", " ", t).strip()


SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9„\"(\[])")

HIST_CAT = re.compile(
    r"histori|dziej|wojn|bitw|powstani|królowie|królowe|władc|dynasti|traktat|pokoje|rozejm|sejm|"
    r"konfederac|państwa historyczne|dawne państwa|imperi|cesarz|cesarstw|księstw|królestw|"
    r"rewoluc|zabor|okupac|holokaust|getta|obozy|zamach|reformy|konstytuc|unie|dyplomac|biskup|"
    r"papież|papieże|zakon|rycer|szlacht|herb|rody|magnat|hetman|wojewod|kasztelan|starost|"
    r"odznaczeni|order|wojsk|armi|żołnierz|oficer|generał|dowódc|pułk|dywizj|legion|partyzant|"
    r"konspirac|armia krajowa|prl|rzeczpospolit|rzeczypospolitej|średniow|starożyt|nowożyt|"
    r"politycy|posłowie|senatorowie|premier|prezydenci|ministrowie|partie polityczne|"
    r"stronnictw|uczestnicy|ofiary|więźniowie|działacze|emigrac|kampani|operacje|oblężeni|"
    r"konflikty|zbrodni|represj|stalinizm|komunizm|nazizm|faszyzm|zimna wojna|kolonializm|"
    r"reformac|renesans|oświecen|barok|romantyzm|pozytywizm|filozofowie|kronikarze|historycy|"
    r"archeolog|zabytki|zamki|twierdz|pałace|katedry|koronacj|elekcj|sejmy|sejmiki|"
    r"miasta lokowane|dawne miasta|stolice|ludy|plemiona|cywilizac|mitologi|religi|"
    r"traktaty|układy|akty prawne|ustawy|wydarzenia|zjazdy|kongresy|uniwersytet|pisarze|poeci|"
    r"malarze|kompozytorzy|naukowcy|odkrywcy|podróżnicy|urodzeni w [ivxlc]+ wieku|zmarli w [ivxlc]+ wieku",
    re.I,
)
NONHIST_CAT = re.compile(
    r"gatunki|taksony|planetoid|albumy|single|piłkarze|filmy|gry komputerowe|seriale|sezony|"
    r"zespoły muzyczne|tenisiści|kolarze|motyle|chrząszcze|pająki|ryby|rośliny|grzyby|ptaki|"
    r"ssaki|owady|bakterie|odcinki|piosenki|utwory|raperzy|youtuberzy|aktorzy|drużyny|kluby piłkarskie|"
    r"stacje kolejowe|przystanki|linie autobusowe|oprogramowanie|samochody|gwiazdozbiór|galaktyki|"
    r"gminy w|sołectwa|reprezentanci|sportowcy|olimpijczycy|lekkoatleci|siatkarze|koszykarze|hokeiści",
    re.I,
)
BORN = re.compile(r"^(?:Urodzeni|Zmarli) w (\d{3,4})$")


def hist_score(categories: list[str], title: str) -> int:
    s = 0
    for c in categories:
        if HIST_CAT.search(c):
            s += 2
        if NONHIST_CAT.search(c):
            s -= 3
        m = BORN.match(c)
        if m and int(m.group(1)) < 1950:
            s += 2
    if re.search(r"\b(bitwa|pokój|traktat|powstanie|wojna|unia|rozejm|konfederacja|sejm|zjazd|oblężenie|"
                 r"rokosz|potop|elekcja|koronacja|rozbiór|kampania)\b", title, re.I):
        s += 4
    return s


def crude_tokens(wikitext: str) -> list[str]:
    s = _RE_COMMENT.sub("", wikitext)
    s = _RE_GALLERY.sub("", s)
    s = _RE_REF1.sub("", s)
    s = _RE_REF2.sub("", s)
    for _ in range(6):
        s2 = _RE_TPL.sub("", s)
        if s2 == s:
            break
        s = s2
    s = _RE_TABLE.sub("", s)
    s = _RE_FILE.sub("", s)
    s = _RE_LINK.sub(r"\1", s)
    s = _RE_EXT.sub(r"\1", s)
    s = _RE_TAG.sub(" ", s)
    return WORD.findall(fold(s))


def split_sections(src: str):
    """-> list of (level, heading, body_wikitext); first entry is the lead (level 1, '')."""
    out = []
    last = 0
    lvl, head = 1, ""
    for m in HEADING_RE.finditer(src):
        out.append((lvl, head, src[last:m.start()]))
        lvl, head = len(m.group(1)), m.group(2)
        last = m.end()
    out.append((lvl, head, src[last:]))
    return out


def clean_heading(h: str) -> str:
    h = _RE_LINK.sub(r"\1", h)
    h = _RE_TPL.sub("", h)
    h = _RE_TAG.sub("", h).replace("'''", "").replace("''", "")
    return h.strip()


class TextIndex:
    """Token view of rendered text for window search."""

    def __init__(self, text: str):
        self.spans = []
        toks = []
        for m in WORD.finditer(text):
            self.spans.append((m.start(), m.end()))
            toks.append(m.group(0))
        self.toks = fold(" ".join(toks)).split(" ") if toks else []
        if len(self.toks) != len(self.spans):  # folding changed token boundaries (rare)
            self.toks = [fold(t) for t in toks]
        self.joined = " ".join(self.toks)
        self.starts = []
        p = 0
        for t in self.toks:
            self.starts.append(p)
            p += len(t) + 1

    def find(self, window: list[str], from_tok: int) -> int:
        """token index of first occurrence at/after from_tok, or -1."""
        if not window:
            return -1
        start_char = self.starts[from_tok] if from_tok < len(self.starts) else len(self.joined)
        pat = " ".join(window)
        while True:
            p = self.joined.find(pat, start_char)
            if p < 0:
                return -1
            # require token-boundary alignment
            if (p == 0 or self.joined[p - 1] == " ") and (
                p + len(pat) == len(self.joined) or self.joined[p + len(pat)] == " "
            ):
                return bisect.bisect_left(self.starts, p)
            start_char = p + 1


def locate_sections(title: str, text: str, src: str, W: int = 4):
    """-> list of (label, char_start, char_end) spans over `text`."""
    ti = TextIndex(text)
    n = len(ti.toks)
    if n == 0:
        return []
    secs = split_sections(src or "")
    content = []
    tail_seen = False
    for lvl, head, body in secs[1:]:
        h = clean_heading(head)
        if lvl == 2 and h.lower() in TAIL_HEADINGS:
            tail_seen = True
            break
        content.append((lvl, h, body))
    anchors = [(0, "Wstęp")]
    cur = 0
    parent = ""
    last_body_toks = crude_tokens(secs[0][2]) if secs else []
    for lvl, h, body in content:
        if lvl == 2:
            parent = h
        label = h if (lvl == 2 or not parent or parent == h) else f"{parent} / {h}"
        toks = crude_tokens(body)
        if len(toks) < W:
            continue
        found = -1
        for off in range(0, min(len(toks) - W + 1, 30)):
            p = ti.find(toks[off:off + W], cur)
            if p >= 0:
                found = max(cur, p - off)
                break
        if found >= 0 and found > anchors[-1][0]:
            anchors.append((found, label))
            cur = found
            last_body_toks = toks
        elif found >= 0 and found == anchors[-1][0]:
            anchors[-1] = (found, label)
            last_body_toks = toks
    # end of content
    end = n
    if tail_seen:
        end = -1
        toks = last_body_toks
        L = len(toks)
        for off in range(0, min(L - W + 1, 40)):
            win = toks[L - W - off:L - off]
            p = ti.find(win, cur)
            if p >= 0:
                end = min(n, p + W + off)
                break
        if end < 0:
            end = min(n, cur + int(len(toks) * 1.1) + 5)
    spans = []
    for i, (a, label) in enumerate(anchors):
        b = anchors[i + 1][0] if i + 1 < len(anchors) else end
        b = min(b, end)
        if b <= a:
            continue
        spans.append((label, ti.spans[a][0], ti.spans[b - 1][1]))
    return spans


def pack(text: str, target: int = 170, max_w: int = 250, min_w: int = 60):
    """Split a section into ~120-250-word chunks on sentence boundaries."""
    sents = SENT_SPLIT.split(text.strip())
    chunks, buf, bw = [], [], 0
    for s in sents:
        w = s.split()
        if len(w) > max_w:  # very long sentence / list: hard split
            if buf:
                chunks.append(" ".join(buf))
                buf, bw = [], 0
            for i in range(0, len(w), target):
                chunks.append(" ".join(w[i:i + target]))
            continue
        if bw + len(w) > max_w and bw >= min_w:
            chunks.append(" ".join(buf))
            buf, bw = [], 0
        buf.append(s)
        bw += len(w)
        if bw >= target:
            chunks.append(" ".join(buf))
            buf, bw = [], 0
    if buf:
        if chunks and bw < min_w and len(chunks[-1].split()) + bw <= max_w + 40:
            chunks[-1] = chunks[-1] + " " + " ".join(buf)
        else:
            chunks.append(" ".join(buf))
    return chunks


def is_disambig(d: dict) -> bool:
    for t in d.get("template") or ():
        if t.startswith("Szablon:Strona ujednoznaczniająca") or t == "Szablon:Disambig":
            return True
    for c in d.get("category") or ():
        if c.startswith("Strony ujednoznaczniające"):
            return True
    return False


COLS = ["page_id", "title", "section", "chunk_idx", "text", "n_words", "url", "popularity_score",
        "incoming_links", "categories", "aliases", "hist_score", "opening_text", "headings"]


def process_doc(d: dict, min_words: int = 20):
    if d.get("namespace", 0) != 0:
        return []
    title = d.get("title") or ""
    text = clean_text(d.get("text") or "")
    if not title or not text or is_disambig(d):
        return []
    if len(text.split()) < min_words:
        return []
    cats = d.get("category") or []
    try:
        spans = locate_sections(title, text, d.get("source_text") or "")
    except Exception:
        spans = [("Wstęp", 0, len(text))]
    if not spans:
        return []
    # merge tiny sections into the next one
    merged = []
    for label, a, b in spans:
        if merged and len(text[merged[-1][1]:merged[-1][2]].split()) < 40:
            pl, pa_, _ = merged[-1]
            merged[-1] = (f"{pl}; {label}" if pl != label else pl, pa_, b)
        else:
            merged.append((label, a, b))
    url = "https://pl.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
    aliases = [r.get("title", "") for r in (d.get("redirect") or []) if r.get("namespace", 0) == 0][:20]
    hs = hist_score(cats, title)
    rows = []
    ci = 0
    for label, a, b in merged:
        body = text[a:b]
        for ch in pack(body):
            nw = len(ch.split())
            if nw < 8:
                continue
            rows.append({
                "page_id": int(d.get("page_id") or 0),
                "title": title,
                "section": label,
                "chunk_idx": ci,
                "text": f"{title} — {label}\n{ch}",
                "n_words": nw,
                "url": url,
                "popularity_score": float(d.get("popularity_score") or 0.0),
                "incoming_links": int(d.get("incoming_links") or 0),
                "categories": "|".join(cats) if ci == 0 else "",
                "aliases": "|".join(aliases) if ci == 0 else "",
                "hist_score": hs,
                "opening_text": (d.get("opening_text") or "") if ci == 0 else "",
                "headings": "|".join(d.get("heading") or []) if ci == 0 else "",
            })
            ci += 1
    return rows


SCHEMA = pa.schema([
    ("page_id", pa.int64()), ("title", pa.string()), ("section", pa.string()), ("chunk_idx", pa.int32()),
    ("text", pa.string()), ("n_words", pa.int32()), ("url", pa.string()), ("popularity_score", pa.float32()),
    ("incoming_links", pa.int32()), ("categories", pa.string()), ("aliases", pa.string()),
    ("hist_score", pa.int32()), ("opening_text", pa.string()), ("headings", pa.string()),
])


def work(args):
    batch_id, lines, out_dir = args
    rows = []
    ndocs = 0
    for ln in lines:
        try:
            d = orjson.loads(ln)
        except Exception:
            continue
        ndocs += 1
        rows.extend(process_doc(d))
    if rows:
        tbl = pa.Table.from_pylist(rows, schema=SCHEMA)
        tmp = os.path.join(out_dir, f".part-{batch_id:05d}.parquet.tmp")
        pq.write_table(tbl, tmp, compression="zstd")
        os.replace(tmp, os.path.join(out_dir, f"part-{batch_id:05d}.parquet"))
    return batch_id, ndocs, len(rows)


def read_docs(path: str, limit: int | None):
    if path == "-":
        stream = sys.stdin.buffer
        proc = None
    else:
        proc = subprocess.Popen(["gzip", "-dc", path], stdout=subprocess.PIPE, bufsize=1 << 24)
        stream = proc.stdout
    n = 0
    for line in stream:
        if line.startswith(b'{"index"'):
            continue
        yield line
        n += 1
        if limit and n >= limit:
            break
    if proc:
        proc.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True, help=".json.gz path or - for stdin (decompressed)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--batch", type=int, default=2000, help="docs per worker task / shard")
    ap.add_argument("--limit", type=int, default=0, help="debug: stop after N docs")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()

    def tasks():
        buf, bid = [], 0
        for ln in read_docs(a.dump, a.limit or None):
            buf.append(ln)
            if len(buf) >= a.batch:
                yield (bid, buf, a.out)
                buf, bid = [], bid + 1
        if buf:
            yield (bid, buf, a.out)

    tot_docs = tot_rows = 0
    ctx = mp.get_context("spawn")
    from collections import deque

    inflight: deque = deque()
    done = 0

    def collect(r):
        nonlocal tot_docs, tot_rows, done
        bid, nd, nr = r.get()
        tot_docs += nd
        tot_rows += nr
        done += 1
        if done % 25 == 0:
            el = time.time() - t0
            print(f"[{el:7.1f}s] batches={done} docs={tot_docs} chunks={tot_rows} ({tot_docs/el:.0f} docs/s)", flush=True)

    # bounded in-flight queue => bounded RAM (Pool.imap would read the whole dump eagerly)
    with ctx.Pool(a.workers, maxtasksperchild=200) as pool:
        for t in tasks():
            inflight.append(pool.apply_async(work, (t,)))
            while len(inflight) >= 2 * a.workers:
                collect(inflight.popleft())
        while inflight:
            collect(inflight.popleft())
    print(f"DONE docs={tot_docs} chunks={tot_rows} in {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
