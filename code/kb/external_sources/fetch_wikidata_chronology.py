"""Pull deterministic Polish-history chronology facts from Wikidata (CC0 1.0 -- no
copyright/licence risk, unlike scraped book scans). Used to generate chronology /
ordering / matching matura-style questions ("uporzadkuj wladcow chronologicznie",
"ktory traktat podpisano wczesniej") without any third-party text in the repo.

Usage:
    python -m kb.external_sources.fetch_wikidata_chronology --out kb_data/wikidata

Network access only; nothing here touches data_cke/ or the organizers' backend.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "wmt-matura-hackathon-research/1.0 (educational, non-commercial)"

# Q3273712 = "King of Poland" (position held, P39). Extend with more QIDs
# (e.g. Q713750 "Prince of Poland", Q1370598 "President of Poland") as needed.
RULERS_QUERY = """
SELECT ?rulerLabel ?start ?end WHERE {
  ?ruler p:P39 ?stmt .
  ?stmt ps:P39 wd:Q3273712 .
  ?stmt wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  ?stmt pq:P580 ?start .
  OPTIONAL { ?stmt pq:P582 ?end }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "pl". }
}
ORDER BY ?start
LIMIT 200
"""


def run_query(query: str) -> dict:
    url = SPARQL_ENDPOINT + "?" + urllib.parse.urlencode({"query": query})
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def rulers_to_rows(data: dict) -> list[dict]:
    rows = []
    for b in data["results"]["bindings"]:
        rows.append(
            {
                "ruler": b.get("rulerLabel", {}).get("value", "?"),
                "reign_start": b.get("start", {}).get("value", "")[:10],
                "reign_end": (b.get("end", {}).get("value", "")[:10] if "end" in b else None),
            }
        )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="kb_data/wikidata/polish_monarchs.json")
    args = ap.parse_args()

    try:
        data = run_query(RULERS_QUERY)
    except urllib.error.URLError as e:
        raise SystemExit(f"Wikidata query failed (no internet in the harness?): {e}")

    rows = rulers_to_rows(data)
    time.sleep(1)  # be polite to the shared public endpoint

    import os

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"wrote {len(rows)} rows to {args.out} (CC0, source: Wikidata SPARQL query service)")


if __name__ == "__main__":
    main()
