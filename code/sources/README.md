# sources/ — public-domain historical-book + open-school-textbook source catalog

Metadata-only dataset (no copyrighted text committed), built for extending `kb/`'s
Wikipedia-only RAG with historical-synthesis and primary-document text, plus open-licensed
school teaching material. Two separate research passes, two writeups:
`docs/historical_book_sources.md` (public-domain history books/archives) and
`docs/open_school_textbook_sources.md` (ZPE/Scholaris/IPN/MHP/Otwarte Zasoby OER platforms).

- `portals.csv` — one row per portal surveyed across BOTH passes (Polona, FBC + 4 regional
  dLibra libraries, Internet Archive, HathiTrust, Google Books, Wikisource PL, Wolne Lektury,
  plus ZPE, Scholaris, IPN edukacja, Muzeum Historii Polski, Otwarte Zasoby): access method/API,
  licence summary, text quality, `verdict` (use/maybe/avoid) + reason.
- `works_catalog.csv` — one row per candidate historical *book*: title, author, author death
  year, `pd_status` (PD / NOT_PD_until_<year>), best source portal + URL(s), format, and a
  `verified` flag (`yes` = URL and PD status checked this pass, `partial` = source located but
  not fully checked, `no` = lead only, confirm before use).
- `school_ematerialy_sample.csv` — a handful of concrete OER platform pages actually checked
  (not a full catalog — none of those platforms cleared bulk automated harvesting this pass,
  see `docs/open_school_textbook_sources.md` for why per source).
- `raw/` (git-ignored) — actual downloaded text lands here via
  `scripts/fetch_historical_sources.py` (books) or `scripts/fetch_wolnelektury_genres.py`
  (Wolne Lektury primary-document genres); never committed, same pattern as `data_cke/`.
- `raw/zpe/` (git-ignored) — ZPE history e-materials (liceum/technikum) via `scripts/fetch_zpe.py`:
  only text of elements whose own caption shows CC BY / CC BY-SA / CC0 (the lesson prose shows no
  licence and is never kept); `manifest.csv` logs every material, `zpe_chunks.parquet` is the
  KB-compatible chunk file (page_id 900000000+). Attribution list: `docs/zpe_sources.md`.

## Rules baked into the catalog (see CLAUDE.md)
- Only rows with `pd_status = PD` are fetched by the script; `NOT_PD_until_*` rows (e.g.
  Oskar Halecki, d. 1973 -> PD in 2044) are always skipped.
- `verified != yes` rows are leads, not confirmed sources — the fetch script skips them
  unless `--include-unverified` is passed; check the URL and PD status by hand first.
- No scraping of Google Books or bulk pulls from HathiTrust (see portals.csv `avoid`/`maybe`
  reasons) — both are dead ends for this timebox.
