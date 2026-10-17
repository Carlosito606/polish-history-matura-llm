#!/usr/bin/env python3
"""Fetch public-domain historical-book text listed in sources/works_catalog.csv.

Only pulls rows marked verified=yes (leads still need a human to confirm URL + PD status
before this script is pointed at them — see docs/historical_book_sources.md).

Sources handled:
  - archive.org item URLs  -> downloads the item's *_djvu.txt full-text file via the
    documented metadata API (no auth, respects the item's own rights field).
  - pl.wikisource.org page URLs -> pulls clean wikitext via the MediaWiki API
    (action=query, prop=revisions, no auth).
  - polona.pl preview/item URLs -> NOT auto-fetched (no stable public bulk-text endpoint
    confirmed in the research pass); the script just prints the URL for a manual check.

Output goes to sources/raw/ (git-ignored, same pattern as data_cke/) — never committed.
Usage:
  python scripts/fetch_historical_sources.py [--catalog sources/works_catalog.csv] [--out sources/raw]
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

UA = "wmt-matura-hackathon-research/0.1 (non-commercial, contact: repo owner)"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_archive_org(item_url: str, out_dir: Path) -> bool:
    m = re.search(r"archive\.org/details/([^/?#]+)", item_url)
    if not m:
        return False
    identifier = m.group(1)
    meta_url = f"https://archive.org/metadata/{identifier}"
    try:
        meta = json.loads(_get(meta_url))
    except Exception as e:
        print(f"  ! metadata fetch failed for {identifier}: {e}")
        return False
    files = meta.get("files", [])
    txt_file = next((f["name"] for f in files if f["name"].endswith("_djvu.txt")), None)
    if not txt_file:
        print(f"  ! no *_djvu.txt found for {identifier} (item may be image-only)")
        return False
    server = meta.get("server") or meta.get("d1") or "ia800000.us.archive.org"
    dir_ = meta.get("dir", f"/0/items/{identifier}")
    text_url = f"https://{server}{dir_}/{txt_file}"
    data = _get(text_url)
    out_path = out_dir / f"{identifier}.txt"
    out_path.write_bytes(data)
    print(f"  -> {out_path} ({len(data)} bytes)")
    return True


def fetch_wikisource(page_url: str, out_dir: Path) -> bool:
    m = re.search(r"pl\.wikisource\.org/wiki/(.+)$", page_url)
    if not m:
        return False
    title = m.group(1)
    api = (
        "https://pl.wikisource.org/w/api.php?action=query&prop=revisions&rvprop=content"
        f"&format=json&titles={title}"
    )
    try:
        data = json.loads(_get(api))
    except Exception as e:
        print(f"  ! wikisource fetch failed for {title}: {e}")
        return False
    pages = data.get("query", {}).get("pages", {})
    for _, page in pages.items():
        rev = page.get("revisions", [{}])[0]
        content = rev.get("*") or rev.get("slots", {}).get("main", {}).get("*")
        if content:
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", title)[:120]
            out_path = out_dir / f"{safe_name}.wikitext"
            out_path.write_text(content, encoding="utf-8")
            print(f"  -> {out_path} ({len(content)} chars)")
            return True
    print(f"  ! no content found for {title}")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="sources/works_catalog.csv")
    ap.add_argument("--out", default="sources/raw")
    ap.add_argument("--include-unverified", action="store_true",
                     help="also attempt rows with verified != yes (not recommended)")
    args = ap.parse_args()

    catalog = Path(args.catalog)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with catalog.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        if row.get("pd_status", "").startswith("NOT_PD"):
            print(f"[skip] #{row['id']} {row['title']}: not public domain yet")
            continue
        if row.get("verified") != "yes" and not args.include_unverified:
            print(f"[skip] #{row['id']} {row['title']}: unverified lead, confirm URL/PD status first")
            continue
        for url in filter(None, [row.get("url"), row.get("alt_url")]):
            url = url.strip()
            if not url or url.startswith("search "):
                continue
            print(f"[fetch] #{row['id']} {row['title']} <- {url}")
            ok = False
            if "archive.org" in url:
                ok = fetch_archive_org(url, out_dir)
            elif "wikisource.org" in url:
                ok = fetch_wikisource(url, out_dir)
            elif "polona.pl" in url:
                print("  (Polona: no confirmed bulk-text endpoint - check manually / via labs.polona.pl API docs)")
            if ok:
                time.sleep(1)  # be polite
                break


if __name__ == "__main__":
    sys.exit(main())
