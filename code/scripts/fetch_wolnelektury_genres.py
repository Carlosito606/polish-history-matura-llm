#!/usr/bin/env python3
"""Fetch primary-source historical documents from the WolneLektury.pl API, by genre.

Companion to `fetch_historical_sources.py` (which handles archive.org / wikisource.org /
polona.pl rows from `sources/works_catalog.csv`). This script instead pulls WHOLE GENRES
from Wolne Lektury directly, since its catalog isn't row-listed in works_catalog.csv (it's a
different kind of source: many small primary documents, not a handful of named books).
See `docs/open_school_textbook_sources.md` (section "Bonus") for how the endpoint was found.

Wolne Lektury is public domain / CC BY-SA / Wolna Licencja Sztuki per book — see
`sources/portals.csv` (verdict: use). Genres below are the primary-document ones useful for
history (as opposed to the literary-canon fiction/poetry that dominates the catalog):
kazanie (sermon), pamietnik (memoir), dziennik (diary), odezwa (proclamation), manifest,
akt-prawny (legal act), kronika (chronicle), rozprawa-polityczna (political treatise),
traktat, list (letters), publicystyka (journalism).

API shape (verified live 2026-09-25):
  GET /api/genres/<slug>/books/   -> list of {title, author, slug, epoch, genre, href, ...}
  GET /api/books/<book-slug>/     -> detail incl. direct download URLs: txt, html, epub, pdf, fb2, mobi
  IMPORTANT: /api/books/?genre=<slug> and /api/books/?epoch=<slug> query params are silently
  IGNORED by the API (confirmed live: both returned the same unfiltered 7656-book list) -
  you must use the path-composed /api/genres/<slug>/books/ form instead.
Docs: https://wolnelektury.pl/api/

Usage:
  python scripts/fetch_wolnelektury_genres.py [--out sources/raw/wolnelektury] [--genres kazanie,pamietnik,...]

Writes:
  <out>/manifest.tsv    one row per book: title, author, genre, epoch, txt_url, local_path
  <out>/txt/<slug>.txt  the plain-text body

Output stays under sources/raw/ (git-ignored, see .gitignore) - never committed, only this
script + the manifest schema are.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://wolnelektury.pl/api"
UA = "wmt-matura-hackathon-research/0.1 (non-commercial, contact: repo owner)"

DEFAULT_GENRES = [
    "kazanie", "pamietnik", "dziennik", "odezwa", "manifest",
    "akt-prawny", "kronika", "rozprawa-polityczna", "traktat",
    "list", "publicystyka",
]


def get_json(url: str, retries: int = 3, pause: float = 1.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == retries - 1:
                raise
            time.sleep(pause)
        except urllib.error.URLError:
            if attempt == retries - 1:
                raise
            time.sleep(pause)
    return None


def get_bytes(url: str, retries: int = 3, pause: float = 1.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.URLError:
            if attempt == retries - 1:
                raise
            time.sleep(pause)
    return b""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sources/raw/wolnelektury", help="output directory")
    ap.add_argument("--genres", default=",".join(DEFAULT_GENRES),
                     help="comma-separated WolneLektury genre slugs")
    ap.add_argument("--limit", type=int, default=0, help="max books total (0 = no limit)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    txt_dir = out_dir / "txt"
    txt_dir.mkdir(parents=True, exist_ok=True)

    genres = [g.strip() for g in args.genres.split(",") if g.strip()]
    seen_slugs = set()
    rows = []

    for genre in genres:
        url = f"{API}/genres/{genre}/books/"
        print(f"[genre={genre}] GET {url}", file=sys.stderr)
        books = get_json(url)
        if not books:
            print(f"  no books / bad genre slug: {genre}", file=sys.stderr)
            continue
        print(f"  {len(books)} books", file=sys.stderr)

        for b in books:
            slug = b.get("slug")
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            if args.limit and len(rows) >= args.limit:
                break

            detail = get_json(b.get("href", f"{API}/books/{slug}/"))
            if not detail:
                continue
            txt_url = detail.get("txt")
            local_path = ""
            if txt_url:
                local_path = str(txt_dir / f"{slug}.txt")
                if not Path(local_path).exists():
                    try:
                        data = get_bytes(txt_url)
                        Path(local_path).write_bytes(data)
                    except Exception as e:
                        print(f"  FAILED {slug}: {e}", file=sys.stderr)
                        local_path = ""

            rows.append({
                "title": b.get("title", ""),
                "author": b.get("author", ""),
                "genre": b.get("genre", genre),
                "epoch": b.get("epoch", ""),
                "txt_url": txt_url or "",
                "local_path": local_path,
            })
        if args.limit and len(rows) >= args.limit:
            break

    manifest = out_dir / "manifest.tsv"
    with open(manifest, "w", encoding="utf-8") as f:
        f.write("title\tauthor\tgenre\tepoch\ttxt_url\tlocal_path\n")
        for r in rows:
            f.write("\t".join(r[k].replace("\t", " ") for k in
                               ("title", "author", "genre", "epoch", "txt_url", "local_path")) + "\n")

    print(f"wrote {len(rows)} rows to {manifest}", file=sys.stderr)


if __name__ == "__main__":
    main()
