# Books dataset: build plan (next ~6 h)

Date: 2026-09-26. This builds on `docs/historical_book_sources.md`, `docs/open_school_textbook_sources.md`,
`docs/book_archive_sources.md` and `sources/*.csv`. Every URL, licence template, translator and file size below
was checked live on 2026-09-25/26 through the Wikisource MediaWiki API, the Wolne Lektury API and archive.org
metadata, unless it is marked **(lead)**.

## 0. Findings that change the earlier reports

1. **Wikisource pages are mostly ProofreadPage transclusions.** The raw wikitext of *Konstytucja 3 maja*, *Konstytucja marcowa*,
   *Konstytucja kwietniowa*, *Manifest PKWN* and *Ustawa Konstytucyjna KP 1815* is only 500–1,000 bytes of `<pages index=…/>`
   tags. As a result, `scripts/fetch_historical_sources.py` (`prop=revisions`) returns **no text** for them. Use
   `action=parse&prop=text` (rendered HTML) instead. For example, *Konstytucja marcowa* comes back as 5,663 words. Multi-page works have a `/całość` subpage.
2. **Wikisource rate-limits bursts.** About 15 search calls in a few seconds returned HTTP 429. Send one request every 3 s or slower, with
   `maxlag=5`, a descriptive User-Agent, and honour `Retry-After`. Batch `prop=info|templates` calls (up to 50 titles each) for metadata.
3. **The Gall Anonim translation risk is resolved.** Wolne Lektury `gall-anonim-kronika-polska` uses the translation by **Zygmunt Komarnicki,
   Warszawa 1873** (colophon checked), so it is public domain. The Grodecki translation is not needed.
4. **Wikisource also hosts openly licensed modern historiography**, which neither earlier report found:
   - Henryk Zieliński, *Historia Polski 1914–1939* (Ossolineum 1982): template `Cc-by-sa-3.0-tekst` + `GFDL-tekst`, 151,687 words, proofread.
   - Andrzej Paczkowski, *Trzy twarze Józefa Światły*: `Cc-by-3.0-pl-tekst`, 96,160 words.
5. **A clean school-level narrative of all of Polish history is available:** Cecylia Niewiadomska (d. 1938, so PD),
   *Legendy, podania i obrazki historyczne*, about 17 booklets on Wikisource, 7–12k words each, proofread.
6. **Old syntheses have outdated facts.** Bobrzyński's OCR text, for example, gives Chrobry's reign as ending in "1026". Archaic
   spelling (*Historya*, *Szwecyi*, *przedewszystkiem*) also hurts BM25 matching against modern queries. The consequence is that 19th-c. OCR books are **RAG-only / low priority**. Question
   generation should use the primary documents plus Niewiadomska, Zieliński and Grabiec, with a Wikipedia cross-check (§4b).
7. **Repo rule conflict.** `CLAUDE.md` says: "Training targets come from open-weight generators (not Claude outputs) unless organizers
   confirm otherwise". The brief asks for Claude-generated training questions, and `train/datagen/claude_*` already exists.
   **Get organizer confirmation before training on these.** If they do not confirm, run the same batches through the open-weight generator.

## 1. Ranked sources (clearly legal only)

| rank | source | why | access |
|---|---|---|---|
| 1 | **Wikisource PL** (pl.wikisource.org) | Hand-proofread text with no OCR noise. Legal acts are marked `PD-ineligible` (art. 4 pr. aut.) and old texts `PD-old`/`MixPD`. There are also a few CC-licensed modern monographs. | MediaWiki API `action=parse`, no auth |
| 2 | **Wolne Lektury** (wolnelektury.pl) | Proofread `.txt` with colophons stating the source edition and translator. The texts are PD, and WL's notes are under Licencja Wolnej Sztuki 1.3. | `/api/books/<slug>/` → `txt` URL, no auth |
| 3 | **Internet Archive** (archive.org) | Ready `*_djvu.txt` OCR. Items marked `NOT_IN_COPYRIGHT`, or with the author dead >70 years. It is the sanctioned mirror of Google scans. | `archive.org/metadata/<id>` → `*_djvu.txt` |
| – | Polona, FBC, dLibra | Scans only, needing OCR and a per-item rights check. Use only as a fallback for missing volumes (Szujski t. 4 → WBC). | manual |
| ✗ | Google Books scraping, HathiTrust bulk, IPN, MHP, ZPE/Scholaris bulk | ToS, licence or access blockers (see the earlier reports). | – |

Wikidata (CC0, `kb/external_sources/`) stays a separate structured-facts track and is not part of this books dataset.

## 2. Works to download first (46 core + 8 optional)

`est. words` comes from Wikisource `wordcount` or from bytes/7 for `.txt`. Legend: **Q** = feed to question generation,
**R** = RAG index only, **QR** = both.

### Tier A: primary documents, Wikisource (clean, about 40k words total, all Q R)

Base URL is `https://pl.wikisource.org/wiki/<title>`. Fetch with `action=parse&page=<title>`.

| id | title (Wikisource page) | licence template / basis | est. words |
|---|---|---|---|
| A01 | `Akt konfederacji warszawskiej` (1573) | PD-old | 0.9k |
| A02 | `Traktat wieczystej przyjaźni pomiędzy Rosją a Rzecząpospolitą (1768)` | PD-old | 2.4k |
| A03 | `Ustawa rządowa czyli Konstytucya 3 maja 1791` | PD-ineligible (legal act) | 4k |
| A04 | `Zaręczenie Wzajemne Obojga Narodów` (1791) | PD-ineligible | 0.7k |
| A05 | `Akt powstania kościuszkowskiego` (1794) | PD-old | 1.6k |
| A06 | `Uniwersał Połaniecki` (1794) | MixPD (18th-c. text) | 1.5k |
| A07 | `Konstytucja Księstwa Warszawskiego` (1807) | PD-ineligible | 2.6k |
| A08 | `Ustawa Konstytucyina Królestwa Polskiego` (1815) | PD-old | 4.5k |
| A09 | `Manifest Tymczasowego Rządu Narodowego (1863)` | PD-old | 0.6k |
| A10 | `Akt 5 listopada (1916)` | PD-ineligible | 0.2k |
| A11 | `Mała Konstytucja z 1919` | PD-old | 0.2k |
| A12 | `Konstytucja marcowa (1921)` | PD-old / legal act | 5.7k |
| A13 | `Konstytucja kwietniowa (1935)` | PD-ineligible | 5k |
| A14 | `Manifest Polskiego Komitetu Wyzwolenia Narodowego` (1944) | PD-ineligible | 1.8k |
| A15 | `Mała Konstytucja z 1947` | PD-ineligible | 1.3k |
| A16 | `21 postulatów Międzyzakładowego Komitetu Strajkowego z 17 sierpnia 1980` | PD-ineligible | 0.5k |
| A17 | `Protokół ustaleń MKS z komisją rządową w Gdańsku (1980)` | PD-ineligible | 3.3k |

### Tier B: chronicles, treatises, memoirs, Wolne Lektury `.txt` (PD; colophon per book)

URL: `https://wolnelektury.pl/media/book/txt/<slug>.txt`

| id | slug | work (edition per colophon) | size | use |
|---|---|---|---|---|
| B01 | `gall-anonim-kronika-polska` | Gall Anonim, *Kronika polska*, tr. Komarnicki 1873 | 270 KB ≈ 38k w | QR |
| B02 | `krotka-rozprawa-miedzy-trzemi-osobami` | Rej, *Krótka rozprawa…* | 73 KB | QR |
| B03 | `o-poprawie-rzeczypospolitej` | Modrzewski, tr. Bazylik (ed. 1857) | 741 KB | R (+Q on 3–4 chapters) |
| B04 | `skarga-kazania-sejmowe` | Skarga, *Kazania sejmowe* (already in `sources/raw/wolnelektury/`) | 225 KB | QR |
| B05 | `pamietniki` | Pasek, *Pamiętniki* | 743 KB | R (+Q sample) |
| B06 | `kitowicz-opis-obyczajow-i-zwyczajow-za-panowania-augusta-iii` | Kitowicz | 865 KB | R |
| B07 | `przestrogi-dla-polski` | Staszic, *Przestrogi dla Polski* | 349 KB | QR |
| B08 | `kilinski-pamietnik` | Kiliński, *Pamiętnik* (1794) | 218 KB | QR |
| B09 | `slomka-pamietniki-wloscianina-od-panszczyzny-do-dni-dzisiejszych` | Słomka (d. 1932) | 747 KB | QR |
| B10 | `krahelska-oswiecim-pamietnik-wieznia` | Krahelska (d. 1945), AK ed. 1942 | 118 KB | QR |
| B11 | `daszynska-golinska-prawo-wyborcze-kobiet` | Daszyńska-Golińska | 39 KB | QR |
| B12 | `mazurek-dabrowskiego` | Wybicki | 2 KB | R |
| B13 | `stryjkowski-kronika-polska-litewska-zmudzka-i-wszystkiej-rusi` | Stryjkowski | 489 KB | R |

### Tier C: Niewiadomska, *Legendy, podania i obrazki historyczne* (Wikisource, PD, about 150k words, all QR)

Fetch `<title>/całość` when it exists, otherwise `<title>`. Titles come from the links on `Autor:Cecylia Niewiadomska`. **Confirm each
against the series index page `Legendy, podania i obrazki historyczne` before fetching.**

C01 `Czasy przedchrześcijańskie` · C02 `Lat temu dziewięćset` · C03 `Chrobry` · C04 `Bolesław Śmiały, Krzywousty i jego synowie` ·
C05 `Leszek Biały — Bolesław Wstydliwy` · C06 `Łokietek — Kazimierz Wielki` · C07 `Jadwiga i Jagiełło` · C08 `Jagiellonowie` ·
C09 `Rey — Kochanowski` · C10 `Królowie obieralni: Henryk, Stefan Batory` · C11 `Wazowie (Niewiadomska)` · C12 `Sobieski (Niewiadomska)` ·
C13 `Czasy saskie, Stanisław August Poniatowski` · C14 `Kościuszko — Książę Józef` · C15 `Królestwo Polskie 1815—31` (10.4k w) ·
C16 `Emigracja — Rok 1863` · C17 `Królestwo Polskie po roku 1815` (7.4k w)

Caveat: these are 1917–25 youth booklets, so drop passages explicitly framed as legends ("podanie głosi…") before question generation.

### Tier D: syntheses

| id | work | source / URL | licence basis | format, size | use |
|---|---|---|---|---|---|
| D01 | **H. Zieliński, *Historia Polski 1914–1939*** (1982) | WS `Historia Polski (Henryk Zieliński)/całość` | CC BY-SA 3.0 + GFDL (WS template) | clean, 152k w | **QR** |
| D02 | J. Dąbrowski (Grabiec), *Powstanie Styczniowe 1863—1864* | WS `Powstanie Styczniowe 1863—1864/całość` | author d. 1936 → PD | clean, 64k w | QR |
| D03 | J. Grabiec, *Sto lat walki o prawa Królestwa Polskiego 1815—1915* | WS same title | PD (TekstPD) | clean | QR |
| D04 | A. Świętochowski, *Historja chłopów polskich w zarysie* t. I (+ t. II) | WS `…/Tom I/całość` | d. 1938 → PD | clean, 116k w (t. I) | QR |
| D05 | M. Bobrzyński, *Dzieje Polski w zarysie* (1887 / 1890 eds) | IA `dziejepolskiwza01bobrgoog`, `dziejepolskiwza00bobrgoog` | NOT_IN_COPYRIGHT; d. 1935 | OCR, 717 + 790 KB | R (+Q after cross-check) |
| D06 | S. Kutrzeba, *Historya ustroju Polski w zarysie* (1912) t. 1–4 | IA `historyaustrojup01kutr` … `04kutr` | d. 1946 → PD since 2017 (IA field empty, so the basis is the death date) | OCR, 0.58/0.49/0.65/0.72 MB | R (t. 1 Q) |
| D07 | J. Szujski, *Dzieje Polski* t. 1–3 (1894–95) | IA `dziejepolski01szujgoog`, `02`, `03` (t. 4 not on IA → WBC 68237) | NOT_IN_COPYRIGHT; d. 1883 | OCR, 1.1/2.5/0.96 MB | R |
| D08 | T. Korzon, *Kościuszko: biografia z dokumentów wysnuta* (1894) | IA `kociuszkobiogra00korzgoog` | NOT_IN_COPYRIGHT; d. 1918 | OCR, 2.0 MB | R |
| D09 | W. Kalinka, *Sejm Czteroletni* | IA `sejmczteroletni00kaligoog` | NOT_IN_COPYRIGHT; d. 1886 | OCR, 1.5 MB | R |
| D10 | Sz. Askenazy, *Napoleon a Polska* t. 1 (1918) | IA `napoleonpolska01askeuoft` | NOT_IN_COPYRIGHT; d. 1935 | OCR, 0.86 MB | R |
| D11 | J. Lelewel, *Dzieje Polski potocznym sposobem opowiedziane* (1859) | IA `polska.-dzieje-i-rzeczy-jej-t.-2-1859` | d. 1861 | OCR, 0.45 MB | R |

**Optional (after the core set works):** D12 Paczkowski, *Trzy twarze Józefa Światły* (WS, CC BY 3.0 PL, 96k w, QR) ·
D13 Korzon, *Wewnętrzne dzieje Polski za St. Augusta* t. 1 (IA `wewntrznedziejep01korzuoft`, 1.2 MB, R) ·
D14 Nowakowski/Szwarce, *Warszawa w 1794 roku* (WS, PD) · D15 *Kronika Jana z Czarnkowa* (WS, MixPD; check translator) ·
B14 Dembołęcki, *Pamiętniki o Lisowczykach* (WL) · **(lead)** `Pacta conventa` (WS, GFDL wiki translation; check which king) ·
**(lead)** `Krzyżacy (Samsonowicz, 1988)` (WS says MixPD but the author d. 2021, so check the licence on the author page; skip if unclear) ·
**(lead)** Mecherzyński's 1867–70 Długosz translation (Polona/IA, not located yet).

**Skip:** Halecki (d. 1973), modern Długosz/Kadłubek translations, anything with `access-restricted-item=true` on IA, the Latin-only
`Literae confirmationis articulorum Henrico…`.

**Volume:** about 3M words (about 20 MB of text) in total, of which about 0.8M words are clean Q-grade text. Books would add about 18k BM25 chunks, 0.5% of the Wikipedia index.

## 3. Pipeline (`train/books/`)

All text output goes to `sources/raw/books/` (already git-ignored via `sources/raw/`), and indexes go to `kb_data/` (ignored).

| file | does |
|---|---|
| `train/books/manifest.csv` (commit) | One row per work: `id,tier,title,author,author_death,backend,locator,licence,pd_basis,use,est_words,priority`. `backend` ∈ `wikisource,wolnelektury,archive`. Built from §2. |
| `train/books/fetch.py` | Three backends. **wikisource:** `action=parse&prop=text&formatversion=2&redirects=1&maxlag=5`, try `<title>/całość` first; 1 req per 3 s; retry on 429/503 with `Retry-After`; also records `prop=templates` licence templates and aborts if none match `PD-*`, `MixPD`, `TekstPD`, `Cc-by*` or `GFDL`. **wolnelektury:** `/api/books/<slug>/` → `txt`; saves the colophon (text after the last `-----`) to `<id>.attribution.txt`. **archive:** `/metadata/<id>` → first `*_djvu.txt`; refuse if `access-restricted-item` is set; log `possible-copyright-status`. Writes `sources/raw/books/raw/<id>.{html,txt}` and `fetch_log.jsonl` (url, bytes, sha256, licence, retrieved_at). Idempotent (skips existing files unless `--force`). |
| `train/books/clean.py` | Per backend. **WS HTML:** drop the "Dane tekstu" header table, `.ws-noexport`, `.pagenum` / `[ 12 ]` markers, `↑` footnote backlinks and the licence footer ("Tekst jest własnością publiczną…"); turn h2/h3 into `#`/`##` markers. **WL txt:** drop the header (author/title/ISBN) and the footer after `-----`; drop footnote markers. **IA OCR:** (1) cut the Google boilerplate (EN "This is a digital copy…" and PL "Jest to cyfrowa wersja…" blocks); (2) drop page-number lines `^\s*\d{1,4}\s*$` and running heads (short lines repeated ≥5×); (3) drop marginalia (isolated lines under 4 words between blank lines) and footnote blocks (lines starting `») `, `*) `, `1) ` at page bottom); (4) **de-hyphenation:** join `(\w)[-¬­]\s*\n\s*([a-ząćęłńóśźż])`; keep the hyphen only if the hyphenated form occurs elsewhere in the same book (`polsko-litewski`); (5) unwrap lines into paragraphs; (6) NFC, ligatures/`ſ`, quotes; (7) **quality gate:** per 500-word window, the share of tokens found in the Wikipedia KB vocab (`kb/textnorm` on `kb_data/index/chunks.vocab.npy`) must be ≥ 0.80, otherwise drop the window (tables, indexes, garbage OCR); also drop "Spis rzeczy / Skorowidz / Errata" sections. Output `clean/<id>.md` + `clean_stats.csv` (kept/dropped words per work). Spot-check 3 random windows per OCR work by eye. |
| `train/books/segment.py` | Splits each work into **article-like units**. Headings: WS/WL markers; OCR regexes `^§\.?\s*\d+\.` (Bobrzyński), `^ROZDZIA[ŁL]`, `^Rozdział`, `^[IVXLC]+\.\s`, `^KSIĘGA`. Target 600–2,500 words: split longer ones at paragraph breaks (`— cz. 2`), merge shorter with the next one. The primary documents in Tier A are split by chapter/article group (e.g. *Konstytucja marcowa — Rozdział II. Władza ustawodawcza*). Output `articles.jsonl`: `{art_id, work_id, title, url, licence, era, words, text}`. Title = `<Author short>, <Work short> — <heading>`. `url` = the source page (for IA, `https://archive.org/details/<id>/page/n<N>` if the page index is known). `era` comes from the manifest or the heading years, for balancing. |
| `train/books/make_batches.py` | Writes the generator's exact format, 20 articles per file, to `sources/raw/books/batches/books_batch_NNN.md`:<br>`### ARTYKUŁ: <title>`<br>`URL: <url>`<br>`<text>`<br>(blank line between articles; no extra header lines, because the generator treats everything after `URL:` as text). Filter `use ∈ {Q,QR}`. Interleave works and eras so each batch spans 3+ eras, like the Wikipedia batches. Cap each article at `--max-chars 12000` (truncate at a paragraph boundary). Sidecar `batches/index.jsonl` maps `title → work_id, licence, url` so that `source_title`/`source_url`/`licence` can be back-filled into the generated questions. |
| `train/books/build_kb_parquet.py` | Articles → 120–250-word chunks (reuse `kb.build_chunks.pack`) → parquet with the exact `kb.build_chunks.SCHEMA`: `page_id = 900_000_000 + n`, `section = heading`, `text = "<title> — <heading>\n<chunk>"`, `incoming_links=0`, `popularity_score=0`, `hist_score=5`, `categories="ksiazki|<tier>"`. Then `python -m kb.build_index --chunks kb_data/books_chunks --out kb_data/index_books --workers 4` (seconds). Optional index-only spelling normalizer (`-yi`→`-ji`, `-ya`→`-ja`, `przedewszystkiem`→`przede wszystkim`), applied only to the indexed text and never to the display text. |

## 4. Uses

### (a) Offline RAG: secondary, off by default

- Use a **separate index** (`kb_data/index_books`), not a merge. Merging would shift the IDF of the Wikipedia index and bypass the tuned article-level/inlink priors, which books do not have.
- Harness hook: in `harness/retrieval.py`, add an optional second `KB(KB_BOOKS_INDEX_DIR)`. Its hits go into `fuse()` as one more result list with
  weight `BOOKS_WEIGHT` (default **0 = off**), with at most 1 book chunk in the packed context, labelled with the work title.
- Turn it on only if the A/B on `devset/dev-*.jsonl` (`devset/eval.py`) shows no regression. The exam questions come from Wikipedia, so the expected gain is small. The
  most likely benefit is for primary-document questions (constitution articles, manifestos). Do not rerun `kb/tune.py` weights for this.
- Offline and size limits are fine: the index is local and tens of MB, with no model involved.

### (b) Source texts for training questions (same generator + verifier as Wikipedia)

1. Run the generator on `books_batch_*.md`. Expect about 44 questions per 20-article batch (Wikipedia run: 1,334 questions / 30 batch files), so the
   target is about 30 batches ≈ 1,200–1,300 raw questions. Suggested mix: all of Tier A, Niewiadomska, Zieliński, Grabiec, Gall, Świętochowski t. I, Staszic, Kiliński,
   Słomka, plus Bobrzyński §§ only if time allows.
2. Add one line to the generator prompt: *questions must be about historical facts, not about "the text"; do not ask about claims that
   modern historiography rejects*. This keeps the style identical to the Wikipedia-derived exam.
3. Run the existing verifier (answer supported by `evidence` from the article).
4. **New gate: Wikipedia cross-check.** Run `kb.search(question, k=8)` on the main index and have an LLM judge whether the Wikipedia chunks support
   the gold answer. Keep `supported` rows and drop `contradicted`. `no_evidence` rows are kept only for "no-context" training variants.
   This removes outdated 19th-c. claims and preserves train/inference parity (the model sees Wikipedia context at inference).
5. Dedupe against `devset/*.jsonl` (normalized 5-gram Jaccard > 0.5 or same `answer` + same entity → drop), because dev sets must never leak into
   training. Also dedupe against `train/datagen/claude_verified/`.
6. Output goes to `train/datagen/books_raw/` and `books_verified/` with the Wikipedia schema plus `licence` and `work_id`.
7. The training-target rule in §0.7 applies: organizer OK is needed for Claude-generated targets, otherwise use an open-weight generator.

## 5. Git: what may and may not go in

**Commit:** `train/books/*.py`, `train/books/manifest.csv`, this plan, `DATA_SOURCES.md`, small stats
(`clean_stats.csv`, `fetch_log.jsonl` without text), and verified question JSONL whose `evidence` quotes are ≤ 300 chars and carry `licence` + `source_url`.

**Never commit** (all under ignored `sources/raw/` or `kb_data/`): raw or cleaned book text, batches `.md`, `articles.jsonl`, parquet, index.
This includes PD and CC texts: the repo convention (`CLAUDE.md`, `.gitignore`) is URL list + script. CC BY-SA/GFDL texts (Zieliński) are
copyrighted-but-licensed, and the hackathon rule says to list them and script the download. Nothing from IPN, ZPE, Scholaris, MHP, Google Books or HathiTrust.

**`DATA_SOURCES.md` entries (to add):**

```markdown
## Historical books / primary documents (downloaded by train/books/fetch.py; texts NOT in repo)
- Wikisource (pl.wikisource.org) — transcriptions CC BY-SA 3.0 / GFDL; underlying texts public domain
  (PD-old, or PD-ineligible: normative acts/official documents, art. 4 ustawy o prawie autorskim).
  Works: see train/books/manifest.csv (tiers A, C, D01–D04). Attribution: "Wikiźródła, wolna biblioteka", page URL per record.
- Henryk Zieliński, "Historia Polski 1914–1939", Ossolineum 1982 — via Wikisource, CC BY-SA 3.0 + GFDL
  (https://pl.wikisource.org/wiki/Historia_Polski_(Henryk_Zieliński)). Derived data inherit BY-SA; non-commercial use here.
- [optional] Andrzej Paczkowski, "Trzy twarze Józefa Światły" — via Wikisource, CC BY 3.0 PL.
- Wolne Lektury (wolnelektury.pl), Fundacja Wolne Lektury — public-domain texts; editorial notes under Licencja Wolnej Sztuki 1.3
  (https://artlibre.org/licence/lal/pl/); use per https://wolnelektury.pl/info/zasady-wykorzystania/. Source edition per book
  colophon (e.g. Gall Anonim, tr. Z. Komarnicki, Warszawa 1873).
- Internet Archive (archive.org) — public-domain scans (NOT_IN_COPYRIGHT or author d. > 70 years), OCR *_djvu.txt; Google-digitized
  items (*goog) used non-commercially per Google's usage notice. Item IDs in manifest.csv.
- All derived data (indexes, generated questions) are non-commercial, per hackathon rules.
```

## 6. Time plan (about 6 h, one person plus the generator running in the background)

| step | time | cut line if late |
|---|---|---|
| 0. Organizer question on Claude targets (§0.7), in parallel | 5 min | – |
| 1. `manifest.csv` from §2 | 20 min | – |
| 2. `fetch.py` (3 backends) + run (WS about 50 pages × 3 s ≈ 3 min; IA about 15 files ≈ 20 MB) | 45 + 15 min | drop the IA backend (Tier D05–D11) |
| 3. `clean.py` + spot checks | 60 + 15 min | WS/WL cleaning only (15 min), skip OCR |
| 4. `segment.py` + `make_batches.py` | 45 min | – |
| 5. Generator on about 30 batches (background) + verifier + Wikipedia cross-check + dedupe | 60–90 min wall | 15 batches |
| 6. `build_kb_parquet.py` + `index_books` + harness hook + dev A/B | 20 + 40 min | skip; RAG is secondary |
| 7. `DATA_SOURCES.md`, README row in `sources/README.md` | 15 min | – |
| **total** | **≈ 5 h 30 min – 6 h** | Minimum viable path (Tiers A+B+C + D01–D04, clean text only, no OCR): about 3 h 30 min |
