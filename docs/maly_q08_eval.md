# „Mały, ale wariat”: ocena CKE Qwen3.5-0.8B na trzech arkuszach (26.09.2026)

Oceniłem, jak egzaminator CKE, odpowiedzi Qwen3.5-0.8B (Q8_0) z `devset/cke_full/answers_q08_{raw,bm25,v3}_{cke2024,cke2025,cke2026}.jsonl`. To części tekstowe arkuszy CKE 2024 (30 pozycji, 47 pkt), 2025 (24 pozycje, 43 pkt) i 2026 (25 pozycji, 41 pkt), razem 79 pozycji i 131 pkt na konfigurację. Metodyka jest ta sama co w `docs/cke_full_eval.md`. Oceny pozycja po pozycji są w `devset/cke_full/grades.jsonl`, systemy `q08_raw`, `q08_bm25` i `q08_v3` (237 wierszy). Ten dokument nie cytuje treści arkuszy.

Konfiguracje (wszystkie z wyłączonym thinkingiem):

- **raw**: samo pytanie, `--mode raw`, limit 1400 tokenów.
- **bm25**: harness v2, `QTYPE_V2=1 RERANK=0 CKE_MODE=0 TOP_K=4`.
- **v3**: harness v3 bez rerankera, `QTYPE_V2=1 RERANK=0 CKE_MODE=1 TOP_K=4`.

## Wynik

Margines liczę względem progu 35%, w punktach procentowych.

| Konfiguracja | Arkusz | Zamknięte | Otwarte | Wypracowanie | Razem | % | Margines do 35% |
|---|---|---|---|---|---|---|---|
| raw | CKE 2024 | 1/5 | 4/27 | 1/15 | 6/47 | 12,8 | −22,2 |
| raw | CKE 2025 | 2/6 | 0/22 | 0/15 | 2/43 | 4,7 | −30,3 |
| raw | CKE 2026 | 1/6 | 1/20 | 0/15 | 2/41 | 4,9 | −30,1 |
| **raw** | **razem** | **4/17** | **5/69** | **1/45** | **10/131** | **7,6** | **−27,4** |
| bm25 | CKE 2024 | 4/5 | 5/27 | 1/15 | 10/47 | 21,3 | −13,7 |
| bm25 | CKE 2025 | 3/6 | 1/22 | 1/15 | 5/43 | 11,6 | −23,4 |
| bm25 | CKE 2026 | 1/6 | 3/20 | 1/15 | 5/41 | 12,2 | −22,8 |
| **bm25** | **razem** | **8/17** | **9/69** | **3/45** | **20/131** | **15,3** | **−19,7** |
| v3 | CKE 2024 | 2/5 | 2/27 | 1/15 | 5/47 | 10,6 | −24,4 |
| v3 | CKE 2025 | 2/6 | 3/22 | 1/15 | 6/43 | 14,0 | −21,0 |
| v3 | CKE 2026 | 3/6 | 2/20 | 1/15 | 6/41 | 14,6 | −20,4 |
| **v3** | **razem** | **7/17** | **7/69** | **3/45** | **17/131** | **13,0** | **−22,0** |

Kategorie są takie same jak w `docs/cke_full_eval.md`. „Zamknięte” to ABCD, P/F i przyporządkowanie z podanej listy.

## Czy próg 35% jest spełniony

**Nie, w żadnej konfiguracji i na żadnym arkuszu.**

- Najlepsza konfiguracja, bm25, ma 15,3%, czyli 20 ze 131 pkt. Do 35% brakuje jej 26 pkt, a do 45% brakuje 39 pkt.
- Najlepszy pojedynczy wynik to bm25 na arkuszu 2024: 21,3%, czyli 13,7 pp poniżej progu.
- Na próbnym arkuszu (maj 2023, 60 pkt, z opisami obrazów; szczegóły w `docs/mock_internal_eval.md`) najlepszy Qwen, `qwen08-harness-v3-bm25`, ma 12/60, czyli 20,0%. Do 35% brakuje mu 9 pkt, a do 45% brakuje 15 pkt.
- Pełny arkusz CKE ma więcej pozycji z obrazami niż części tekstowe ocenione tutaj. Opisy obrazów dodały Qwenowi na próbnym arkuszu tylko 1 pkt (zadanie 15), więc wynik na pełnym arkuszu będzie podobny albo niższy.
- Szum między przebiegami to około ±3 pkt na arkusz. Różnice między bm25 i v3 (20 wobec 17 pkt) mieszczą się w tym szumie. Różnica między harnessem i raw (+7 do +10 pkt) jest realna.

Dla porównania: Bielik-4.5B raw na tych samych 131 pkt ma 51 (38,9%). Qwen 0.8B z harnessem osiąga mniej więcej 40% wyniku surowego Bielika.

## Gdzie Qwen traci punkty

Podział według typu polecenia. Pozycje zamknięte są tu liczone razem z jednym przyporządkowaniem nazw, dlatego jest ich 19 pkt, a nie 17.

| Typ polecenia | Pozycje | Pkt możliwe | raw | bm25 | v3 |
|---|---|---|---|---|---|
| Wypracowanie | 3 | 45 | 1 | 3 | 3 |
| Identyfikacja („Podaj nazwę/nazwisko/imię/datę”, „Wymień”) | 25 | 27 | 1 | 3 | 3 |
| Rozstrzygnięcie z uzasadnieniem | 20 | 20 | 1 | 1 | 1 |
| Zamknięte (ABCD, P/F, przyporządkowanie) | 17 | 19 | 4 | 8 | 7 |
| Wyjaśnienie, argument | 11 | 14 | 0 | 1 | 0 |
| Porównanie (podobieństwo/różnica) | 3 | 6 | 3 | 4 | 3 |

Najważniejsze przyczyny strat, od największej:

1. **Wypracowanie: 42–44 z 45 pkt straconych.** Żadna praca nie dostała punktów w kryterium A. Wiedza jest niefunkcjonalna i każda praca ma ponad 5 błędów rzeczowych, np. zdarzenia z innej epoki albo pomylone osoby. Punkty pochodzą tylko z kryterium B (spójność, 1 pkt).
   - raw na wszystkich trzech arkuszach zaczyna od „propozycji odpowiedzi” zamiast wypracowania. W 2024 pisze wszystkie trzy tematy naraz, w 2025 i 2026 wpada w pętlę (12% unikalnych słów).
   - v3 w 2026 wkleja do pracy instrukcję z własnego promptu („Podaj 2–3 konkretne fakty…”).
   - Praca v3 z 2025 ma sprzeczne stanowisko: we wstępie „zgadzam się”, w zakończeniu „nie”.
2. **Identyfikacja: 24–26 z 27 pkt straconych.** Model 0.8B nie zna faktów z programu matury. Zgaduje przypadkową postać z tej samej epoki, podaje nazwisko autora opracowania zamiast postaci albo przepisuje polecenie. RAG trafił tylko 2–3 razy na 25 pozycji. Odpowiedzi, które coś trafiają, pochodzą z bm25 albo v3.
3. **Rozstrzygnięcia: 19 z 20 pkt straconych.** Nawet przy trafnym rozstrzygnięciu uzasadnienie opiera się na zmyślonych datach i osobach albo przeczy rozstrzygnięciu (np. „Nie, … dotyczą tego samego”). Kilka odpowiedzi nie wybiera żadnego wariantu z polecenia.
4. **Zamknięte: 11–15 z 19 pkt straconych.** P/F są na poziomie losowym. ABCD raw zgaduje, harness trafia częściej (bm25 8, v3 7, raw 4). Przyporządkowania „1-A, 2-B” zamiast nazw władców dają 0.
5. **Degeneracja tekstu** (dotyczy wszystkich typów):
   - raw ma 10 z 79 odpowiedzi zapętlonych i 8 uciętych na limicie 1400 tokenów.
   - bm25 ma 1 pętlę, v3 ma 2 wycieki promptu.
   - Na próbnym arkuszu `qwen08-base-raw` ma 7 wycieków instrukcji („Odpowiedź po polsku, bez toku rozumowania…”).
6. **Porównania to jedyny typ, w którym Qwen coś zdobywa.** Punkty pochodzą z przepisania zdań ze źródeł, więc tę samą ocenę dostaje także raw.

## Plan dojścia do ≥ 45%

Uczciwa ocena: 0.8B, który sam generuje treść, nie osiągnie 45%. Nie ma wiedzy faktograficznej i nie utrzymuje spójnego długiego tekstu. Realny cel na pełnym arkuszu (60 pkt) to 35% (21 pkt). 45% (27 pkt) wymaga, żeby prawie cały wynik pochodził z retrievalu i szablonów, a model tylko wybierał i formatował.

Poniżej zmiany w kolejności oczekiwanego zysku na arkuszu 60-punktowym, liczonego od obecnych około 12 pkt. Wszystkie mieszczą się w zasadach: jeden LLM, pomocnicze modele retrievalu, zero internetu.

1. **Pozycje zamknięte przez scoring opcji, nie przez generację. Oczekiwany zysk: +2–3 pkt.**
   - Dla ABCD, P/F i przyporządkowań liczyć logprob każdej opcji (A/B/C/D, P/F) z kontekstem RAG i źródłami, zamiast generować tekst.
   - Dodać głosowanie po 3–5 permutacjach kolejności opcji.
   - To usuwa formatowe zera i losowość. Cel: 8/11 na próbnym arkuszu, obecnie 4–7.
2. **Identyfikacja ekstrakcyjna. Oczekiwany zysk: +3–4 pkt.**
   - Dla „Podaj nazwę/nazwisko/imię/datę” reranker (bge-reranker-v2-m3) wybiera fragment KB.
   - Kandydatów na encje wyciągać regułami (nazwy własne, daty, lata) z top-k fragmentów oraz ze źródeł w zadaniu. Model wybiera jedną z listy przez scoring, a nie pisze z pamięci.
   - Krótki limit tokenów (32–48) i format „tylko nazwa”.
   - Reguły szczegółowości jak u Bielika: państwo, a nie miasto; imię z przydomkiem lub numerem.
3. **Szablon wypracowania z faktami z KB. Oczekiwany zysk: +3–5 pkt.**
   - Jeden temat wybierany według pokrycia w retrievalu.
   - Stała rama: teza z wariantu polecenia, trzy akapity po jednym na element tematu, zakończenie. Każdy akapit to osobne krótkie wywołanie (≤ 180 tokenów) z 2–3 datowanymi faktami z KB wstawionymi do promptu.
   - Filtr po generacji: usuwać zdania z datą lub nazwą spoza kontekstu, zdania powtórzone i wycieki instrukcji. Pilnować progu 300 słów.
   - Cel: B = 2–3 i A = 1–3, obecnie 1 pkt łącznie.
4. **Rozstrzygnięcia jako wybór plus cytaty. Oczekiwany zysk: +2–3 pkt.**
   - Wariant wybierany scoringiem spośród tych z polecenia („Tak/Nie”, „A/B”, „przed/po”).
   - Uzasadnienie składane z dwóch krótkich cytatów lub parafraz: po jednym z każdego wymaganego źródła, wskazanym przez reranker, i jednego zdania łączącego.
   - Nic z pamięci modelu. To likwiduje zmyślone uzasadnienia, a przy trafnym wyborze daje punkt.
5. **Twarde zabezpieczenia przed degeneracją. Oczekiwany zysk: +1–2 pkt.** Działają pośrednio we wszystkich typach.
   - `repeat_penalty` / `DRY`, `max_tokens` zależne od typu, stop na powtórzonej linii.
   - Czyszczenie wycieków promptu, jeden temat wypracowania.
   - Walidator formatu etykiet („Rozstrzygnięcie:”, „Uzasadnienie:”).
6. **LoRA na krótkich kanonicznych odpowiedziach. Oczekiwany zysk: +1–2 pkt.**
   - Wyłącznie format i wybór opcji, zgodnie z polityką zespołu: cele to „B”, „P, F”, nazwa lub rok. Można wykorzystać trwające `rft_sample`/`train_lora`.
   - Adapter wyłączony dla wyjaśnień i wypracowań, jak u Bielika.
7. **Porównania ekstrakcyjne. Oczekiwany zysk: +0,5–1 pkt.** Podobieństwo i różnica jako dwa zestawienia zdań ze źródeł. Ta metoda już działa, trzeba ją tylko ustabilizować.

Suma zysków to +12,5–20 pkt, czyli z około 12 do 25–32 pkt (42–53%). Dolna granica przekracza 35%. Górna daje 45% tylko wtedy, gdy punkty 1–4 zadziałają jednocześnie. Proponowana kolejność prac:

1. Pozycje zamknięte (1) i zabezpieczenia (5): tanie, pewne, mierzalne na próbnym arkuszu w godzinę.
2. Identyfikacja (2).
3. Wypracowanie (3).

Każdą zmianę mierzyć na próbnym arkuszu 2023 oraz na jednym arkuszu 2024–2026, nie na wszystkich naraz, bo przepustowość GPU jest dzielona z treningiem.

## Metodyka i zastrzeżenia

- **Ocena ślepa.** Trzy odpowiedzi na pozycję dostały losowe etykiety X/Y/Z, a mapowanie zostało w notatniku. Style raw (markdown, pętle) i harnessu bywają rozpoznawalne.
- **Reguły** są takie same jak w `docs/cke_full_eval.md` i `docs/cke_grading_rules.md`:
  - Każda pozycja „wszystko albo nic”, chyba że klucz przewiduje punkty częściowe.
  - P/F: 3/3 → 2 pkt, 2/3 → 1 pkt.
  - W zamkniętych liczy się jawny wybór końcowy.
  - Kilka odpowiedzi naraz albo sprzeczne odpowiedzi → 0.
  - Wypracowanie: oceniany jest pierwszy temat; poniżej 300 słów B = 0; kary za błędy w A.
  - Nadmiarowy błędny element w wyliczeniu → 0, spójnie z oceną Bielika z 26.09 (2026 5.2).
- **Werdykty graniczne**, każdy może przesunąć wynik o 1 pkt:
  - 2024: 12.3 w raw (1 pkt), 16.1 w bm25 (1 pkt).
  - 2025: 8 w v3 (1 pkt), 17.1 w bm25 (0 pkt).
  - 2026: 16.1 w bm25 (1 pkt).
- **Jeden oceniający AI, jeden przebieg na konfigurację.** Szum wynosi około ±3 pkt na arkusz. Wniosek, że żadna konfiguracja nie zbliża się do 35%, jest odporny na ten szum.
