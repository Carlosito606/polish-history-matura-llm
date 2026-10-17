# Mapa błędów harnessu v2: Bielik-4.5B + LoRA

Dla: lead (Vibers WMT). Od: sesja panelu. Stan danych: 26.09, ok. 14:30.

## Co i jak sprawdziłem

- **System:** `final-bielik-4.5b-v3-harness-v2-lora`, czyli Bielik-4.5B Q8_0 + LoRA `final-bielik-4.5b-v3-r16-e2` + harness v2.
- **Dane:** pliki per pytanie z `devset/runs/`, 9 plików pełnego benchmarku. Dla porównania użyłem tego samego systemu bez LoRA (`final-bielik-4.5b-v3-harness-v2`) i `final-qwen3-8b-harness-v2-lora`.
- **Rozmiar próbki:** 673 wiersze, ale to tylko **513 unikalnych pytań**, bo tourney160 w całości dubluje inne pliki. Poprawnych jest **387/513 (75,4%)**, błędnych **126**: open 35, chrono 32, pf 31, match 15, abcd 13.
- **Metoda:** dla każdej klasy błędów stawiałem hipotezę i testowałem ją na zapisanych odpowiedziach (`raw`, `ctx`, `meta`). Logikę harnessu odtwarzałem offline. Trzy subagenty ręcznie zweryfikowały prawdziwe daty, fakty i klucz odpowiedzi.
- **Czego nie zrobiłem:** testów na żywym modelu. Mac był przeciążony (load average do 165, SSH gubił połączenia), więc nie dokładałem obciążenia. Takie hipotezy mają status **DO TESTU**, a przy każdej jest przepis na test.
- **Statusy:** **POTWIERDZONA** = dane to pokazują; **OBALONA** = sprawdzone i nieprawdziwe; **DO TESTU** = wymaga uruchomienia modelu.

## Priorytety

| # | Obszar | Błędy (z 126) | Przyczyna | Zmiana | Szacowany zysk |
|---|---|---|---|---|---|
| 1 | Chronologia | 32 | 20 zły rok u modelu, 10 remis lat w obrębie jednego roku, 1 brak „p.n.e.” | daty RRRR-MM(-DD) tylko dla remisów, „ p.n.e.” w gramatyce, pytanie parowe przy konflikcie | +5–7 pytań (optymistycznie +11) |
| 2 | Wyszukiwanie | 19 z brakiem artykułu źródłowego | pobiera artykuł o podobnym tytule, gubi „I”/„III” w tytułach | premia za dokładny tytuł z pytania, sprawdzić stopword „i” | do +19, głównie abcd, open, match |
| 3 | LoRA a „rozstrzygnij/wyjaśnij” | 13 (explain) | LoRA odpowiada prawie zawsze „Nie” i bez uzasadnienia | explain bez LoRA | +2–3; ważniejsze na egzaminie, jeśli ocenia uzasadnienie |
| 4 | Prawda/fałsz | 31 | Wiki: jedno źle ocenione zdanie; CKE: zła identyfikacja źródła | druga tura „F tylko z dowodem”, split dla podejrzanych | do testu |
| 5 | Dopasowanie | 15 | zamiana dwóch podobnych par, kopiowanie przykładu formatu, `abcd_parts` | neutralny przykład formatu, `abcd_parts` jako osobne abcd | +2–3 |
| 6 | ABCD | 13 | brak artykułu źródłowego, przynęta najbardziej znana; dev-h ma same A | wyszukiwanie (punkt 2), przetasować opcje w dev-h | patrz punkt 2 |
| 7 | Pomiar | – | duplikaty, niedeterminizm 4%, błąd w ocenie łagodnej, luki w listach accept | poprawki w `eval.py` i zestawach | +1,2–1,8 pkt w samym pomiarze |

## 1. Chronologia: 32 błędy (62 unikalne pytania, 30 poprawnych)

**Hipoteza „błąd w sortowaniu harnessu”: OBALONA.** Odtworzyłem tryb hybrid offline (sortowanie po roku, remis rozstrzyga `raw[1]`). Wynik zgadza się z `pred` w 62/62 pytaniach.

**Hipoteza „z LoRA lepsza jest sama kolejność bezpośrednia”: OBALONA.** Na unikalnych pytaniach hybrid daje 30/62, sama kolejność bezpośrednia 29/62. Wyrocznia wybierająca lepszą z dwóch dałaby 36/62.

**Hipoteza „remisy lat”: POTWIERDZONA, ale to druga przyczyna, nie pierwsza.**
- W 31/62 pytaniach model daje ten sam rok dwóm lub więcej wydarzeniom. Trafność z remisem wynosi 35%, bez remisu 61%.
- Pytania o wydarzenia z jednego roku (Wiosna Ludów 1848, Korzec VI 1920, krater 1864, Leros 1943, 238 r.): 1/5 poprawnych.

**Klasyfikacja 32 błędów** (daty sprawdzone ręcznie):

| Klasa | Liczba | Pytania |
|---|---|---|
| Y: model podał zły rok | 20 | a-012, a-013, a-049, b-028, b-038, b-040, b-051, b-070, c-005, c-032, c-042, c-064, c-071, f-006, f-014, f-018, f-045, g-033, g-047, h-045 |
| T: lata dobre, remis w tym samym roku | 10 | b-053, c-010, c-053, f-012, f-033, f-039, g-004, g-006, g-009, h-042 |
| S: brak „p.n.e.” | 1 | a-009 (znak brakuje też w a-012 i g-047, ale tam są również złe lata) |
| G: wzorzec wątpliwy | 1 | h-040 („zwycięska bitwa pod Chocimiem”: 1621 albo 1673) |

**Korekta mojej wcześniejszej wiadomości o p.n.e.:**
- `dev-a-013` to czasy Konstantyna, czyli n.e. Błąd polega tam na złym roku.
- Model czasem pisze minus (dev-g-047: „-88”, „-114”), ale niekonsekwentnie.
- Czysty błąd znaku jest jeden: `dev-a-009` (lata 219/216/212/207 bez minusa, w efekcie odwrócona kolejność).

**Proponowana zmiana (DO TESTU):**
1. **Etap 1 bez zmian,** poza tym, że gramatyka dopuszcza `" p.n.e."` po roku, a prompt mówi „dla dat przed naszą erą dopisz ‘ p.n.e.’”. `parse_years` już to rozumie. Awaryjnie: jeśli w pytaniu lub w kontekście stoi „216 p.n.e.”, a model podał „216”, traktuj rok jako ujemny.
2. **Etap 2 tylko dla grup z tym samym rokiem:** „Wydarzenia A i C miały miejsce w 1767 r. Podaj ‘A: MM-DD’, ‘A: MM’ albo ‘A: ?’.” Pytania bez remisu (61% poprawnych) zostają bez zmian, więc nie ma ryzyka regresji.
3. **Konflikt:** gdy sortowanie po latach i `raw[1]` różnią się dla jakiejś pary, rozstrzygnij ją pytaniem parowym „Co było wcześniej: A czy C?” z kontekstem.
4. **Szacunek:** realistycznie +5–7 pytań, bo model 4.5B nie zna wielu dat dziennych, chyba że są w kontekście. Optymistycznie +11.

**Test:** 80 wierszy chrono z 9 plików, po wprowadzeniu zmiany w `harness/prompts.py` (`instruction_chrono_years`, `grammar_years`) i `pipeline._chrono_years`. Porównaj z 41/80 obecnie.

## 2. Wyszukiwanie: artykuł źródłowy poza kontekstem

**Hipoteza „brak artykułu źródłowego to istotna przyczyna błędów”: POTWIERDZONA.**
- Pytań z Wikipedii jest 409, w każdym znamy `source_title`.
- Gdy artykuł źródłowy jest w kontekście (355 pytań): 81% poprawnych. Gdy go nie ma (54 pytania): 65%.
- 19 ze 126 błędów ma brak artykułu źródłowego.
- Najmocniej widać to w ABCD: błąd 20% bez źródła (5/25) wobec 1,7% ze źródłem (2/119). 5 z 7 błędów ABCD z Wikipedii to brak źródła.

**Wzorzec „artykuł-rodzeństwo”: POTWIERDZONY.** W 25 z 54 pytań bez źródła kontekst zawiera artykuł o bardzo podobnym tytule:
- dev-b-034: „II wojna trzydziestoletnia” zamiast „Wojna trzydziestoletnia”,
- dev-a-010: I i III wojna punicka zamiast II,
- dev-b-066, dev-h-011: „Rozbiory Polski” zamiast „III rozbiór Polski”,
- dev-h-042: konferencja kairska i teherańska zamiast poczdamskiej,
- dev-h-040 i dev-h-058: Chocim, Buczacz zamiast Wiednia.

**Liczebniki rzymskie w tytułach (poszlaka, DO SPRAWDZENIA w `kb/textnorm.py`):**
- Artykuły z „I …” albo „III …” w tytule trafiają do kontekstu w 4 z 10 przypadków, z „II …” w 4 z 5.
- Podejrzenie: „I” po zmianie na małe litery staje się stopwordem „i” i znika z zapytania.

**Proponowana zmiana (DO TESTU):**
- premia za dokładne dopasowanie nazwy z pytania do tytułu artykułu (np. „Bitwa o Monte Cassino”, „Henryk III Walezy”);
- zachowanie liczebników rzymskich jako tokenów;
- kara za tokeny w tytule, których nie ma w pytaniu („II” w „II wojna trzydziestoletnia”).

**Test:** recall `source_title` w top-5 po reranku, na 54 pytaniach z listy braków. Te same pytania zadaj harnessowi i porównaj trafność. Istniejące narzędzie: `python -m kb.eval_recall --index kb_data/index devset/dev-*.jsonl --misses`.

Pytania bez źródła, które są błędne: dev-a-010, a-018, a-036, b-027, b-034, b-035, b-066, c-064, f-048, g-024, h-006, h-009, h-011, h-040, h-042, h-045, h-056, h-058, h-068.

## 3. LoRA psuje zadania „rozstrzygnij / wyjaśnij” (qtype `explain`, 20 zadań CKE)

**Hipoteza „LoRA uczy krótkich odpowiedzi, co szkodzi zadaniom z uzasadnieniem”: POTWIERDZONA.**

| | z LoRA | bez LoRA |
|---|---|---|
| explain poprawne (strict) | 7/20 | 9/20 |
| decyzje Tak/Nie poprawne | 3/7 | 6/7 |
| ile razy model mówi „Nie” (7 zadań) | 6 | 3 |
| odpowiedzi z „Uzasadnienie:” | 1/20 | 10/20 |
| mediana długości odpowiedzi | 25 znaków | 883 znaki |

- **Zepsute przez LoRA:** cke23-16.1, cke23-17, cke23-4.2 (poprawne „Tak” zmienione na „Nie”).
- **Wniosek:** LoRA uczono samych krótkich kanonicznych odpowiedzi i to działa na abcd, pf, match i chrono. Zadania `explain` oczekują rozstrzygnięcia z uzasadnieniem. Na egzaminie, jeśli oceniane jest uzasadnienie, strata może być większa niż w naszym `eval.py`, który sprawdza tylko pierwszą linię.
- **Zmiana (DO TESTU):** dla `qtype == explain` generuj bez adaptera. Sprawdź, czy llama-server b11185 obsługuje `lora` w żądaniu ze skalą 0 (`GET /lora-adapters`). Jeśli nie, użyj osobnego serwera bez LoRA; model bazowy i tak działa osobno do benchmarku B.
- **Test:** 20 zadań explain z cke-2023 i cke-more, w obu wariantach.

Dla porównania całościowo: LoRA względem v2 bez LoRA naprawiła 98 wierszy, a zepsuła 21. Zepsute to chrono 8, open 6 (3 powyższe Tak/Nie i 3 zmiany formy: hidżra→hadżdżra, komandosi→komandosowie, Więzienie Mokotowskie→Mokotów), abcd 4, match 2 i pf 1.

## 4. Prawda/fałsz: 31 błędów (22 z Wikipedii, 9 CKE)

**Hipoteza „błąd parsowania zdań”: OBALONA.** Liczba stwierdzeń w odpowiedzi zgadza się ze wzorcem we wszystkich błędnych pytaniach.

**Pytania z Wikipedii:**
- Trafność na poziomie zdania to 91%. 17 z 22 błędnych pytań ma dokładnie jedno źle ocenione zdanie. Artykuł źródłowy był w kontekście we wszystkich pytaniach pf.
- **Kierunek błędów** (27 błędnych zdań): 19 razy prawdziwe zdanie oznaczone jako F, 8 razy fałszywe jako P.
- Wzorzec „prawdziwy konkret odrzucony” (liczba, data, miejsce), 9 przypadków: dev-c-038 (7-letnia kadencja), dev-h-028 (linia Gaeta–Ortona), dev-c-047 (Kazachstan IV 1940), dev-b-045 (koronacja w Reims).
- Wzorzec „fałsz z jednym zmienionym szczegółem przyjęty”, wszystkie 8 błędów F→P: Richelieu zamiast Mazarina (dev-b-045), „zburzyć” Azow zamiast oddać (dev-g-021), „ostatecznie” (dev-c-055), „bez żadnych zastrzeżeń” (dev-h-032), 14 zamiast 15 lutego (dev-h-028).
- Pomylenie podobnych wydarzeń: dev-h-029 (II rozbiór pomylony z I), dev-a-046 (bulla z 1136 pomylona z bullą z 1133), dev-h-033 (w kontekście „Bitwa nad Dźwiną” z 1701 zamiast Kircholmu 1605).
- Te same fakty są błędne w różnych typach pytań (Ortona w h-028 i h-006, Prusy Zachodnie w h-035 i h-023). To sugeruje, że wiedza zapisana w modelu wygrywa z kontekstem.

**Pytania CKE:**
- Trafność na poziomie zdania to 51%. W 4 zadaniach wszystkie zdania są odwrócone, bo model źle rozpoznał, czego dotyczy źródło.
- Wyszukiwarka pobiera artykuł o przynęcie z fałszywego zdania: cke2405-20.2 (Stalin zamiast NEP), cke23-19 i cke2305-19 („Konstytucja kwietniowa” zamiast marcowej), cke2505-10 (trzy razy Sobieski).

**Zmiany (DO TESTU):**
1. **„F tylko z dowodem”:** druga tura dla każdego F z prośbą o zacytowanie zdania z kontekstu, które przeczy stwierdzeniu. Brak cytatu oznacza P. Dla zdań z liczbą, datą, nazwą lub kwantyfikatorem („ostatecznie”, „wyłącznie”, „po raz pierwszy”) model wypisuje wartość z kontekstu i porównuje.
2. **`pf_mode=split` warunkowo:** gdy odpowiedź ma co najmniej 2 F albo same P. Nie narzucaj liczby F.
3. **CKE dwuetapowo:** najpierw sam tekst źródła („kto, co, kiedy?”), potem wyszukiwanie na podstawie tego rozpoznania.

**Test:** 124 wiersze pf z `--cfg pf_mode=split` jako pierwszy, tani krok, bo to nie wymaga zmiany kodu. Porównaj z 84/124.

## 5. Dopasowanie: 15 błędów (11 z Wikipedii, 4 CKE)

- **Hipoteza „powtórzone litery albo zła liczba par”: OBALONA** (0 przypadków).
- **Zamiana dwóch par o podobnej roli, 6 przypadków:** dev-c-074 (rzecznicy obu stron Okrągłego Stołu), dev-c-007 (TDP i komitet Lelewela), dev-g-050 (Cezar i Antoniusz), dev-h-054, dev-f-013, dev-g-003.
- **Kopiowanie przykładu formatu z polecenia: POTWIERDZONE, mała próbka.** Dotyczy 2 z 7 pytań, w których polecenie zawiera przykład („1-B, 2-A, 3-D, 4-C”). 3 z 4 błędnych par pochodzą z przykładu: dev-b-034 (pary 2-A i 3-D), dev-b-066 (para 1-A).
  - Zmiana: zastąpić litery w przykładzie formatu neutralnym „1-X, 2-X…” przed wysłaniem do modelu.
- **`abcd_parts`: POTWIERDZONE.** cke23-21 jako `abcd_parts` ma oba podpunkty błędne (1-D, 2-B zamiast 1-B, 2-C). To samo zadanie jako dwa osobne abcd (cke2305-21.1 i 21.2) jest rozwiązane dobrze.
  - Zmiana: każdy podpunkt jako osobne wywołanie abcd.
- **Brak artykułu źródłowego, 3 przypadki:** dev-b-034, dev-b-066, dev-h-056 (patrz punkt 2).

## 6. ABCD: 13 błędów (7 z Wikipedii, 6 CKE)

**Hipoteza „skłonność przeciw odpowiedzi A”: OBALONA dla pytań z Wikipedii, NIEROZSTRZYGNIĘTA dla CKE.**
- W `dev-h.jsonl` wszystkie 25 pytań abcd mają poprawną odpowiedź A (sprawdzone). Ten zbiór jest też trudniejszy w innych typach.
- Poza dev-h, tylko pytania z Wikipedii: błędy przy A to 1/35, a przy B/C/D 2/84.
- Poza dev-h razem z CKE: A 5/43 wobec B/C/D 4/101 (Qwen 7/43 wobec 1/101, bez LoRA 3/43 wobec 8/101). Nadwyżka to 4 z 8 zadań CKE z poprawnym A, głównie typu „Podaj literę A albo B” (porównanie fragmentów źródeł). Przy błędzie LoRA nigdy nie wybiera A (0 na 13), ale próbka jest za mała.
- Test rozstrzygający (DO TESTU): cykliczna permutacja opcji w pytaniach abcd z dev-h i w zadaniach CKE „A albo B”. Jeśli trafność się nie zmieni, skłonności do pozycji nie ma.
- Rzeczywiste przyczyny to brak artykułu źródłowego (5 z 7 błędów z Wikipedii) oraz wybór najbardziej znanej przynęty: Ankona (h-006), Łuck (h-011), Prusy Wschodnie (h-023).
- **Zbiór:** dev-f i dev-g nie mają ani jednej odpowiedzi D, a dev-h ma same A. Warto przetasować opcje, żeby benchmark nie nagradzał pozycji.
- **CKE:** 3 zadania „rozstrzygnij A czy B / który najwcześniej” (cke2405-7, cke2405-15.2, cke2505-11.2). Wersja bez LoRA rozwiązuje 2 z nich.

## 7. Pytania otwarte: 35 błędów

Ręczny audyt objął 35 odpowiedzi otwartych i 33 pytania z identyczną złą odpowiedzią obu modeli, łącznie 62 unikalne pozycje. Wynik: 51 to prawdziwe błędy modelu, 8 to poprawne odpowiedzi brakujące na liście accept, 2 pytania są niejednoznaczne, 1 to prawdopodobny błąd klucza.

**Wśród 35 błędów otwartych:** 13 to zadania explain (punkt 3), 8 to poprawne warianty spoza listy accept (punkt 8), a reszta to błędy wiedzy albo wyszukiwania.

**Przekręcanie rzadkich nazw (POTWIERDZONE, niezależne od LoRA):**
- z LoRA: hadżdżra/hidżra (a-018), Baamberg (a-045), defenstracja (b-035);
- bez LoRA: szmalkaldski, Defenstrancja;
- Qwen: jeszcze więcej.

**Reguła „dociągnij do tytułu z kontekstu”:** przetestowana na samych tytułach, 0 napraw. Poprawna forma bywa w treści fragmentu, a nie w tytule, więc warto ją sprawdzić na tekście fragmentów (DO TESTU).

**Sufit oceny ścisłej:** 8 zadań explain z cke-2023 ma wzorzec w postaci zdania. Dopasowanie dokładne ich nie zaliczy, więc maksimum strict to 505/513 (98,4%).

## 8. Pomiar i zestawy (nie model, ale wpływa na decyzje)

- **Duplikaty.** tourney160 składa się w całości z pytań innych plików: cke-more 35, dev-h 25, dev-a 19, dev-c 19, dev-b 18, dev-f 17, dev-g 17, cke-2023 10. Na 513 unikalnych pytaniach wynik to 75,4%, praktycznie tyle samo co 75,5% na 673 wierszach. Raportujmy jednak unikalne pytania.
- **Niedeterminizm przy temperature 0:** te same pytania w dwóch plikach dały różną odpowiedź w 7 ze 160 par (4,4%): dev-c-035, c-047, f-037, g-047, h-035, cke2505-5.1, cke2605-12.1. Najpewniej wynika to z równoległych slotów llama-servera. Różnice między konfiguracjami poniżej ~2 pkt nie są istotne.
- **Błąd w ocenie łagodnej (DO POTWIERDZENIA w `devset/eval.py`, `grade`).** „Nie” jest zaliczane przy wzorcu „Tak” (cke23-16.1, cke23-17, cke23-4.2). Prawdopodobny mechanizm: warunek `len(pn) >= 3 and pn in x` znajduje „nie” wewnątrz akceptowanego wariantu „Rozstrzygnięcie: Tak” po zwinięciu diakrytyków. Zawyża to wyniki lenient.
- **Luki w listach accept, +1,2 do +1,8 pkt:**
  - Poprawne odpowiedzi oceniane jako błąd: „pokój w Karłowicach” (h-058), „200 tys” (f-015), „komandosowie” (c-067), „Mokotów” (f-017), „Wilhelm z Hollandii” (g-041), literówki Baamberg i defenstracja.
  - Reguły ogólne naprawiają 6 z 8 przypadków bez fałszywych trafień: rozwijanie nawiasów we wzorcu, normalizacja liczb („tys”, spacje), tolerancja fleksji oraz fuzzy (Levenshtein ≤1, ale nie na końcu słowa, bo „Magdalena” ≠ „Magdalenka”).
- **Klucz do poprawy lub weryfikacji:**
  - dev-a-066: Długosz od początku leżał na Skałce, więc zdanie 3 powinno być F. Pewność umiarkowana.
  - dev-c-002: Związek Niemiecki liczył 34 albo 35 państw, zależnie od źródła.
  - dev-h-009: sformułowanie niejednoznaczne.
  - dev-h-023: w treści pytania jest Warmia.
  - dev-h-040 i dev-b-022: pytania niejednoznaczne.

## Czego nie potwierdziłem

- **Hipotezy DO TESTU** z punktów 1–5 wymagają uruchomienia modelu. Każda ma listę pytań do testu.
- **Pełne daty w chronologii:** zysk zależy od tego, czy model zna dzień i miesiąc, a tego nie da się sprawdzić offline.
- **Stopword „i” w wyszukiwarce:** tylko poszlaka z trafności, kodu tokenizera nie sprawdzałem.
- **Nie-determinizm llama-servera:** przyczyna jest prawdopodobna, ale nie zweryfikowana.
