# Public-domain historical books in Polish — source survey

Research pass for extending `kb/` (currently Wikipedia-only) with public-domain historical
syntheses and source documents for the HISTORY matura RAG. Timeboxed research, ~40 min.
Legal frame: Polish copyright = author's life + 70 years (art. 36 ustawy o prawie autorskim),
counted from 1 Jan of the year after death. Normative acts (ustawy, konstytucje, akty władzy
publicznej) are excluded from copyright entirely (art. 4) regardless of age. Translations are a
**separate** copyrighted work — a PD original with a modern (post-1956) translator is not PD.

No automated bulk download was performed. Everything below is metadata (URLs, licence
findings) for `sources/*.csv`; actual text must be pulled per the per-source rules below and
stays out of git per `CLAUDE.md` (own `data_cke/`-style ignored directory), only scripts +
URL lists are committed.

## Per-source verdicts

### 1. Polona (polona.pl, Biblioteka Narodowa) — **USE**
- **API**: `https://polona.pl/api/entities/` — documented, no official public docs page found,
  but reverse-engineered and used by third-party tools (e.g. [pypolona](https://github.com/twardoch/pypolona)),
  no auth token needed for read/search of public items; an official "Polona w chmurze dla
  bibliotek" (`pdb.polona.pl`) is a separate paid B2B product, not needed here. cpa.gov.pl lists
  a "Portal Dewelopera" entry for Polona but access details weren't reachable in this pass —
  treat the `/api/entities/` endpoint as the practical route.
- **Licence**: BN states "most historical objects belong to the public domain," and where that
  holds, the OCR text layer and even source XML are released on the same public-domain basis.
  Per-item rights are marked on each record (`public: true/false`, rights statement) — filter on
  that field, don't assume.
- **Text quality**: Tesseract OCR, uneven for old print/fraktur but usable; some items expose a
  searchable-text PDF rather than a plain-text layer (see pypolona notes) — plan for an OCR
  cleanup pass same as the existing CKE pipeline (`raw.txt` → `.txt`).
- **ToS caveat**: regulamin pages exist (`polona.pl/static/polona/polona-regulamin`) but did not
  yield readable clauses via fetch in this pass — before any real bulk pull, a human should
  skim it for a mass-download clause; go polite (identify UA, rate-limit, only `public:true`
  items) regardless.

### 2. Federacja Bibliotek Cyfrowych (fbc.pionier.net.pl) — **MAYBE** (router, not a text source)
- FBC is a metadata aggregator over ~130 Polish digital libraries via **OAI-PMH**
  (`.../dlibra/oai-pmh-repository.xml`), plus a CSV of all provider endpoints:
  `http://fbc.pionier.net.pl/owoc/list-libs.csv`.
- FBC's own API surfaces **metadata + thumbnails**; full OCR text stays on each source
  library's own dLibra instance (not confirmed centrally re-exposed — treat as metadata-only
  until proven otherwise for a given library).
- **Verdict**: good for *discovery* (find which regional library holds a given historical title
  and its dLibra URL), not for bulk text — go to the regional library directly per title.

### 2a–d. Regional digital libraries (dLibra, via FBC) — **MAYBE, per-item**
  - Śląska (sbc.org.pl), Wielkopolska (wbc.poznan.pl), Małopolska (mbc.malopolska.pl),
    Kujawsko-Pomorska (kpbc.umk.pl / kpbc.ukw.edu.pl).
  - All run **dLibra** ≥6, all expose OAI-PMH at `<host>/dlibra/oai-pmh-repository.xml`
    (confirmed pattern for WBC, ŚBC; same software elsewhere).
  - Full text availability is **per-item and inconsistent**: some publications are page-image
    only, some carry a DjVu/OCR text layer downloadable from the item page. No blanket answer —
    each of the ~20 candidate works below needs its item page checked individually.
  - Licence: each item states a rights status on its metadata page; historical (pre-1926,
    author-dead) items are near-universally PD, but verify per item, not per library.
  - **Verdict**: use as a *secondary/backup* source when the same title's Polona/IA scan is
    lower quality — not a first choice given the per-item text-layer uncertainty and no unified API for content.

### 3. Internet Archive (archive.org) — **USE** (best default for bulk text)
- **Search**: `https://archive.org/advancedsearch.php?q=...&output=json` (documented, no key
  needed for reasonable use).
- **Text**: every text item exposes a plain `*_djvu.txt` file (human-readable OCR) and often
  `*_hocr_searchtext.txt.gz`; item metadata gives rights status directly
  (confirmed on `dziejepolskiwza01bobrgoog`: `"NOT_IN_COPYRIGHT"` shown on-page, plus
  ABBYY OCR, EPUB, full-text `.txt`, PDF and a torrent — all freely downloadable, no login).
  Many are Google-scanned (`*goog` suffix — Michigan/Harvard library scans), which is exactly
  the source for several of the syntheses below.
- **Licence/ToS**: item-level rights metadata is authoritative; Internet Archive's own ToS
  permits programmatic access via its documented API/`advancedsearch`; be a good citizen
  (identify UA, don't hammer, batch via the CSV export it offers for a saved search) but there
  is no login/paywall/robots block for this class of content.
- **Verdict**: primary bulk-text source for the syntheses (Bobrzyński, Szujski, etc.) — best
  combination of legal clarity, OCR availability and no auth friction.

### 4. HathiTrust — **MAYBE** (good for English-language secondary lit, awkward for Polish-only pulls)
- **Data API**: id-at-a-time only ("burst activities... not large-scale retrieval") — not
  suited to a many-title pull.
- **Bulk research datasets**: HathiTrust will produce a bulk OCR dataset for "full-view"
  (=public-domain) works on request, but it is a *request-based, non-commercial-research*
  process, not a self-serve download, and volumes originally scanned by Google require an
  institutional Google Distribution Agreement to be signed first.
- **Verdict**: skip for the hackathon timebox — the request/agreement latency doesn't fit a
  40-min-to-few-day build; Internet Archive already carries copies of the same Google-scanned
  Polish-history volumes (see Bobrzyński/Szujski, both `*goog` IDs) without that friction.

### 5. Google Books — **AVOID for scraping / MAYBE for manual single downloads**
- No documented full-text bulk API for arbitrary public-domain books; the only well-documented
  bulk product is the **Ngrams** dataset (n-grams only, CC BY 3.0, not full text — useless for
  RAG passages).
- Google Books' own ToS forbids automated bulk downloading of scanned book content even when
  PD; the *sanctioned* way to get the same PD scans in bulk is via their Internet Archive
  mirrors (the `*goog` IDs above) or via HathiTrust's dataset process.
- **Verdict**: avoid programmatic scraping of books.google.com entirely; when a title exists
  only there, prefer manually fetching the single "Download PDF" for that one item over any
  script, or better, look for the same `*goog`-suffixed item on Internet Archive first.

### 6. Wikisource PL (pl.wikisource.org) — **USE** (best for primary/legal source texts)
- **API**: standard MediaWiki API (`/w/api.php`, `action=query&prop=revisions&rvprop=content`)
  plus `Special:Export` for wikitext dumps — no auth, well documented, rate-friendly.
- **Licence**: CC BY-SA 3.0 / GFDL for wiki-contributed markup and annotations, but the
  **underlying historical source texts themselves are public domain** (that's the whole point
  of Wikisource) — safe for a non-commercial dataset either way.
- **Confirmed present**: "Ustawa rządowa czyli Konstytucya 3 maja 1791" (full text, clean),
  Volumina Legum volumes (partially transcribed, e.g. tom VII; tom II — which holds the 1573
  Henrician Articles and the 1569 Union of Lublin act — was not confirmed transcribed in this
  pass, check `Kategoria:Volumina Legum` on-wiki before assuming), author pages for Lelewel and
  Korzon with linked works.
- **Text quality**: hand-transcribed/proofread wikitext — the cleanest text of any source here,
  no OCR noise. Best fit for short high-value primary documents (constitutions, acts, treaties).
- **Verdict**: first choice for primary/legal documents; check per-title for historiographic
  syntheses (coverage of 19th-c. historians is partial).

### 7. Wolne Lektury (wolnelektury.pl) — **MAYBE → upgraded to USE for primary-document genres (see 2026-09-25 follow-up below)**
- **API**: `https://wolnelektury.pl/api/` — documented REST, JSON default/`?format=xml`,
  endpoints for `/books/`, `/authors/`, `/epochs/`, `/genres/`, `/themes/`, no auth/rate limit
  documented. No bulk full-corpus zip/dump endpoint was found in the developer docs page in
  this pass (worth a follow-up look at `wolnelektury.pl/info/` for a "cały korpus" archive).
- **Licence**: public domain or CC BY-SA / Wolna Licencja Sztuki (project switched from CC
  BY-SA to WLS in 2022) — either way safe for a non-commercial dataset, attribution recommended.
- **Text quality**: clean, proofread, multiple formats (txt/html/epub/mobi/pdf/xml) per book via
  the API.
- **Verdict**: catalogue is curated for the *literary canon* (lektury szkolne) — good for
  period-flavour primary voices (pamiętniki, listy, publicystyka) but thin on historiographic
  syntheses; use as a supplement, not the backbone.

**Follow-up (2026-09-25, from the open-school-textbooks research pass — see
`docs/open_school_textbook_sources.md`)**: the "no bulk full-corpus endpoint found" note above
was because the obvious query params don't work — confirmed live that both
`/api/books/?genre=<slug>` and `/api/books/?epoch=<slug>` are **silently ignored** and return the
same unfiltered 7,656-book list regardless. The real, documented mechanism (spelled out on
`wolnelektury.pl/api/` itself, "Można łączyć autorów, epoki, gatunki i rodzaje") is a
**path-composed** endpoint: `GET /api/genres/<slug>/books/`. Verified live for `kazanie` → returns
exactly Piotr Skarga's *Kazania sejmowe*. This makes the primary-document genres
(`kazanie`, `pamietnik`, `dziennik`, `odezwa`, `manifest`, `akt-prawny`, `kronika`,
`rozprawa-polityczna`, `traktat`, `list`, `publicystyka`) cleanly scriptable —
`scripts/fetch_wolnelektury_genres.py` does this and was smoke-tested (3 books, incl. Skarga
and a Casanova memoir fragment, downloaded successfully). Verdict for these genres upgraded to
**use**; `sources/portals.csv`'s Wolne Lektury row was updated to match.

## Candidate high-value works (with exact URLs found)

| # | Work | Author (dates) | PD status | Best source (URL) | Notes |
|---|---|---|---|---|---|
| 1 | Dzieje Polski w zarysie, t. 1–2 (1879) | Michał Bobrzyński (1849–1935) | PD | https://archive.org/details/dziejepolskiwza01bobrgoog ; https://polona.pl/preview/60dfe59f-b849-4f1a-8a57-f60872cdf057 | IA copy confirmed `NOT_IN_COPYRIGHT`, has djvu.txt/full text |
| 2 | Dzieje Polski w zarysie, t. 1 (alt. scan) | Bobrzyński | PD | https://archive.org/details/MichaBobrzyskiDziejePolskiWZarysieTom1 | second IA copy |
| 3 | Dzieje Polski, t. 1–4 (1862–66, ed. 1894–95) | Józef Szujski (1835–1883) | PD | https://archive.org/details/dziejepolski01szujgoog ; https://polona.pl/item/dzieje-polski-t-1,MTE3MTY0NDM/ ; https://www.wbc.poznan.pl/dlibra/publication/68237 | 4-volume synthesis, good matura coverage Piastowie→1795 |
| 4 | Works of Joachim Lelewel (collected) | Joachim Lelewel (1786–1861) | PD | https://pl.wikisource.org/wiki/Autor:Joachim_Lelewel ; https://polona.pl/public-collections/collection/5fe641ec-24de-480b-ae20-eae52762a497 | Wikisource has clean partial texts; Polona has full scans of many titles |
| 5 | Works of Tadeusz Korzon | Tadeusz Korzon (1839–1918) | PD | https://pl.wikisource.org/wiki/Autor:Tadeusz_Korzon ; https://polona.pl/search/?query=Tadeusz_Korzon | historian of the Sejm Wielki era, Kościuszko |
| 6 | Dzieje narodu polskiego / works of Adam Naruszewicz | Adam Naruszewicz (1733–1796) | PD | search polona.pl for "Naruszewicz Historia narodu polskiego" | 18th-c. synthesis, not yet URL-verified — verify before use |
| 7 | Napoleon a Polska / Łukasiński (works) | Szymon Askenazy (1865–1935) | PD | search polona.pl / archive.org for "Askenazy" | not yet URL-verified — verify before use |
| 8 | **Oskar Halecki's own syntheses** (Historia Polski etc.) | Oskar Halecki (1891–**1973**) | **NOT PD until 2044** | — | died 1973 → 70 pma runs to end of 2043; **AVOID**, regardless of original publication date |
| 9 | Ustawa rządowa czyli Konstytucya 3 maja 1791 | — (act of law) | PD (excluded from copyright as a legal act, also age) | https://pl.wikisource.org/wiki/Ustawa_rz%C4%85dowa_czyli_Konstytucya_3_maja_1791 ; https://biblioteka.sejm.gov.pl/tek01/txt/kpol/1791.html | clean transcribed text, best primary-source pick |
| 10 | Artykuły henrykowskie (1573) | — (act of law) | PD | full text is in *Volumina Legum* t. II; check https://pl.wikisource.org/wiki/Kategoria:Volumina_Legum for a transcribed copy, else scan via Polona/IA | text existence on Wikisource not confirmed this pass — verify before relying on it |
| 11 | Akt unii lubelskiej (1569) | — (act of law) | PD | same as above — via Volumina Legum t. II, not yet found transcribed on Wikisource | verify before use; fall back to a Polona/IA scan of Volumina Legum |
| 12 | Manifest PKWN (22 lipca 1944) | — (state proclamation) | PD (official document, also age) | https://polona.pl/preview/1d66bb1a-6b82-4ccb-a741-ea58a559373c ; https://fbc.pionier.net.pl/publication/3e8d14311e34dde6c51f | confirmed PD by multiple secondary sources |
| 13 | Konstytucja marcowa (1921) | — (act of law) | PD | search biblioteka.sejm.gov.pl / Wikisource | not yet URL-verified |
| 14 | Konstytucja kwietniowa (1935) | — (act of law) | PD | search biblioteka.sejm.gov.pl / Wikisource | not yet URL-verified |
| 15 | Kronika polska (Gall Anonim) | Gall Anonim (12th c.) / trans. Roman Grodecki (d. 1954) | PD original; **translation PD only from 2025** (just crossed) | search Wikisource/Polona — not yet URL-verified | translation copyright is separate — recheck the exact translator/edition before use |
| 16 | Roczniki, czyli Kroniki... Królestwa Polskiego | Jan Długosz (1415–1480) / modern PAN translators (mostly post-1950s) | Original PD; **modern translation likely still copyrighted** | — | high risk: use only a pre-1950s Polish edition/translation if one exists, else skip |
| 17 | Volumina Legum (compiled 1732–82, republished 1859–89) | multiple, all long PD | PD | https://pl.wikisource.org/wiki/Encyklopedia_staropolska/Volumina_legum ; https://pl.wikisource.org/wiki/Volumina_Legum._Tom_VII | partial coverage on Wikisource; full set of scans also on Polona/IA |

Rows 6, 7, 13–17 are **leads, not verified URLs** — the 40-minute timebox ran out before every
row could be individually confirmed; `sources/works_catalog.csv` marks each row's
`verified` column accordingly so a follow-up pass knows what still needs a source check before
anything is downloaded.

## Bottom line for the RAG build

1. **Wikisource PL** for primary/legal texts (constitutions, acts, treaties) — cleanest text,
   clear PD, tiny download.
2. **Internet Archive** for the historiographic syntheses (Bobrzyński, Szujski, Lelewel,
   Korzon) — clear PD marking, plain-text OCR already extracted, no auth.
3. **Polona** as the enrichment/cross-check layer (better scans, Polish-specific metadata,
   sometimes the only copy) — filter strictly on its own `public`/rights field per item.
4. Regional dLibra libraries and FBC: use only for discovery/backup, not as a primary bulk-text
   pipeline (no unified full-text API, per-item availability).
5. Skip Google Books scraping and HathiTrust's request-based bulk process for this timebox;
   skip Oskar Halecki entirely (not PD until 2044).
6. Keep no downloaded book text in git — same pattern as `data_cke/`: raw text in an ignored
   working directory, only `sources/*.csv` (URL + licence metadata) and fetch scripts committed.
