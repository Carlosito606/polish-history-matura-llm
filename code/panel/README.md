# Panel webowy WMT (drużyna Vibers)

Jednoplikowy panel FastAPI (`panel/app.py`, HTML renderowany na serwerze, inline
CSS/JS i wykresy SVG, bez zewnętrznych CDN), serwowany z Maca (`baza`) pod adresem
Tailscale.

**URL:** http://<tailscale-host>:18090/

Panel tylko czyta dane, z jednym wyjątkiem: zakładka „Sprawdź pytanie”
proxuje pytanie do lokalnego harnessu / llama-server. Żaden endpoint nie wykonuje
poleceń powłoki zbudowanych z danych od użytkownika. Cała treść z plików i logów
jest escapowana (`html.escape`). `TEAM_KEY` z `.env` nigdy nie jest czytany ani
wyświetlany. Pliki wskazywane parametrami URL są whitelistowane:
`/run`, `/porownaj`, `/api/run` przyjmują tylko `*.jsonl` spod `devset/runs/`
(oraz `results/`, `devset/results/`). `/api/logs` przyjmuje tylko nazwy z listy
`logs/*.log`, `/api/sample` tylko nazwy z `devset/*.jsonl`, a `/sweep` tylko
`devset/sweep_results*.md`.

## Skąd są liczby

- Źródło: `devset/experiments.csv` (jeden wiersz = jeden przebieg `devset/eval.py`)
  i pliki per pytanie `devset/runs/*.jsonl` (kolumna `run_file`). Format danych
  się nie zmienia; panel tylko je czyta, a inne agenty mogą dalej dopisywać.
- Etykiety są rozbijane na `[seria-]model-wariant`, np.
  `final-bielik-4.5b-v3-harness-v2-lora` → seria `final`, model `bielik-4.5b-v3`,
  wariant `harness-v2-lora`. Serie: `final-`, `l40s-`, `mac-`, `t-`, `integ-devall-`.
  Wariant zaczyna się od `base` albo `harness`. Etykiety spoza konwencji
  (`hv2-*`, `kb-*`, `devac-*`) to eksperymenty; ich model pochodzi z
  `config.llm_model`. Nazwa modelu jest mapowana na katalog w `models/`
  (np. `bielik-1.5b` → `bielik-1.5b-v3`).
- **System** = etykieta na danym zakresie. Zakres to jeden plik (np. `tourney160`)
  albo **pełny benchmark** = suma 9 plików: dev-a, dev-b, dev-c, dev-f, dev-g,
  dev-h, tourney160, cke-2023, cke-more (673 pytania). Wynik pełny liczony jest z
  liczby poprawnych odpowiedzi ważonej `n`, więc jest zgodny z raportem zespołu
  (np. bielik-4.5b-v3 + harness v2 + LoRA: 75,5% ścisła, goły model 2,8%, przyrost
  +72,7 pkt). Do rankingu pełnego wchodzą tylko systemy z kompletem 9 plików.
  Do każdej pary (etykieta, plik) bierzemy najnowszy wiersz.
- **T** = najlepszy system z harnessem (endpoint `answer`) dla modelu. **B** =
  nietknięty model bazowy, wariant `base-raw` (endpoint `base`), tego samego
  modelu na tym samym zakresie, najlepiej z tej samej serii. **Przyrost = T − B**
  w punktach procentowych.
- Przełącznik **Ocena: ścisła / łagodna** w nagłówku działa na wszystkich
  stronach (`?m=strict|lenient`). Per typ pytania `eval.py` zapisuje tylko
  trafność *extract*, więc filtry i wykresy per typ pokazują extract (z opisem).

## Zakładki

1. **Przegląd** – trzy karty kategorii nagród (największy przyrost, najlepszy
   wynik, „Mały, ale wariat”), wykresy przyrostu T−B (pełny benchmark i
   tourney160), ostatnie przebiegi i stan danych, w tym ostrzeżenie, gdy
   brakuje plików per pytanie dla przebiegów `final-*`.
2. **Przyrost** – per model: B, najlepszy T, przyrost ścisły i łagodny, wykres
   B→T, link do porównania pytań. Dodatkowo tabela „Warianty systemu”: goły
   model → harness v1 bez/z KB → harness v2 → LoRA dla każdego modelu.
3. **Najlepszy wynik** – ranking systemów T z filtrami zestawu (pełny, każdy plik)
   i typu pytań; systemy z niepełnym pokryciem są osobno. Na dole macierz
   system × zestaw, gdzie każda komórka prowadzi do pytań danego przebiegu.
4. **Mały, ale wariat** – modele od najmniejszego GGUF, najlepszy wynik z
   progiem 35% (wykres i tabela), zwycięzca, zapas nad progiem i najbliższy
   mniejszy kandydat. Rozmiar to największy `*.gguf` w `models/<model>/`
   (bajty/1e9); reranker (ok. 0,64 GB) nie jest doliczany, patrz notka na stronie.
5. **Modele** → `/model/<nazwa>` – dla każdego modelu: plik GGUF i rozmiar,
   najlepszy benchmark (pełny, jeśli jest, inaczej tourney160), B, przyrost,
   wszystkie jego systemy na wykresie, macierz per zestaw, typy pytań T vs B,
   linki do porównań B/T per zestaw i lista wszystkich przebiegów.
6. **Przebiegi** – wszystkie wiersze `experiments.csv` w zwartej tabeli z filtrami
   (zestaw, model, B/T, czy jest plik per pytanie) i pobieraniem surowego CSV.
   - `/run?file=…` – jeden przebieg: kafle wyników, rozbicie per typ i epokę,
     wszystkie pytania z wzorcem, odpowiedzią modelu, surowym wyjściem, ✓/✗ i
     tytułami kontekstu KB. Filtry: tylko błędne/poprawne, typ, epoka, szukaj.
   - `/porownaj?b=…&t=…` – goły model vs nasz system na tych samych pytaniach:
     naprawione, zepsute, bez zmian, bilans (= przyrost), per typ.
7. **Sweepy** – `devset/sweep_results*.md` jako sortowalne tabele.
8. **Zestaw testowy** – podsumowanie plików `devset/*.jsonl` (liczba pytań per
   typ, przynależność do pełnego benchmarku) i rozwijane listy pytań.
9. **Sprawdź pytanie** – wybór instancji harnessu (probe `GET /health`,
   porty 18000–18010), losowanie pytania z wybranego zestawu (z odpowiedzią
   wzorcową) i porównanie obok siebie: `/answer` (RAG) oraz
   `/base/v1/chat/completions` z **temperature=0, max_tokens=512**, dokładnie jak
   w benchmarku bazowym (`harness/batch.py`), więc odpowiedzi nie są losowe.
   Fallback: llama-server na :18080. Limit 120 s na każde źródło.
10. **System** – procesy własnego użytkownika, pamięć, dysk, load, pliki GGUF z
    sha256 (w tle, cache `logs/sha256_cache.json`), baza wiedzy, logi. Te sekcje
    odświeżają się same co 15 s i zachowują sortowanie.
11. **Pełna matura** – zobacz sekcję niżej.

Strony z wynikami nie przeładowują się same, żeby nie gubić filtrów. Co 20 s
panel sprawdza `/api/version` (mtime/rozmiar `experiments.csv` i `devset/runs/`).
Gdy pojawią się nowe dane, pokazuje baner „Są nowe wyniki – odśwież stronę”.

API: `/api/run?file=`, `/api/version`, `/api/experiments.csv`, `/api/sample?file=`,
`/api/harness_instances`, `/api/ask` (POST), `/api/logs?name=`, `/api/refresh`, `/health`,
`/api/matura/summary`, `/api/matura/grades?paper=`.

## Pełna matura

Zakładka **Pełna matura** (`/matura`, `/matura/<paper>`) pokazuje cały przebieg
egzaminu naszego systemu Bielik-4.5B na kompletnych arkuszach maturalnych CKE,
zadanie po zadaniu, z oceną egzaminatora wg oficjalnej punktacji CKE.

- **Dane** – wyłącznie `devset/cke_full/*.jsonl`, nigdy commitowane (materiał CKE
  jest chroniony prawem autorskim, patrz `CLAUDE.md`). Na Maca trafiają
  skryptem `scripts/sync_cke_full_to_mac.sh` z laptopa (tar-over-ssh,
  idempotentny). Cztery arkusze: `mentor2023` (benchmark tekstowy, obrazy
  opisane słownie), `cke2024`, `cke2025`, `cke2026`. Trzy warianty systemu:
  `raw` (goły model, endpoint bazowy), `harness_nolora`, `harness_lora`
  (`answers_<system>_<paper>.jsonl`). `grades.jsonl` (system, paper, id, points,
  max, category, reason) dopisuje osobny proces oceniający w tle — dopóki
  oceny dla danej pary (system, zadanie) nie ma, panel pokazuje samą odpowiedź
  modelu i znaczek „ocena w toku”; nic się nie wywraca, gdy pliku jeszcze nie ma.
- **Klasyfikacja pytań** – zamknięte (`abcd`, `abcd_parts`, `pf`, `match`,
  `chrono`) / otwarte (`open`, `explain`, `generic`, ...) / wypracowanie
  (`essay`), na podstawie `type_hint` z pliku arkusza (funkcja
  `matura_classify` w `app.py`), niezależnie od tego, co akurat zapisał
  proces oceniający w `category`.
- **/matura** – tabela systemy × arkusze: punkty/max i % w rozbiciu na
  zamknięte/otwarte/wypracowanie plus przyrost (pkt proc.) każdego wariantu
  systemu względem gołego Bielika, liczony na sumie punktów ze wszystkich
  czterech arkuszy (tylko zadania już ocenione).
- **/matura/<paper>** – zadania w kolejności numerycznej (1, 2.1, 2.2, …,
  wypracowanie jako ostatni numer arkusza): nr, typ, punkty (kolor: pełne/
  częściowe/zero/ocena w toku), odpowiedź modelu, uzasadnienie egzaminatora;
  treść zadania i kryteria CKE w rozwijanym `<details>`. Przełącznik systemu
  (`?sys=`) albo tryb **side-by-side** (`?mode=compare&a=…&b=…`) porównujący
  dwa wybrane warianty przy tym samym zadaniu. Wypracowanie ma własny blok:
  pełny tekst, liczba słów (`essay_meta.words` z harnessu, inaczej liczone z
  tekstu), punkty za narrację historyczną (0–12) i kompozycję (0–3) wyparsowane
  z `reason` (wzorzec „... => A<n>; B<n>”, sprawdzony na wszystkich ocenionych
  wypracowaniach), lista wykrytych błędów merytorycznych (najlepszy wysiłek —
  pełne uzasadnienie jest i tak zawsze pokazane obok).
- **Odświeżanie bez zwijania `<details>`** – `/matura` wymienia całą
  zawartość `#matura-summary-body` co 15 s (tak jak sekcje System/Modele/Baza
  wiedzy), bo tam nie ma żadnych `<details>`. `/matura/<paper>` robi to
  punktowo: co 15 s podmienia tylko znaczek punktów (`#mg-<system>-<id>`) i
  uzasadnienie (`#mr-<system>-<id>`) przez mały endpoint JSON
  (`/api/matura/grades?paper=`) — `<details>` z treścią zadania nigdy nie jest
  dotykany, więc rozwinięte zostaje rozwinięte, nawet gdy w tle dojeżdża ocena.

## Uruchamianie / restart

Na Macu (`ssh baza`), z katalogu `~/wmt-matura`:

```bash
panel/run.sh start     # idempotentne - jeśli już działa, nic nie robi
panel/run.sh stop
panel/run.sh restart
panel/run.sh status
```

Skrypt używa `nohup` (bez launchd/cron/login items), trzyma PID w
`logs/panel.pid` i loguje do `logs/panel.log`. Binduje **wyłącznie** do
`<tailscale-host>:18090` (adres Tailscale Maca), nigdy do `0.0.0.0` ani
`127.0.0.1`, bo Mac jest dzielony z innymi osobami.

Test na lokalnej kopii danych (bez Maca): `WMT_PANEL_BASE_DIR=/ścieżka/do/kopii`
(katalog z `devset/`, `models/`, `logs/`) i `uvicorn panel.app:app --host 127.0.0.1`.

## Ograniczenia

- Pliki per pytanie przebiegów `final-*` (pełny benchmark, najlepsze systemy)
  powstały na innej maszynie i w chwili zmiany (26.09, ok. 12:00) nie ma ich w
  `devset/runs/` na Macu. Procenty są widoczne, ale podgląd pytań i porównania
  B/T dla tych przebiegów pokazują „brak pliku”. Wystarczy skopiować pliki z
  `run_file` do `devset/runs/`, a panel podchwyci je sam.
- Przebiegi spoza konwencji etykiet są widoczne w „Przebiegach” i na stronie
  modelu (jako eksperyment), ale nie trafiają do rankingów kategorii.
- Probe instancji harnessu widzi tylko `127.0.0.1:18000–18010` na Macu.
