# Próbne zgłoszenia — pakiet mock (CKE maj 2023, `history-2023-mock-v1`)

Pliki `answers.json` do wysłania na stronę organizatorów (Mock exam). Każdy katalog = jeden system.
`answers.json` i `debug.jsonl` są w `.gitignore` (debug zawiera tekst arkusza CKE; odpowiedzi na razie też poza gitem).

## System finałowy: model wizyjny opisuje obrazy, Bielik odpowiada (26.09, ok. 18:30)

**OCR odpada decyzją zespołu.** W finałowym potoku nie ma OCR (Tesseract), więc wariant `-ocr` opisany niżej
nie jest już planowaną konfiguracją finału. Zamiast OCR działa JEDEN otwarty model wizyjny, który tylko zamienia
każdy obraz arkusza w polski opis. Nie widzi pytania i na nic nie odpowiada. Na wszystkie zadania odpowiada
wyłącznie Bielik-4.5B-v3 i dostaje sam tekst.

- **Model wizyjny:** Qwen3.5-9B Q5_K_M + mmproj F16 (`unsloth/Qwen3.5-9B-GGUF`, apache-2.0), razem 7,5 GB.
  Wygrał ślepą ocenę 5 modeli na 19 obrazach mocka: średnio 6,82/10 i najmniej zmyśleń (12). Szczegóły są
  w `docs/vision_describer_eval.md`.
- **Opisy:** `scripts/describe_images.py`. Model dostaje obraz i podpis źródła z arkusza, nigdy pytanie.
  Prompt w wersji `6ddd83756917`, thinking wyłączony, T=0, `max_tokens` 600. Serwer: `-c 8192 -np 1 --cache-ram 0 -fa on`.
  Wynik dla mocka: `data_cke/mock2023/image_vlm_qwen35-9b-q5km.json`, 19 obrazów, średnio 10,6 s na obraz.
- **Do Bielika** opis trafia jako `[Opis obrazu: …]` w miejscu znacznika `[Obraz: images/X.png]`.

| katalog | konfiguracja | walidacja | czas / zadanie: śr. · med. · maks. | suma | wypracowanie (id 26) |
|---|---|---|---|---|---|
| `bielik45-harness-v3-vlm-qwen35-9b-q5km` | harness v3 (`CKE_MODE=1 QTYPE_V2=1 RERANK=1`, `DENSE=0`, LoRA niezaładowana) + opisy Qwen3.5-9B | VALID, 37/37, 0 błędów, 0 ostrzeżeń | 28,1 · 27,9 · 65,7 s | 1041 s (ok. 5,5 min zegarowo przy 4 zadaniach naraz) | 596 wyrazów |

- Przebieg: L40S, kopia `/scratch/mock/wmt-matura` z aktualnym `harness/` z laptopa. Bielik to nietknięty
  serwer Q8_0 bez LoRA (`127.0.0.1:18093`, współdzielony z próbkowaniem RFT i dwiema ewaluacjami, najwyżej
  4 zapytania w locie). Reranker działa na `127.0.0.1:18092`, a nasz harness v3 na `:18043`. Opis trafił do
  wejścia wszystkich 23 zadań z obrazami. Nie został żaden znacznik.
- Najwolniejsze zadania: wypracowanie 26 (65,7 s), 13.1 (46,0 s), 2.2 (41,6 s) i 18 (40,9 s). Czasy są niższe
  niż w przebiegach `-noimg` i `-ocr` (śr. ok. 73–75 s), bo serwer był dziś mniej obciążony. Tych liczb nie należy
  porównywać wprost.
- Wobec `bielik45-harness-v3-ocr` zmieniło się 30 z 37 odpowiedzi, a wobec `-noimg` 29 z 37. Duża część tej
  różnicy to szum współdzielonego serwera (zob. niżej). Ile dają same opisy, pokaże dopiero ocena organizatorów.
- **Do wysłania jako prognoza finału:** `bielik45-harness-v3-vlm-qwen35-9b-q5km`. Punkt odniesienia:
  `bielik45-harness-v3-noimg`, czyli ten sam system bez opisów.

### Procedura finałowa na jednej maszynie: `scripts/run_final.sh`

```bash
scripts/run_final.sh /ścieżka/do/paczki [OUT_DIR]   # paczka: exam.json + answers-template.json + images/
```

Skrypt po kolei:

1. uruchamia serwer wizyjny,
2. opisuje wszystkie obrazy do `OUT_DIR/image_vlm.json`,
3. zatrzymuje serwer wizyjny, żeby zwolnić VRAM,
4. uruchamia reranker, Bielika (`-np 1` dla determinizmu) i harness v3 z flagami jak wyżej,
5. puszcza `exam_runner --image-desc`,
6. waliduje wynik i wypisuje ścieżkę `answers.json`.

Każdy `llama-server` ma `--cache-ram 0`. Domyślny `OUT_DIR` to `submissions/final/<nazwa paczki>`.
Ścieżki modeli i porty można nadpisać zmiennymi środowiskowymi (lista jest w nagłówku skryptu). Domyślne ścieżki
odpowiadają układowi katalogów na L40S. Skrypt zatrzymuje tylko procesy, które sam uruchomił. Ponowne
uruchomienie z tym samym `OUT_DIR` wznawia pracę od miejsca przerwania.

Skrypt w całości nie był jeszcze uruchomiony. Na mocku osobno przeszły jego etapy: opisy (ewaluacja modeli
wizyjnych) i odpowiadanie z opisami (tabela wyżej).

## Warunki finału: bez opisów obrazów (`-noimg`) i z offline OCR (`-ocr`) — 26.09 wieczorem (historia; OCR porzucony)

Paczka organizatorów daje przy każdym zadaniu tylko `question`, `source_text` i pliki PNG. Opisów obrazów
w niej nie ma („Labels within maps and diagrams remain part of their image”). Wszystkie starsze pliki
(tabela „Stan” niżej) dostawały `--image-desc data_cke/mock2023/image_desc.json`: opisy ilustracji z arkusza
CKE 660 (wersja dla niewidomych), które sami dopasowaliśmy do obrazów. Tych opisów nie ma w paczce i nie
będzie ich na finale. Wygenerować ich w trakcie testu też nie możemy, bo zamknięte API są wtedy zakazane.
Dlatego starsze wyniki są zawyżone i nie nadają się do kalibracji.

Nowe pliki odpowiadają warunkom finału:

- `-noimg`: bez `--image-desc`. W wejściu modelu zostają znaczniki `[Obraz: images/X.png]` z podpisem źródła.
  To dolna granica.
- `-ocr`: `--image-desc data_cke/mock2023/image_ocr.json`, czyli tekst z obrazów odczytany offline przez
  `scripts/ocr_images.py`. To klasyczny silnik OCR, a nie LLM, więc jest takim samym narzędziem pomocniczym
  jak embedder czy reranker. Do modelu trafia jako `[Opis obrazu: Tekst widoczny na obrazie (OCR): …]`.

| katalog | konfiguracja | walidacja | czas / zadanie: śr. · med. · maks. | suma | wypracowanie (id 26) |
|---|---|---|---|---|---|
| `bielik45-base-raw-noimg` | baza, `--mode raw`, T=0, bez opisów obrazów | VALID, 37/37, 0 błędów | 25,1 · 26,5 · 140,1 s | 929 s | 361 wyrazów |
| `bielik45-base-raw-ocr` | baza, `--mode raw`, T=0, OCR | VALID, 37/37, 0 błędów; ostrzeżenie: wypracowanie < 300 wyrazów | 29,8 · 24,7 · 118,1 s | 1103 s | 297 wyrazów (walidator liczy 272) |
| `bielik45-harness-v3-noimg` | harness v3 (`CKE_MODE=1 QTYPE_V2=1 RERANK=1`, `DENSE=0`, LoRA niezaładowana), bez opisów obrazów | VALID, 37/37, 0 błędów | 75,0 · 71,8 · 219,3 s | 2776 s | 686 wyrazów |
| `bielik45-harness-v3-ocr` | jak wyżej + OCR | VALID, 37/37, 0 błędów | 72,8 · 68,1 · 219,5 s | 2692 s | 730 wyrazów |

- Model: ten sam plik Bielik-4.5B-v3 Q8_0, serwer bez LoRA na L40S (`127.0.0.1:18093`, `-np 16`, współdzielony
  z próbkowaniem RFT). Reranker: `127.0.0.1:18092`. Runner miał najwyżej 4 zapytania w locie. Skrypt:
  `scripts/l40s_run_mock_ocr.sh` (`up` / `chain` / `down`). Flagi są te same co w `bielik45-base-raw`
  i `bielik45-harness-v3`. Czasy są wyższe niż wcześniej, bo serwer obsługiwał równolegle RFT.
- Szum między przebiegami jest duży. Zadania bez obrazów mają identyczne wejście, a mimo to w 8 z 14 takich zadań
  `bielik45-base-raw-noimg` i `bielik45-base-raw-ocr` dały inną odpowiedź, a w harnessie v3 (`-noimg` vs `-ocr`)
  w 11 z 14. OCR trafił do wejścia 14 z 23 zadań z obrazami; w pozostałych 9 został znacznik. Przy obciążonym serwerze z wieloma
  slotami wynik przy T=0 nie jest deterministyczny. Przykład: wypracowanie (id 26, bez obrazów) w `bielik45-base-raw-ocr`
  jest na inny temat niż w `bielik45-base-raw-noimg`. Różnicę `-ocr` minus `-noimg` najlepiej liczyć tylko na zadaniach z obrazami:
  1, 3, 4.x, 5.x, 7, 8, 9.x, 13.x, 14.x, 15, 17–21, 24.

**Do wysłania organizatorom (uczciwa kalibracja; stan sprzed decyzji o modelu wizyjnym, aktualna lista jest w sekcji „System finałowy”):**

1. `bielik45-harness-v3-ocr`: harness v3 + OCR. Do 26.09 ok. 17:00 była to planowana konfiguracja finału, ale OCR odpadł.
2. `bielik45-harness-v3-noimg`: ten sam system bez OCR. Różnica 1 − 2 pokazuje, ile daje OCR.
3. `bielik45-base-raw-noimg`: czysta baza w warunkach finału, punkt odniesienia dla przyrostu (tuned − base).
4. Opcjonalnie `bielik45-base-raw-ocr`.

Starszych `bielik45-base-raw` i `bielik45-harness-v3` (z opisami CKE 660) nie traktujemy jako prognozy wyniku
na finale.

### OCR (`scripts/ocr_images.py`)

- Silnik: **Tesseract 4.1.1** (leptonica 1.82.0), model polski `pol` z pakietu Ubuntu 22.04
  `tesseract-ocr-pol` (1:4.00~git30-7274cfa-1.1). Plik modelu:
  `/usr/share/tesseract-ocr/4.00/tessdata/pol.traineddata` (sha256 `c4476cdbc0e3…`). Pillow 12.3.0 w osobnym
  venv `/scratch/ocr/venv`. Na L40S zainstalowane przez `apt-get install tesseract-ocr tesseract-ocr-pol`.
  Działa bez sieci: to jeden plik binarny i plik `.traineddata`.
- Pakowanie na finał: `tesseract` + `pol.traineddata` (4,8 MB) + Pillow. Inną ścieżkę podaje się przez
  `--tesseract` i `--tessdata`. Bez Pillow skrypt robi tylko jeden przebieg bez powiększenia, co daje słabszy
  odczyt drobnych napisów na mapach.
- Przebiegi na każdy obraz: psm 3 (układ strony, x2) dla bloków tekstu i podpisów. Potem psm 11 (rozproszony
  tekst) w powiększeniu x2, x3 i x4, a na koniec psm 11 po obrocie o 90° i 270° dla pionowych napisów. Napis
  zostaje, gdy jeden przebieg odczytał go z pewnością ≥ 88 albo zgodziły się co najmniej dwa. Śmieci
  (kreskowanie odczytane jako litery, tokeny bez liter i cyfr, linie < 3 znaków) są odrzucane. Limit to
  800 znaków na obraz.
- Jeśli `source_text` zawiera już „Transkrypcję” tekstu z obrazu, a ≥ 50% słów z OCR jest w tym tekście, obraz
  dostaje `""` i zostaje znacznik. Tak jest z Z20-S2, Z21 i Z24-S1.
- Cache: surowe słowa każdego przebiegu, klucz to sha256 obrazu (`image_ocr.cache.json`). Metadane silnika
  są w `image_ocr.meta.json`. Mock (19 obrazów, 152 przebiegi) trwał ok. 200 s na obciążonym CPU L40S.
- Wynik na mocku: tekst dla 9 z 19 obrazów. Dobrze wychodzą tablice genealogiczne (Z05-S2, Z09-S2, prawie
  bezbłędnie), mapy z napisami (Z03-S2, Z04-S2, Z13-A/B, Z19-S2; nazwy miejscowości, ulic i dowódców, część
  urwana) i karykatury z podpisami (Z18, Z24-S2). Pusto jest dla zdjęć i obrazów bez tekstu (Z01, Z05-S1, Z07,
  Z08, Z14, Z15, Z17-S2). Tam pomógłby tylko opis treści wizualnej, a tego OCR nie da.

## Stan (26.09, ok. 15:30) — 5 gotowych plików, wszystkie `VALID`

Uwaga: wszystkie pliki z tej tabeli dostawały opisy obrazów z arkusza CKE 660, których na finale nie będzie (zob. wyżej).

Przebieg na L40S (kopia `/scratch/mock/wmt-matura`, skrypt `scripts/l40s_run_mock.sh`), GPU współdzielone
z treningiem LoRA i próbkowaniem RFT, więc czasy są zawyżone względem samodzielnej maszyny. Oceny organizatorów:
jeszcze brak (pliki nie zostały wysłane).

| katalog | model | konfiguracja | walidacja | czas / zadanie: śr. · med. · maks. | suma | wypracowanie (id 26) |
|---|---|---|---|---|---|---|
| `bielik45-base-raw` | Bielik-4.5B-v3 Q8_0 (baza, bez LoRA) | `--mode raw`: jedna wiadomość `user`, bez promptu systemowego, T=0 | VALID, 37/37, 0 ostrzeżeń | 10,9 · 10,8 · 37,8 s | 403 s | 361 wyrazów |
| `bielik45-harness-v3` | Bielik-4.5B-v3 Q8_0 (LoRA niezaładowana) | harness v3: `CKE_MODE=1 QTYPE_V2=1 RERANK=1` (bge-reranker-v2-m3), `DENSE=0` | VALID, 37/37, 0 ostrzeżeń | 56,7 · 24,8 · 214,8 s | 2096 s | 670 wyrazów |
| `qwen08-base-raw` | Qwen3.5-0.8B Q8_0 (baza) | `--mode raw`, thinking wyłączony (`enable_thinking=false`) | VALID, 37/37, 0 ostrzeżeń | 11,3 · 7,0 · 98,4 s | 419 s | 1043 wyrazy, ale zapętlone (4% unikalnych słów) |
| `qwen08-harness-v2-bm25` | Qwen3.5-0.8B Q8_0 | harness v2: `QTYPE_V2=1 RERANK=0 CKE_MODE=0 TOP_K=4`, thinking wyłączony | VALID, 37/37, 0 ostrzeżeń | 10,6 · 8,0 · 48,1 s | 390 s | 450 wyrazów |
| `qwen08-harness-v3-bm25` | Qwen3.5-0.8B Q8_0 | harness v3 bez rerankera: `CKE_MODE=1 QTYPE_V2=1 RERANK=0 TOP_K=4`, thinking wyłączony | VALID, 37/37, 0 ostrzeżeń | 13,5 · 12,1 · 49,0 s | 498 s | 627 wyrazów |

- Zgłoszenie „progress”: `bielik45-harness-v3` (na pełnych arkuszach v3 dało 54,1% wobec 38,8% surowej bazy).
  Zgłoszenie „Mały, ale wariat”: jeden z plików `qwen08-harness-*`; wybór po ocenie organizatorów.
- Harness dla Qwen działa z flagami dostrojonymi pod 0.8B (tylko zmienne środowiskowe): `CTX_TOKENS=1200`,
  `ESSAY_CTX_TOKENS=2500`, `ESSAY_TOP_K=6`, `ESSAY_MAX_TOKENS=1400`, `ESSAY_TEMPERATURE=0.6`,
  `ESSAY_DRY_MULTIPLIER=1.0`, `ESSAY_DRY_ALLOWED=3`, `CKE_SOURCE_TOP_K=3`, `CKE_ESSAY_PART_CTX_TOKENS=1200`,
  `CKE_ESSAY_PART_TOP_K=4`.
- `qwen08-harness-v3-bm25`: 4 zadania (1, 2.1, 2.2, 4.2) pochodzą z pierwszego przebiegu. Potem llama-server Qwena
  padł (OOM kontenera, bo domyślny `--cache-ram` llama-servera to 8 GiB RAM), a pozostałe 33 zadania runner
  dokończył po restarcie z `--cache-ram 0`. Konfiguracja w obu przebiegach była identyczna.
- Czas na zadanie jest w `debug.jsonl` (pole `latency`, liczone od wysłania zapytania do odpowiedzi).

## Jak powstały

Runner: `harness/exam_runner.py` (nowy plik, tylko stdlib). Dla każdego zadania:

1. wejście modelu = `source_text` + `question` (ta sama kolejność co w naszych dev-setach CKE) + instrukcja formatu
   zbudowana z `answer_format` (neutralny wzór składni, np. `1: P albo F`, bez przykładowych wartości, które model
   mógłby przepisać);
2. obrazy: `[Obraz: images/X.png]` zastępowane przez `[Opis obrazu: …]` z `data_cke/mock2023/image_desc.json`
   (oficjalne opisy CKE z arkusza 660 dla maja 2023, dopasowane po numerze zadania; dla obrazów bez opisu — tylko
   podpis źródła). Obrazy z listy `images`, do których `source_text` nie ma odnośnika (zad. 7, 8, 15), są dopisywane
   na końcu źródła;
3. wywołanie modelu: `--mode raw` = czysty llama-server, jedna wiadomość `user`, bez promptu systemowego,
   temperatura 0; `--mode harness` = `POST /answer` naszego harnessu (instrukcja formatu jako `system` tylko dla
   zadań otwartych — zamknięte mają gramatykę GBNF);
4. deterministyczny post-format do `answer_format`: `P, F, P` → `1: P\n2: F\n3: P`, `1-B, 2-C` → `1: B\n2: C`,
   `A-3, B-1` → `A: 3\nB: 1`, `Odpowiedź: C. …` → `C`; usuwanie toku rozumowania (`<think>`, markdown, tekst przed
   ostatnim „Odpowiedź:” w zadaniach zamkniętych); etykiety z arkusza (`Rozstrzygnięcie:`, `Uzasadnienie:`,
   `Nazwa stylu 1.:`, `Cecha:` …) zawsze w osobnych wierszach (gdy model ich nie napisał, a są dokładnie dwie —
   pierwsze zdanie trafia pod pierwszą etykietę, reszta pod drugą); wypracowanie (id `26`) dostaje numer tematu,
   jeśli model go nie podał (temat o największym pokryciu słów);
5. walidacja względem `answers-template.json` (wszystkie 37 id dokładnie raz, same stringi, tylko `exam_id` +
   `answers`, ≤ 100 000 znaków na odpowiedź, ≤ 1 MiB, brak `TEAM_KEY`/wartości z `.env`) + ostrzeżenia o składni
   odpowiedzi zamkniętych, pustych odpowiedziach i wypracowaniu < 300 wyrazów.

Uruchomienie (Mac, kopia `~/wmt-matura-exam`, porty 18050–18057, skrypt `run_exam_mock.sh`):

```bash
python -m harness.exam_runner data_cke/mock2023/exam.json --image-desc data_cke/mock2023/image_desc.json \
    --mode raw --llm-url http://127.0.0.1:18050 --model bielik-4.5b-v3 --out submissions/mock/bielik45-base-raw/answers.json
python -m harness.exam_runner data_cke/mock2023/exam.json --image-desc data_cke/mock2023/image_desc.json \
    --mode harness --url http://127.0.0.1:18053 --lora-llm-url http://127.0.0.1:18051 --lora-off-types explain,essay \
    --out submissions/mock/bielik45-lora-harness-v2/answers.json
# sprawdzenie gotowego pliku
python -m harness.exam_runner --validate submissions/mock/<system>/answers.json --exam data_cke/mock2023/exam.json
# po zmianie post-formatu: przebudowa answers.json z debug.jsonl bez ponownego pytania modelu
python -m harness.exam_runner data_cke/mock2023/exam.json --out submissions/mock/<system>/answers.json --reformat-only
```

Runner jest wznawialny (pomija id, które mają w `debug.jsonl` niepustą odpowiedź bez błędu), współbieżność 4,
timeout 1800 s na zadanie, 1 ponowienie.

## Jak wysłać

1. Link do strony zgłoszeń podają organizatorzy (nie wpisujemy go do repo, nie wywołujemy ich backendu skryptem).
2. Na stronie: wpisz `TEAM_KEY` (jest w `.env` w katalogu repo — nie wklejaj go do czatu, commitów ani do JSON-a),
   nazwę rozwiązania (np. nazwę katalogu: `bielik45-lora-harness-v2`), wybierz **Mock exam**, wgraj `answers.json`.
3. Zachowaj potwierdzenie. Udany upload = przyjęte, nie ocenione; ocena LLM wg klucza CKE co ok. 30 min.
4. Przed wysłaniem zawsze: `python -m harness.exam_runner --validate … --exam …` → `VALID`.
