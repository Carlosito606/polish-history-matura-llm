#!/usr/bin/env python
"""Download the CKE history matura archive mirrored on arkusze.pl.

Source of truth for which pages to crawl: docs/cke_archive_sources.md (one arkusze.pl
exam-page URL per row). For each page this script:
  1. fetches the page HTML (polite: sequential requests, ~0.7s pause, a normal
     browser User-Agent -- arkusze.pl's robots.txt allows crawling),
  2. collects every PDF link on it (exam sheet, answer key / zasady oceniania PDF,
     and any extra attachment),
  3. downloads them into data_cke/arkusze/<slug>/ (slug = last path segment of the
     page URL),
  4. extracts text next to each PDF as <name>.txt with PyMuPDF, keeping
     "=== PAGE n ===" markers between pages,
  5. records year / session / level / formula / split per exam in
     data_cke/arkusze/manifest.json.

CKE materials are copyrighted third-party content: data_cke/ is git-ignored (see
.gitignore) -- only this script and the URL list in docs/cke_archive_sources.md are
committed. Nothing under data_cke/ is ever committed.

Usage:
  pip install pymupdf     # if not already installed
  python scripts/fetch_arkusze.py                 # fetch missing files only, then extract
  python scripts/fetch_arkusze.py --force          # re-download + re-extract everything
  python scripts/fetch_arkusze.py --pause 1.0      # slower crawl
  python scripts/fetch_arkusze.py --sources path/to/list.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCES = os.path.join(ROOT, "docs", "cke_archive_sources.md")
OUT_ROOT = os.path.join(ROOT, "data_cke", "arkusze")
MANIFEST_PATH = os.path.join(OUT_ROOT, "manifest.json")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

URL_RE = re.compile(r"https://arkusze\.pl/[a-z0-9\-]+/")
PDF_HREF_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)

SESSION_WORDS = [
    "styczen", "luty", "marzec", "kwiecien", "maj", "czerwiec", "lipiec",
    "sierpien", "wrzesien", "pazdziernik", "listopad", "grudzien", "przykladowy",
]


def log(msg: str) -> None:
    print(msg, flush=True)


def load_source_urls(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    seen: set[str] = set()
    urls: list[str] = []
    for m in URL_RE.finditer(text):
        u = m.group(0)
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def http_get(url: str, timeout: int = 30, retries: int = 3) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt == retries:
                raise
            time.sleep(1.5 * attempt)
    raise last_err  # pragma: no cover


def classify(slug: str) -> dict:
    """Derive year / session / level / formula / split from the arkusze.pl page slug."""
    year_m = re.search(r"(\d{4})", slug)
    year = int(year_m.group(1)) if year_m else None

    if "rozszerzony" in slug:
        level = "rozszerzony"
    elif "podstawowy" in slug:
        level = "podstawowy"
    else:
        level = None

    session = None
    for w in SESSION_WORDS:
        if w in slug:
            session = w
            break

    if "probna" in slug:
        kind = "probna"
    elif "poprawkowa" in slug:
        kind = "poprawkowa"
    elif "przykladowy" in slug:
        kind = "przykladowy"
    elif "stara" in slug:
        kind = "stara"
    else:
        kind = "glowna"

    # "matura stara" pages keep the pre-2015 (old-formula) exam even when re-sat in
    # recent years, so the slug tag overrides the year-based default.
    if "stara" in slug:
        formula = "stara"
    elif year is None:
        formula = None
    elif year <= 2014:
        formula = "stara"
    elif year <= 2022:
        formula = "2015"
    else:
        formula = "2023"

    split = "eval" if (year is not None and year >= 2023) else "train"

    return {
        "year": year,
        "session": session,
        "level": level,
        "kind": kind,
        "formula": formula,
        "split": split,
    }


def is_key_pdf(filename: str) -> bool:
    lower = filename.lower()
    return "odpowiedz" in lower or "zasady" in lower or "klucz" in lower


def extract_pdf_text(pdf_path: str, txt_path: str) -> int:
    """Extract text from pdf_path into txt_path with '=== PAGE n ===' markers.

    Returns the number of non-whitespace characters extracted.
    """
    import pymupdf  # imported lazily so --help works without the dependency

    doc = pymupdf.open(pdf_path)
    try:
        parts = []
        total_chars = 0
        for i, page in enumerate(doc, start=1):
            text = page.get_text()
            total_chars += len(text.strip())
            parts.append(f"=== PAGE {i} ===\n{text}")
        with open(txt_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(parts))
        return total_chars
    finally:
        doc.close()


def process_page(url: str, pause: float, force: bool) -> dict:
    slug = slug_from_url(url)
    meta = classify(slug)
    entry = {
        "slug": slug,
        "url": url,
        **meta,
        "files": [],
        "sheet_pdf": None,
        "key_pdf": None,
        "has_key": False,
        "error": None,
    }

    try:
        html = http_get(url).decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        entry["error"] = f"page fetch failed: {type(e).__name__}: {e}"
        log(f"FAIL  {slug}  <- page fetch: {e}")
        return entry

    pdf_urls: list[str] = []
    seen = set()
    for m in PDF_HREF_RE.finditer(html):
        u = m.group(1)
        if u not in seen:
            seen.add(u)
            pdf_urls.append(u)

    if not pdf_urls:
        entry["error"] = "no PDF links found on page"
        log(f"WARN  {slug}  no PDF links found")
        return entry

    dest_dir = os.path.join(OUT_ROOT, slug)
    os.makedirs(dest_dir, exist_ok=True)

    for pdf_url in pdf_urls:
        time.sleep(pause)
        fname = pdf_url.rsplit("/", 1)[-1]
        pdf_path = os.path.join(dest_dir, fname)
        txt_path = pdf_path[:-4] + ".txt"
        role = "key" if is_key_pdf(fname) else "arkusz"

        if not os.path.exists(pdf_path) or force:
            try:
                data = http_get(pdf_url)
                with open(pdf_path, "wb") as fh:
                    fh.write(data)
                log(f"ok    {slug}/{fname}  ({len(data):,} B)")
            except Exception as e:  # noqa: BLE001
                log(f"FAIL  {slug}/{fname}  <- download: {e}")
                entry["files"].append({
                    "filename": fname, "role": role, "url": pdf_url,
                    "downloaded": False, "text_chars": 0, "error": str(e),
                })
                continue
        else:
            log(f"skip  {slug}/{fname}  (exists)")

        text_chars = 0
        if not os.path.exists(txt_path) or force:
            try:
                text_chars = extract_pdf_text(pdf_path, txt_path)
            except Exception as e:  # noqa: BLE001
                log(f"FAIL  {slug}/{fname}  <- extract: {e}")
        elif os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8", errors="replace") as fh:
                text_chars = len(fh.read().strip())

        file_entry = {
            "filename": fname, "role": role, "url": pdf_url,
            "downloaded": True, "text_chars": text_chars, "error": None,
        }
        entry["files"].append(file_entry)

        rel_pdf = os.path.relpath(pdf_path, ROOT).replace("\\", "/")
        if role == "key" and entry["key_pdf"] is None:
            entry["key_pdf"] = rel_pdf
            entry["has_key"] = text_chars > 0
        elif role == "arkusz" and entry["sheet_pdf"] is None:
            entry["sheet_pdf"] = rel_pdf

    return entry


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", default=DEFAULT_SOURCES, help="Markdown/text file listing arkusze.pl page URLs")
    ap.add_argument("--force", action="store_true", help="re-download and re-extract even if files exist")
    ap.add_argument("--pause", type=float, default=0.7, help="seconds to sleep between HTTP requests")
    ap.add_argument("--limit", type=int, default=None, help="only process the first N pages (debugging)")
    args = ap.parse_args()

    urls = load_source_urls(args.sources)
    if args.limit:
        urls = urls[: args.limit]
    if not urls:
        log(f"no source URLs found in {args.sources}")
        return 2

    os.makedirs(OUT_ROOT, exist_ok=True)
    log(f"{len(urls)} source pages from {args.sources}")

    manifest = []
    for i, url in enumerate(urls, start=1):
        log(f"[{i}/{len(urls)}] {url}")
        entry = process_page(url, args.pause, args.force)
        manifest.append(entry)
        time.sleep(args.pause)

    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    total = len(manifest)
    ok = sum(1 for e in manifest if e["sheet_pdf"])
    with_key = sum(1 for e in manifest if e["has_key"])
    errors = [e["slug"] for e in manifest if e["error"]]
    log("")
    log(f"done: {ok}/{total} pages have a sheet PDF, {with_key}/{total} have a readable key")
    if errors:
        log(f"pages with issues: {errors}")
    log(f"manifest written to {MANIFEST_PATH}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
