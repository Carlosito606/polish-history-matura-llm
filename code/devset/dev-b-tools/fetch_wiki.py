"""Fetch plain-text extracts of Polish Wikipedia articles (sequential, gentle).

Usage: python fetch_wiki.py titles.txt outdir
Each output file: <outdir>/<safe>.json with title, pageid, lastrevid, fullurl, extract.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = "WMT-hackathon-devset/1.0 (contact: see repository README)"
API = "https://pl.wikipedia.org/w/api.php"


def fetch(title):
    params = {
        "action": "query",
        "prop": "extracts|info",
        "inprop": "url",
        "explaintext": "1",
        "format": "json",
        "redirects": "1",
        "titles": title,
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    pages = data["query"]["pages"]
    page = next(iter(pages.values()))
    return {
        "requested": title,
        "title": page.get("title"),
        "pageid": page.get("pageid"),
        "lastrevid": page.get("lastrevid"),
        "fullurl": page.get("fullurl"),
        "missing": "missing" in page,
        "extract": page.get("extract", ""),
    }


def main():
    titles_file, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    titles = [t.strip() for t in open(titles_file, encoding="utf-8") if t.strip()]
    for t in titles:
        safe = re.sub(r"[^\w]+", "_", t)[:80]
        path = os.path.join(outdir, safe + ".json")
        if os.path.exists(path):
            continue
        try:
            rec = fetch(t)
        except Exception as e:  # noqa: BLE001
            print(f"ERR {t}: {e}")
            time.sleep(2)
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        print(f"{t!r} -> {rec['title']!r} len={len(rec['extract'])} missing={rec['missing']}")
        time.sleep(0.7)


if __name__ == "__main__":
    main()
