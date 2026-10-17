# „Mały, ale wariat”: Bielik-1.5B i Qwen3.5-2B wobec progu 35% (26.09.2026)

Oceniłem, jak egzaminator CKE, 32 nowe pliki odpowiedzi:

- 8 próbnych egzaminów: `submissions/mock/{bielik15,qwen2b}-*/answers.json`. To pełny arkusz z maja 2023: 37 pozycji, 60 pkt, w tym zadania z obrazami 7, 8 i 15.
- 24 pliki z częściami tekstowymi arkuszy CKE 2024, 2025 i 2026: `devset/cke_full/answers_{b15,q2b}_{raw,bm25,v3,v3rerank}_cke20{24,25,26}.jsonl`. Razem 79 pozycji i 131 pkt na konfigurację.

Metodyka jest ta sama co w `docs/cke_full_eval.md`, `docs/maly_q08_eval.md` i `docs/mock_internal_eval.md`. Oceny pozycja po pozycji (928 wierszy) dopisałem do `devset/cke_full/grades.jsonl`, systemy `b15_*`, `q2b_*` i `mock_bielik15-*`, `mock_qwen2b-*`. Dokument nie cytuje treści arkuszy.

Modele:

- **Bielik-1.5B-v3.0-Instruct**, Q8_0, 1,70 GB (`b15`, `bielik15`).
- **Qwen3.5-2B**, Q8_0 od unsloth, 2,01 GB, bez thinkingu (`q2b`, `qwen2b`).

Konfiguracje: `raw`, harness v2 z BM25 (`bm25`), harness v3 z BM25 (`v3`), harness v3 z rerankerem (`v3rerank`).

## Wynik: próbny egzamin (60 pkt)

Z = zamknięte, O = otwarte, W = wypracowanie. Margines liczę względem 35%, w punktach procentowych.

| Model | Konfiguracja | Z /11 | O /34 | w tym obrazy /5 | W /15 | Razem /60 | % | Margines |
|---|---|---|---|---|---|---|---|---|
| Bielik-1.5B | raw | 5 | 12 | 2 | 1 | **18** | **30,0** | −5,0 |
| Bielik-1.5B | v2-bm25 | 5 | 11 | 1 | 1 | 17 | 28,3 | −6,7 |
| Bielik-1.5B | v3-bm25 | 3 | 7 | 0 | 3 | 13 | 21,7 | −13,3 |
| Bielik-1.5B | v3-rerank | 4 | 9 | 1 | 2 | 15 | 25,0 | −10,0 |
| Qwen3.5-2B | raw | 6 | 9 | 2 | 0 | 15 | 25,0 | −10,0 |
| Qwen3.5-2B | v2-bm25 | 2 | 6 | 1 | 1 | 9 | 15,0 | −20,0 |
| Qwen3.5-2B | v3-bm25 | 3 | 8 | 1 | 1 | 12 | 20,0 | −15,0 |
| Qwen3.5-2B | v3-rerank | 3 | 11 | 1 | 1 | 15 | 25,0 | −10,0 |

Próg 35% to 21 pkt. Najlepszemu plikowi, Bielik-1.5B raw, brakuje 3 pkt.

## Wynik: arkusze CKE 2024–2026 (części tekstowe, 131 pkt)

| Model | Konfiguracja | 2024 /47 | 2025 /43 | 2026 /41 | Z /17 | O /69 | W /45 | Razem /131 | % | Margines |
|---|---|---|---|---|---|---|---|---|---|---|
| Bielik-1.5B | raw | 9 | 10 | 6 | 4 | 20 | 1 | 25 | 19,1 | −15,9 |
| Bielik-1.5B | bm25 | 8 | 12 | 7 | 4 | 18 | 5 | 27 | 20,6 | −14,4 |
| Bielik-1.5B | v3 | 11 | 10 | 10 | 5 | 20 | 6 | **31** | **23,7** | −11,3 |
| Bielik-1.5B | v3rerank | 11 | 8 | 8 | 5 | 13 | 9 | 27 | 20,6 | −14,4 |
| Qwen3.5-2B | raw | 10 | 9 | 8 | 8 | 16 | 3 | 27 | 20,6 | −14,4 |
| Qwen3.5-2B | bm25 | 10 | 8 | 9 | 6 | 18 | 3 | 27 | 20,6 | −14,4 |
| Qwen3.5-2B | v3 | 11 | 10 | 8 | 7 | 19 | 3 | 29 | 22,1 | −12,9 |
| Qwen3.5-2B | v3rerank | 11 | 9 | 10 | 5 | 20 | 5 | 30 | 22,9 | −12,1 |

Żaden arkusz w żadnej konfiguracji nie przekracza 28%. Najlepszy pojedynczy wynik to Bielik-1.5B bm25 na 2025: 12/43 (27,9%).

## Porównanie z innymi modelami

| Model (rozmiar GGUF) | Najlepsza konfiguracja | Próbny /60 | Arkusze /131 |
|---|---|---|---|
| Qwen3.5-0.8B | v3-bm25 / bm25 | 12 (20,0%) | 20 (15,3%) |
| Bielik-1.5B (1,70 GB) | raw / v3 | 18 (30,0%) | 31 (23,7%) |
| Qwen3.5-2B (2,01 GB) | raw lub v3-rerank / v3rerank | 15 (25,0%) | 30 (22,9%) |
| Bielik-4.5B-v3 (5,06 GB), raw | raw | 25 (41,7%) | 51 (38,9%) |
| Bielik-4.5B-v3 (5,06 GB), harness | v3 / harness + LoRA | 27 (45,0%) | 56 (42,7%) |

Źródła: `docs/maly_q08_eval.md` (0.8B), `docs/mock_internal_eval.md` i `docs/cke_full_eval.md` (4.5B; v3 oceniono na arkuszach tylko dla 2025).

- Przejście z 0.8B na 1.5–2B daje +3 do +6 pkt na próbnym i +10 do +11 pkt na arkuszach.
- Do Bielika-4.5B wciąż brakuje 7–12 pkt na próbnym i 20–26 pkt na arkuszach.
- Wszystkie osiem konfiguracji 1.5–2B mieści się na arkuszach w przedziale 25–31 pkt. Różnice między nimi są w granicach szumu (około ±3 pkt na arkusz).

## Gdzie modele tracą punkty

Punkty w podziale na typ polecenia, suma dla trzech arkuszy (131 pkt).

| Typ polecenia | Pkt możliwe | b15 raw | b15 v3 | b15 v3rerank | q2b raw | q2b v3rerank |
|---|---|---|---|---|---|---|
| Wypracowanie | 45 | 1 | 6 | 9 | 3 | 5 |
| Identyfikacja (nazwa, nazwisko, data) | 29 | 13 | 11 | 5 | 6 | 9 |
| Rozstrzygnięcie z uzasadnieniem | 20 | 4 | 3 | 3 | 4 | 2 |
| Zamknięte (ABCD, P/F, przyporządkowanie) | 17 | 4 | 5 | 5 | 8 | 5 |
| Wyjaśnienie | 14 | 2 | 4 | 3 | 2 | 6 |
| Porównanie | 6 | 1 | 2 | 2 | 4 | 3 |

Najważniejsze przyczyny strat, od największej:

1. **Wypracowanie: 36–44 z 45 pkt straconych na arkuszach, 12–15 z 15 na próbnym.**
   - Najlepsze prace (A1 + B2) to 3 pkt. Kryterium A prawie zawsze wynosi 0–1: ponad 5 błędów rzeczowych, np. „wojna atomowa w Korei”, unia w Krewie jako rok 1939, Hollywood jako dowód apogeum zimnej wojny.
   - Bielik-1.5B raw za każdym razem pisze wszystkie trzy tematy w punktach, około 150–200 słów na temat, więc B = 0.
   - Bielik-1.5B bm25 oddał prace poniżej 300 słów w 2025 i 2026 (B = 0), w tym jedną z wklejoną instrukcją promptu.
   - Qwen raw wpada w pętle. Jedna praca v3-bm25 kończy się „poprawioną wersją” i meta-komentarzem.
2. **Rozstrzygnięcia: 2–4 z 20 pkt na arkuszach i 2–5 z 10 na próbnym.**
   - Modele wpisują „Tak” w polu „Rozstrzygnięcie:” przy poleceniach typu „A czy B”. Mają skrzywienie na „Tak”.
   - Uzasadnienia opierają się na zmyślonych datach i utożsamieniach, np. mowa Aleksandra przypisana Dariuszowi albo Lenino jako armia Andersa.
3. **Identyfikacja: 5–13 z 29 pkt.** Bielik-1.5B raw zna najwięcej (13). Reranker obniża go do 5, bo harness wkleja nietrafione fragmenty KB. Typowe błędy: autor opracowania zamiast postaci (np. nazwisko autora źródła jako polityk), miasto zamiast państwa, statut zamiast konstytucji.
4. **Zamknięte: 4–8 z 17 pkt.** P/F są blisko losowych. Najlepszy jest Qwen raw (8/17, na próbnym 6/11). Przyporządkowania „1-A, 2-B” zamiast nazw władców dają 0.
5. **Śmieci z RAG i wycieki promptu.** W odpowiedziach pojawiają się hasła Wikipedii bez związku z pytaniem (np. „kuweta fotograficzna”, „naczynie włosowate”, gazeta z 1912 roku) oraz fragmenty instrukcji („Odpowiedź po polsku, bez toku rozumowania…”).

## Rekomendacja

**Żadna z ośmiu konfiguracji modeli ≤ 2 GB (2 modele × 4 konfiguracje) nie spełnia progu 35%, a tym bardziej nie z zapasem. Nie zgłaszać Bielika-1.5B ani Qwena3.5-2B jako modeli z wynikiem ≥ 35%.**

- Najbliżej jest Bielik-1.5B raw (1,70 GB): 30,0% na próbnym. Na arkuszach ma jednak 19,1%, więc wynik próbnego jest prawdopodobnie zawyżony szumem.
- Nawet idealne przełączanie konfiguracji według typu pozycji, dopasowane do tych samych danych, daje Bielikowi-1.5B 22/60 (36,7%) i 37/131 (28,2%). To oszacowanie jest optymistyczne i nie daje zapasu.
- **Najmniejszy zmierzony przez nas model z ≥ 35% i zapasem to Bielik-4.5B-v3 Q8_0, 5,06 GB, harness v3 bez LoRA: 45,0% na próbnym, +10 pp nad progiem.** Jeśli regulamin pozwala zgłosić do „Mały, ale wariat” ten sam model co do „progress”, rekomenduję właśnie tę konfigurację.
- Jeśli potrzebny jest inny, mniejszy model, najlepszym kandydatem poniżej 5 GB z opublikowanym wynikiem ≥ 35% jest Qwen3-4B-Instruct-2507: 40,0% na tekstowym benchmarku mentora (Gemma-3-4B ma tam 36,4%, czyli bez zapasu; `docs/cke_full_eval.md`). Sami żadnego z nich nie mierzyliśmy. Przed decyzją potrzebny jest jeden przebieg próbnego egzaminu.

## Najtańsze poprawki (gdyby zespół chciał jeszcze powalczyć modelem 1.5–2B)

Zyski są liczone od Bielika-1.5B raw (18/60 na próbnym, 25/131 na arkuszach).

1. **Przełączanie według typu pozycji, bez nowego kodu: raw dla pozycji krótkich, tryb wypracowania harnessu v3 dla wypracowania (v3rerank: 9/45 na arkuszach, v3-bm25: 3/15 na próbnym).**
   - Na arkuszach: 24 pkt raw bez wypracowania + 9 pkt wypracowań v3rerank = 33/131 (+8 pkt).
   - Na próbnym: 17 + 3 = 20/60 (+2 pkt).
2. **Twarde zabezpieczenia wypracowania.**
   - Jeden temat i minimum 300 słów liczone przed oddaniem; przy krótszej pracy dopisać akapit.
   - Usuwać wklejone instrukcje, meta-komentarze i akapity o pozycjach KB z niskim wynikiem rerankera (próg odcięcia).
   - To daje B = 2 zamiast 0–1, czyli +1–2 pkt na pracę.
3. **Rozstrzygnięcia i pozycje zamknięte jako wybór, nie generacja.**
   - Wariant rozstrzygnięcia wybierać spośród opcji z polecenia („A/B”, „przed/po”, numer fragmentu), nigdy gołe „Tak”.
   - ABCD i P/F oceniać scoringiem logprob opcji.
   - Oczekiwany zysk: +2–4 pkt na arkuszach i +1–2 pkt na próbnym.

Suma tych trzech poprawek daje w najlepszym razie około 21–23/60 na próbnym, czyli 35–38%. To dolna granica progu bez zapasu, więc rekomendacja z poprzedniej sekcji pozostaje bez zmian.

## Metodyka i zastrzeżenia

- **Ocena ślepa.** Osiem odpowiedzi na każdą pozycję dostało losowe etykiety A–H. Mapowanie zostało w notatniku i odkryłem je dopiero po ocenie wszystkich 928 pozycji.
- **Reguły** są takie same jak w poprzednich ocenach:
  - Każda pozycja „wszystko albo nic”, chyba że klucz przewiduje punkty częściowe.
  - P/F: 3/3 → 2 pkt, 2/3 → 1 pkt.
  - Liczy się jawny wybór końcowy.
  - Sprzeczne odpowiedzi → 0.
  - Rozstrzygnięcie bez poprawnego uzasadnienia → 0.
  - Wypracowanie: oceniany jest pierwszy temat; poniżej 300 słów B = 0; kary za błędy w A.
- **Decyzje spójne z poprzednimi ocenami:**
  - „Tak” w polu rozstrzygnięcia uznaję, gdy treść jednoznacznie wskazuje wariant (graniczne).
  - Renta naturalna ze srebrem → 0, tak jak w ocenie Bielika-4.5B.
  - Na próbnym style „neogotycki/neoromański” nie są uznawane za gotycki/renesansowy (zadanie 7).
- **Werdykty graniczne** z przyznanymi punktami (oznaczone w `reason` jako „graniczne”): 3–9 pkt na konfigurację na arkuszach i 1–4 pkt na próbnym. Surowy egzaminator obniżyłby więc wyniki, a nie podniósł. Wniosek, że próg 35% jest poza zasięgiem, na tym nie traci.
- **Jeden oceniający AI, jeden przebieg na konfigurację.** Szum około ±3 pkt na arkusz.
