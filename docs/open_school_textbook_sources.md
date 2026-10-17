# Open-licensed school textbook / OER portals — source survey

Companion to `docs/historical_book_sources.md` (which covers portals that archive
public-domain *historical books*). This pass covers the other research track: **open-licensed
Polish school HISTORY teaching material** — ZPE/epodreczniki, Scholaris, IPN's education portal,
Muzeum Historii Polski, and the "Otwarte Zasoby" meta-directory. Timeboxed research, ~40 min,
2026-09-25. No automated bulk download was performed on any of these; everything below is
metadata (URLs, robots.txt/API findings, licence notes) for `sources/portals.csv` +
`sources/school_ematerialy_sample.csv`. Nothing from these sites is committed here, per
`CLAUDE.md`.

## Per-source verdicts

### 1. ZPE — Zintegrowana Platforma Edukacyjna (zpe.gov.pl) — **MAYBE**
Successor platform (launched 2019) that folded in `epodreczniki.pl` (Cyfrowa Szkoła programme)
and `Scholaris.pl`. Covers historia for szkoła podstawowa and liceum/technikum (zakres
podstawowy i rozszerzony), 2022 podstawa programowa, e.g.
`https://zpe.gov.pl/podstawa-programowa/szkola-ponadpodstawowa/historia-pp-2022`.

- **Licence**: publicly and repeatedly stated (ministry press pages, ORE/KOED write-ups) that
  all e-materiały are released under an open Creative Commons licence, commonly cited as
  CC BY‑SA 4.0. **Not independently verifiable from the raw page HTML in this pass** — see
  below.
- **robots.txt**: `User-agent: *` / `Allow: /` — fully crawlable by policy.
- **Regulamin** (`zpe.gov.pl/regulamin`): only spells out the licence a *registered user*
  grants *to the platform* when uploading content; says nothing explicit about redistribution
  rights the platform grants back to the public beyond "w granicach prawa autorskiego"
  (within the limits of copyright law). No bulk-download or scraping permission is stated.
- **No public export API / no WOMI bulk endpoint.** Reader content (e.g.
  `zpe.gov.pl/a/dla-nauczyciela/D1BZ8nwuu`) is real server-rendered HTML for the page chrome,
  but the actual textbook body is injected by a client-side "Reader" module against WOMI asset
  bundles hosted on `static.zpe.gov.pl`; the CC licence badge shown to a human visitor is not
  present in the raw HTML fetched by a script. Confirmed live: `curl` of that page shows
  `api/v1` (an internal, auth-gated LMS endpoint, not a content-export API) and a `womi`
  reference, nothing else usable for automation.
- **What to actually do**: open ~10 concrete history e‑materiały in a real browser first,
  confirm the CC BY‑SA footer badge on each, then extract via a headless-browser render (not a
  raw HTTP scrape) — or ask ORE/ZPE for an official bulk export, which several other public
  bodies have received for similar OER platforms. Don't hit `api/v1` — it's internal and the
  regulamin's "don't destabilize the platform" clause plus the ambiguity on redistribution
  rights make an undocumented-API scrape a real legal grey area, not just a technical one.

### 2. Scholaris (legacy `scholaris.pl`, now folded into `zpe.gov.pl/scholaris`) — **MAYBE, per-resource only**
~25,000+ teacher resources (animacje, scenariusze, e-lekcje, teksty źródłowe). Publicly and
repeatedly documented (otwartezasoby.pl and others) that **only ~1,000 of ~26,000** resources
carry a CC BY‑SA licence; the rest are not openly licensed. The catalog UI on ZPE has a
type/subject filter (e.g. `zpe.gov.pl/scholaris?filtr_Typ=scenariusze_lekcji`) but no confirmed
licence-filter query param in this pass.

- **Verdict**: never touch the catalog in bulk. Filter to the CC BY‑SA subset first (manually,
  or by finding the right filter param), confirm the badge per resource, only then reuse.

### 3. IPN — edukacja.ipn.gov.pl (teki edukacyjne, Centralny Przystanek Historia) — **AVOID for bulk / MAYBE hand-picked**
~3,000 free PDFs/e-books, lesson folders with source cards, teacher/student materials, all
"free to download and print."

- **Licence**: standard © IPN. No CC grant or open-licence statement found anywhere on the
  portal or in its footer (checked `edukacja.ipn.gov.pl/edu/`, `.../materialy-edukacyjne`).
  Free-to-download is not the same right as free-to-redistribute-as-training-data.
- **robots.txt**: HTTP 200, `Content-Length: 0` — no rules at all (technically crawlable, but
  that says nothing about copyright).
- **Verdict**: don't scrape teki edukacyjne wholesale. A hand-picked PDF whose own colophon
  explicitly grants reuse could be used individually; otherwise this needs a written OK from
  IPN's education office before any dataset use.

### 4. Muzeum Historii Polski (muzhp.pl) — **AVOID**
Education offer (lekcje muzealne, materiały dla szkół) is delivered in person / on request via
Dział Obsługi Publiczności, not published as a scrapeable text corpus.

- **Licence**: none found; ordinary museum copyright.
- **Access**: the museum runs a public collections API at `api.muzhp.pl` (advertised via a
  Hydra/JSON-LD `apiDocumentation` link header on the site), but it sits behind **Cloudflare
  bot protection** — confirmed live: `curl https://api.muzhp.pl/` → HTTP 403 "Attention
  Required! | Cloudflare" for a scripted client.
- **Verdict**: no open licence and no scriptable access; skip.

### 5. Otwarte Zasoby (otwartezasoby.pl) — **use as a research map only, not a content source**
A WordPress blog/directory (Fundacja/KOED-adjacent) that reviews and points to open-content
sites (photos, video, music, libraries/museums/archives, education) — it hosts no history
teaching content of its own. Confirmed via its own `robots.txt` (normal WP rules + sitemap).
Useful for finding further leads (it independently corroborates the Polona and Wolne Lektury
verdicts already in `docs/historical_book_sources.md`), not as something to harvest.

## Bonus: two sources that directly match the *original* ask ("portale, które archiwizują i
indeksują książki historyczne") and are stronger than anything above

These overlap with `docs/historical_book_sources.md` — cross-check before re-adding rows.

- **Wolne Lektury** (`wolnelektury.pl`) — already catalogued there as "maybe / thin on
  historiographic syntheses." This pass found the concrete endpoint that fixes that gap:
  genre-filtered book lists are **not** a `?genre=` query param on `/api/books/` (that param is
  silently ignored — confirmed live, it returns the unfiltered 7,656-book catalog regardless of
  the query string) but a **path-composed** endpoint:
  `GET /api/genres/<slug>/books/` (documented at `wolnelektury.pl/api/`, under "Można łączyć
  autorów, epoki, gatunki i rodzaje"). Verified live for genre `kazanie` → returns exactly
  Piotr Skarga's *Kazania sejmowe* (Renesans). Genres directly useful for primary historical
  documents: `kazanie` (sermon), `pamietnik` (memoir), `dziennik` (diary), `odezwa`
  (proclamation), `manifest`, `akt-prawny` (legal act), `kronika` (chronicle),
  `rozprawa-polityczna` (political treatise), `traktat`, `list` (letters), `publicystyka`
  (journalism). Each book detail (`/api/books/<slug>/`) then gives direct `txt`/`html`/`epub`/
  `pdf`/`fb2`/`mobi` download URLs, no auth. `scripts/fetch_wolnelektury_genres.py` implements
  this and was smoke-tested live (3 books incl. Skarga's *Kazania sejmowe* and Casanova's
  memoir fragment downloaded and manifest written). **Verdict upgraded from "maybe" to "use"
  for the primary-document genres above** (still thin/irrelevant for narrative synthesis text,
  which stays Internet Archive/Wikisource's job per the existing doc).
- **Polona** (`polona.pl`) — already catalogued there as "use." Not re-verified further in this
  pass; see the existing writeup.

## Bottom line

For the hackathon's actual RAG build, none of the five OPEN SCHOOL TEXTBOOKS portals are ready
for an unattended scripted pull today — ZPE/Scholaris need a manual per-page licence check before
any extraction, IPN and MHP don't clear the bar at all for bulk reuse. The one immediately usable
addition to the corpus from this pass is the Wolne Lektury genre-filtered primary-document pull
(`scripts/fetch_wolnelektury_genres.py`), which is a genuine improvement on the existing
"maybe/thin" verdict for that source.
