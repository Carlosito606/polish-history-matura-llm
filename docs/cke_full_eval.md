# Ocena CKE: cztery arkusze, trzy systemy (26.09.2026)

Oceniłem, jak egzaminator CKE, wszystkie odpowiedzi z `devset/cke_full/answers_*.jsonl`. To 113 pozycji na system, 186 pkt możliwych: tekstowy benchmark mentora 2023 (55 pkt) oraz części tekstowe arkuszy CKE 2024 (47 pkt), 2025 (43 pkt) i 2026 (41 pkt). Oceny pozycja po pozycji są w `devset/cke_full/grades.jsonl` (plik git-ignored, bo zawiera fragmenty kluczy CKE). Ten dokument nie cytuje treści arkuszy.

Systemy:

- **(a) raw**: Bielik-4.5B-v3 Q8_0, bez LoRA i bez RAG, samo pytanie.
- **(b) harness + LoRA**: RAG (QTYPE_V2, RERANK) z adapterem, który harness wyłącza dla wyjaśnień i wypracowań.
- **(c) harness bez LoRA**.

## Wynik

| System | Arkusz | Zamknięte | Otwarte | Wypracowanie | Razem | % |
|---|---|---|---|---|---|---|
| (a) raw | mentor 2023 | 6/11 | 14/29 | 1/15 | 21/55 | 38,2 |
| (a) raw | CKE 2024 | 2/5 | 14/27 | 2/15 | 18/47 | 38,3 |
| (a) raw | CKE 2025 | 4/6 | 12/22 | 1/15 | 17/43 | 39,5 |
| (a) raw | CKE 2026 | 3/6 | 11/20 | 2/15 | 16/41 | 39,0 |
| **(a) raw** | **razem** | **15/28** | **51/98** | **6/60** | **72/186** | **38,7** |
| (b) harness + LoRA | mentor 2023 | 4/11 | 20/29 | 1/15 | 25/55 | 45,5 |
| (b) harness + LoRA | CKE 2024 | 2/5 | 13/27 | 3/15 | 18/47 | 38,3 |
| (b) harness + LoRA | CKE 2025 | 5/6 | 11/22 | 5/15 | 21/43 | 48,8 |
| (b) harness + LoRA | CKE 2026 | 2/6 | 9/20 | 6/15 | 17/41 | 41,5 |
| **(b) harness + LoRA** | **razem** | **13/28** | **53/98** | **15/60** | **81/186** | **43,5** |
| (c) harness bez LoRA | mentor 2023 | 3/11 | 21/29 | 4/15 | 28/55 | 50,9 |
| (c) harness bez LoRA | CKE 2024 | 1/5 | 13/27 | 3/15 | 17/47 | 36,2 |
| (c) harness bez LoRA | CKE 2025 | 4/6 | 10/22 | 5/15 | 19/43 | 44,2 |
| (c) harness bez LoRA | CKE 2026 | 1/6 | 7/20 | 6/15 | 14/41 | 34,1 |
| **(c) harness bez LoRA** | **razem** | **9/28** | **51/98** | **18/60** | **78/186** | **41,9** |

„Zamknięte” to ABCD, P/F i przyporządkowanie z podanej listy. Na benchmarku mentora daje to te same 11 pkt, które liczy mentor. Krótkie odpowiedzi z nazwą lub nazwiskiem liczę jako otwarte.

Na samych arkuszach CKE 2024–2026 (131 pkt) wychodzi: (a) 51 (38,9%), (b) 56 (42,7%), (c) 50 (38,2%). Pełny arkusz ma 60 pkt, a 13–19 pkt na arkusz przypada na pominięte zadania wymagające obrazu. Bez opisów obrazów realny wynik (b) na pełnym arkuszu to około 31–36%.

## Porównanie z bazami mentora (tekstowy benchmark 2023, 55 pkt)

| Model | Razem | Zamknięte /11 | Otwarte /29 | Wypracowanie /15 |
|---|---|---|---|---|
| Bielik-4.5B-v3 (mentor, v0.1 greedy, BF16) | 23 (41,8%) | 6 | 15 | 2 |
| **(a) nasz raw (Q8_0)** | **21 (38,2%)** | 6 | 14 | 1 |
| **(b) harness + LoRA** | **25 (45,5%)** | 4 | 20 | 1 |
| **(c) harness bez LoRA** | **28 (50,9%)** | 3 | 21 | 4 |
| Qwen3-4B-Instruct-2507 | 22 (40,0%) | 7 | 12 | 3 |
| Gemma-3-4B | 20 (36,4%) | 10 | 7 | 3 |
| LLaVA-Bielik-11B (tekst) | 29 (52,7%) | 5 | 21 | 3 |
| Ministral-3-14B (tekst) | 33 (60,0%) | 5 | 25 | 3 |

- **Metodyka jest zgodna z mentorską.** Nasz raw (21) mieści się w 2 pkt od opublikowanego wyniku tego samego modelu (23), przy identycznym wyniku zamkniętych (6).
- **Harness podnosi część otwartą.** Otwarte rosną z 14 do 20–21 pkt, czyli do poziomu LLaVA-Bielik-11B.
- **Harness obniża część zamkniętą.** Zamknięte spadają z 6 do 3–4 pkt: harness wymusza goły wybór litery, bez rozumowania.
- Arkusz 2023 jest publiczny, więc może być w danych treningowych modeli.

## Zysk (b) i (c) względem surowej bazy (a)

| | mentor 2023 | CKE 2024 | CKE 2025 | CKE 2026 | razem (186) |
|---|---|---|---|---|---|
| (b) − (a) | +4 | 0 | +4 | +1 | **+9 (+4,8 pp)** |
| (c) − (a) | +7 | −1 | +2 | −2 | **+6 (+3,2 pp)** |

Ten sam zysk w podziale na kategorie:

| | zamknięte | otwarte | wypracowanie |
|---|---|---|---|
| (b) − (a) | −2 | +2 | **+9** |
| (c) − (a) | −6 | 0 | **+12** |

- **Cały zysk pochodzi z trybu wypracowania.** Bez wypracowań (126 pkt) wyniki wynoszą: (a) 66, (b) 66, (c) 60. Ścieżka krótkich odpowiedzi harnessu w obecnej postaci nie daje nic ponad surowy model. Z LoRA wychodzi na zero, bez LoRA traci 6 pkt.
- **LoRA naprawia to, co psuje ścieżka krótkich odpowiedzi.** Na 54 pozycjach z LoRA włączonym (63 pkt) wyniki wynoszą: (a) 35, (b) 34, (c) 28. Adapter daje +6 względem (c), głównie przez format. Odpowiedzi wieloczłonowe mieszczą się w jednej linii, więc stop na znaku nowej linii ich nie ucina: 2025 11.1, 2026 5.1 i 6.1.
- **Szum między przebiegami:** około 3 pkt. Na 59 pozycjach z LoRA wyłączonym (b) i (c) powinny być identyczne. Jedyna różnica to wypracowanie 2023: (b) 1, (c) 4, efekt niedeterminizmu przy równoległych żądaniach. Różnice poniżej około 4 pkt na arkusz nie są istotne.

## Wypracowania

| | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|
| (a) raw | 1: trzy tematy naraz, pierwszy ma 280 słów | 2: 255 słów, B=0 | 1: temat 1956 z błędami | 2: 290 słów, B=0 |
| (b) | 1: jako wydarzenia lat 50. podane 1962, 1972 i kino | 3: A1 + B2 | 5: A3 + B2 | 6: A4 + B2 |
| (c) | 4: A3 + B1 | 3: A1 + B2 | 5: A3 + B2 | 6: A4 + B2 |

Tryb wypracowania harnessu robi swoje: jeden temat, stanowisko, powyżej 300 słów, struktura wstęp–rozwinięcie–zakończenie. Wszystkie jego wypracowania kończą się jednak na poziomie A 0–4/12 i B 1–2/3. Powody:

- **Argumentacja jest powierzchowna.** Większość elementów dostaje 1 pkt, co najwyżej jeden element dostaje 3.
- **Zdarzają się 2–3 błędy rzeczowe na pracę**, co kosztuje −1 albo −2 pkt.
- **Tezy z „najbardziej/najwybitniejszy” nie mają porównania.**
- **Nagłówek jest zdublowany z literówką** („WYPROCOWANIE/WYPROCOWAĆ NA TEMAT NR X”), a w 2025 praca przepisuje polecenie. Oba zabiegi obniżają spójność.
- **W 2023 wybrane wydarzenia wypadły poza okres z tematu.**

## Główne typy błędów

Rozkład dotyczy najlepszego systemu (b), który stracił 105 pkt.

| # | Typ błędu | Stracone pkt | Przykłady (arkusz, pozycja) |
|---|---|---|---|
| 1 | Wypracowanie: płytka argumentacja, błędy rzeczowe, spójność | 45 (43%) | wszystkie cztery |
| 2 | Pozycje zamknięte (P/F z wiedzą, ABCD z pamięci, format przyporządkowania) | 15 | 2023: 3, 19, 21; 2024: 11.1, 16.2; 2025: 5.1; 2026: 2, 3.2, 14.3, 15.2 |
| 3 | Identyfikacja i przypominanie faktów mimo RAG, w tym zła szczegółowość (miasto zamiast państwa, samo imię bez przydomka) | 15 | 2023: 9.3, 14.1, 25.1; 2024: 3.1, 3.2, 5.2, 12.1, 17.2; 2025: 4, 9.3; 2026: 12.1, 16.2 |
| 4 | Uzasadnienie bez odwołania do treści źródła albo ze zmyślonym szczegółem, połowiczne porównania | 14 | 2023: 22, 24; 2024: 9, 22.2; 2025: 24.1; 2026: 11, 14.2, 17 |
| 5 | Złe rozstrzygnięcie w zadaniach „Rozstrzygnij…” | 13 | 2023: 20; 2024: 2, 7, 15.2; 2025: 22; 2026: 4.1, 22, 23.1 |
| 6 | Treść dostępna tylko na obrazie | 3 | 2025: 8, 23 |

- **Harness ma skrzywienie na „Tak”.** W 17 rozstrzygnięciach typu tak/nie (b) i (c) odpowiedziały „Tak” 12 razy. Odpowiedziały „Tak” we wszystkich 6 pozycjach z kluczem „tak” i w 6 z 11 pozycji z kluczem „nie”. Raw jest bardziej wyważony. Arkusze CKE celowo zestawiają źródła podobne tematycznie, ale dotyczące różnych wydarzeń.
- **Na pozycjach zamkniętych harness przegrywa z raw (13 i 9 wobec 15).** Raw rozumuje przed wyborem i trafia tam, gdzie harness (sama litera) się myli: 2023 21 (2 pkt), 2024 16.2, 2026 3.2, 2026 15.2.

Błędy techniczne harnessu:

- Zdublowany nagłówek wypracowania.
- Samą etykietę arkusza odpowiedzi zamiast odpowiedzi, np. „Wystawca:”, oddał (c) w 2026 5.1 i 5.2.
- Stop na znaku nowej linii ucina odpowiedzi wieloczłonowe w (c): 2025 11.1, 2026 6.1.
- Typ `match` wymusza format „1-B, 2-A” tam, gdzie trzeba wpisać nazwiska władców: 2024 11.1, 2025 5.1.

## Trzy poprawki według oczekiwanego zysku punktowego

1. **Tryb wypracowania: jakość, nie tylko forma. Oczekiwany zysk: +3–4 pkt na arkusz.** Wypracowanie to 43% strat.
   - Usunąć zdublowany nagłówek i przepisywanie polecenia w kroku czyszczenia. To powinno dać B=3 zamiast 1–2, czyli +1 pkt na pracę.
   - Wymusić akapit na każdy z trzech elementów tematu, a w każdym 2–3 datowane fakty z odzyskanych fragmentów i zdanie wiążące z tezą.
   - Przy tezach z „najbardziej” dodać porównanie z alternatywą.
   - Dodać przebieg weryfikujący: usunąć zdania z datą lub nazwą, której nie ma w kontekście RAG. Kara za błędy powinna spaść z −2 do −1 lub 0.
   - Wymusić ramę czasową tematu (np. „lata 50.”) i wybierać temat z najlepszym pokryciem w wyszukiwaniu.
   - To powinno podnieść A z około 4 do 6–7.
2. **Rozstrzygnięcia: dwuetapowy tryb z porównaniem referentów. Oczekiwany zysk: +1–1,5 pkt na arkusz.**
   - Najpierw ustalić dla każdego źródła osobno kto, co i kiedy (osobne zapytanie RAG na źródło). Dopiero potem porównać.
   - Odpowiedzieć „Tak” tylko wtedy, gdy oba źródła dotyczą tego samego wydarzenia, dokumentu lub okresu.
   - Pole „Rozstrzygnięcie:” wypełniać wariantem z polecenia („po reformie”, „przeciwników”, „A”), nigdy gołym „Tak”. W tej ocenie dwa takie przypadki (2025 2 i 15.2) uznałem, bo treść jest jednoznaczna. Surowy egzaminator mógłby dać za nie 0.
3. **Pozycje zamknięte: krótkie rozumowanie, potem wybór, oraz poprawny format przyporządkowania. Oczekiwany zysk: +1–1,5 pkt na arkusz.**
   - Dla typów abcd, pf i match pozwolić na 2–3 zdania rozumowania i wyciągać ostatnią jawną odpowiedź. Raw, który rozumuje, bije harness na zamkniętych.
   - Dla poleceń „przyporządkuj władcę/państwo” wypisywać nazwy („Fragment A – …”), a nie pary cyfra–litera.
   - Odpowiedzi wieloczłonowe zawsze składać w jednej linii, bez stopu na nowej linii. Ten punkt dotyczy głównie (c).

Mniejsze poprawki poza pierwszą trójką:

- Reguły szczegółowości: dla „państwa” podawać państwo, nie miasto; dla „imienia i przydomka” oba człony.
- Obowiązkowe odwołanie do konkretu z każdego wskazanego źródła (typ błędu 4).

## Metodyka i zastrzeżenia

- **Ocena ślepa.** Dla każdej pozycji trzy odpowiedzi dostały losowe etykiety X/Y/Z, a mapowanie zostało w notatniku. Styl raw (markdown, rozwlekłość) i tak bywa rozpoznawalny.
- **Reguły** według `docs/cke_grading_rules.md` i zasad oceniania z `rubric_text`:
  - Każda pozycja „wszystko albo nic”, chyba że klucz przewiduje punkty częściowe.
  - P/F 3/3 → 2 pkt, 2/3 → 1 pkt.
  - Rozstrzygnięcie bez poprawnego uzasadnienia z odwołaniem do wymaganych źródeł = 0.
  - Akceptowane są wszystkie odpowiedzi merytorycznie poprawne.
- **Zasady mentora:**
  - W zamkniętych liczy się jawny, końcowy wybór (2026 15.2 raw: rozumowanie sprzeczne, końcowe „C” = 1 pkt).
  - Przy kilku tematach wypracowania oceniany jest pierwszy, a liczba słów liczy się tylko dla niego.
  - Poniżej 300 słów B = 0.
  - Kary za błędy: 1–2 → −1, 3–5 → −2, >5 → −3.
- **Błędy poboczne**, które nie naruszają ocenianego elementu, nie zerują odpowiedzi, np. zła data w tle przy poprawnym ogniwie uzasadnienia. Zerują ją, gdy uzasadnienie na nich się opiera.
- **Pozycje bez obrazu**, oceniane z samego podpisu (notatka `note`), traktowałem jak w arkuszu. Jeśli klucz wymaga elementu graficznego, odpowiedź bez niego dostaje 0 (2024 9).
- **Jeden oceniający AI, jeden przebieg na system.** Szum około ±3 pkt na arkusz, głównie przez wypracowanie. Werdykty graniczne (2024 9, 2025 2 i 15.2, 2026 14.2 i 17) mogą przesunąć wynik o 1–2 pkt na system.

Pliki:

- `devset/cke_full/grades.jsonl`: pola system, paper, id, points, max, category, lora, reason; 339 wierszy.
- Odpowiedzi i skrypty uruchomień leżą w tym samym katalogu.
