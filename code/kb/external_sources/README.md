# kb/external_sources/ — book-archive portals research + a CC0 chronology dataset

Research deliverable: which portals beyond Polish Wikipedia legally archive/index historical
books and other structured facts useful for Polish-history matura questions. Full writeup with
per-source licence/access/verdict reasoning: `docs/book_archive_sources.md`.

No copyrighted material lives in this folder (per `CLAUDE.md`): only a source catalogue, a
download script, and one genuinely CC0 sample.

## Files

- `sources_catalog.csv` / `sources_catalog.json` — the dataset asked for: every portal checked,
  with `licence`, `access_method`, `value_for_task`, `effort` and a `verdict`
  (`use` / `maybe` / `avoid`) + `reason`. 14 rows.
- `fetch_wikidata_chronology.py` — reruns the one source rated `use` that needed live code
  (Wikidata SPARQL, CC0): `python -m kb.external_sources.fetch_wikidata_chronology --out <path>`.
  No API key, no auth, polite 1s delay, ~200-row cap.
- `wikidata_polish_monarchs_sample.json` — 37 rows actually pulled from
  `query.wikidata.org/sparql` during this research pass (King of Poland, `wd:Q3273712`, reign
  start/end dates). CC0 1.0, safe to commit verbatim. Known caveat: a handful of entries are
  claimants/pretenders who were elected but never reigned (Wikidata models "position held" more
  broadly than "actually ruled") — filter by cross-checking against a second source, or add a
  `P31`/country qualifier, before treating a row as exam ground truth.

## Top-line verdicts (see the CSV for all 14)

| verdict | sources |
|---|---|
| **use** | Wolne Lektury, Wikiźródła (Polish Wikisource), Wikidata |
| **maybe** | Federacja Bibliotek Cyfrowych, Polona, Encyklopedia Orgelbranda, dane.gov.pl, KRONIK@, Europeana |
| **avoid** | IPN Przystanek Historia (all rights reserved despite free download), Project Gutenberg PL shelf (wrong content type — fiction), Internet Archive (mixed CDL/public-domain, easy to grab a non-free item by accident), Google Books / HathiTrust (ToS forbids the bulk access this task needs) |
