# Próbny egzamin (history-2023-mock-v1): nasza wewnętrzna ocena (26.09.2026)

Oceniłem, jak egzaminator CKE, pięć plików `submissions/mock/<system>/answers.json`. Próbny egzamin to pełny arkusz CKE z maja 2023: 37 pozycji, 60 pkt, w tym zadania z obrazami 7, 8 i 15 (razem 5 pkt).

Oceniałem według zasad oceniania CKE 2023 (`data_cke/MHIP-R0-100-2305-zasady.pdf`, `rubric_text` z `devset/cke_full/mentor2023.jsonl`) i reguł z `docs/cke_full_eval.md`. Oceny pozycja po pozycji są w `devset/cke_full/grades.jsonl`, systemy `mock_<system>`, paper `mock2023` (185 wierszy).

Ten dokument służy do porównania z oficjalną oceną organizatorów, kiedy przyjdzie. Nie cytuje treści arkusza. Pliki nie zostały jeszcze wysłane.

## Wynik

| System | Konfiguracja | Zamknięte /11 | Otwarte /34 | w tym obrazy /5 | Wypracowanie /15 | Razem /60 | % |
|---|---|---|---|---|---|---|---|
| `bielik45-base-raw` | Q8_0, bez LoRA i RAG | 7 | 16 | 2 | 2 | **25** | **41,7** |
| `bielik45-harness-v3` | CKE_MODE=1, QTYPE_V2=1, RERANK=1, bez LoRA | 4 | 17 | 1 | 6 | **27** | **45,0** |
| `qwen08-base-raw` | Qwen3.5-0.8B, raw, bez thinkingu | 7 | 1 | 0 | 0 | **8** | **13,3** |
| `qwen08-harness-v2-bm25` | QTYPE_V2=1, RERANK=0, TOP_K=4 | 4 | 3 | 1 | 1 | **8** | **13,3** |
| `qwen08-harness-v3-bm25` | CKE_MODE=1, RERANK=0, TOP_K=4 | 7 | 4 | 1 | 1 | **12** | **20,0** |

„Zamknięte” to ABCD, P/F i przyporządkowanie: 2.2, 3, 10, 11.2, 13.2, 19 i 21, razem 11 pkt, jak u mentora. „Otwarte” obejmują zadania z obrazami 7, 8 i 15.

## Wnioski do wyboru zgłoszeń

- **„progress” (Bielik): `bielik45-harness-v3`, 27/60 (45,0%), wobec raw 25/60 (41,7%).** Przewaga 2 pkt mieści się w szumie (około ±3 pkt), ale układ jest ten sam co na arkuszach 2024–2026:
  - Harness wygrywa wypracowaniem: 6 wobec 2 pkt.
  - Harness traci na pozycjach zamkniętych: 4 wobec 7 pkt. P/F w zadaniu 19 i przyporządkowanie w zadaniu 21 dają harnessowi 0, raw ma za nie 3 pkt.
  - Bez tej straty harness miałby około 30/60 (50%). Poprawka „krótkie rozumowanie przed wyborem litery” z `docs/cke_full_eval.md` wciąż jest warta wdrożenia przed testem.
- **„Mały, ale wariat” (Qwen): `qwen08-harness-v3-bm25`, 12/60 (20,0%).** To wyraźnie najlepszy z trzech plików Qwena (+4 pkt), ale 15 pp poniżej progu 35%. v2-bm25 i raw mają po 8 pkt. Szczegóły i plan poprawy są w `docs/maly_q08_eval.md`.
- **Nasza ocena vs text-track z 26.09 na tym samym arkuszu** (tamta ocena bez zadań 7, 8, 15; 55 pkt):
  - raw: 21/55 (38,2%) teraz i 25/60 (41,7%) na próbnym.
  - harness v3: 29/55 (52,7%) teraz i 27/60 (45,0%) na próbnym.
  - Próbny egzamin to nowe przebiegi z innym wejściem (PNG + `image_desc.json` zamiast zamrożonych opisów mentora).
  - Różnice pojawiają się głównie na pozycjach zamkniętych. harness v3 stracił 10 i 21 (−4), a zyskał 3 i 13.2 (+2). raw zyskał 3 i 19 (+4), a stracił 10 i 21 (−3). Pasuje to do szumu przebiegów rzędu 3–4 pkt.

## Oceny pozycja po pozycji (do porównania z oficjalną oceną)

Kat.: Z = zamknięte, O = otwarte, W = wypracowanie.

| Pozycja | Max | Kat. | `bielik45-base-raw` | `bielik45-harness-v3` | `qwen08-base-raw` | `qwen08-harness-v2-bm25` | `qwen08-harness-v3-bm25` |
|---|---|---|---|---|---|---|---|
| 1 | 1 | O | 1 | 1 | 1 | 1 | 0 |
| 2.1 | 1 | O | 1 | 1 | 0 | 0 | 0 |
| 2.2 | 1 | Z | 0 | 0 | 0 | 0 | 0 |
| 3 | 2 | Z | 2 | 2 | 1 | 1 | 2 |
| 4.1 | 1 | O | 1 | 1 | 0 | 0 | 0 |
| 4.2 | 1 | O | 1 | 1 | 0 | 1 | 1 |
| 5.1 | 1 | O | 1 | 1 | 0 | 0 | 0 |
| 5.2 | 1 | O | 0 | 0 | 0 | 0 | 0 |
| 5.3 | 1 | O | 0 | 0 | 0 | 0 | 0 |
| 6 | 2 | O | 1 | 1 | 0 | 0 | 0 |
| 7 | 2 | O (obraz) | 1 | 1 | 0 | 0 | 0 |
| 8 | 2 | O (obraz) | 0 | 0 | 0 | 0 | 0 |
| 9.1 | 1 | O | 0 | 1 | 0 | 0 | 0 |
| 9.2 | 1 | O | 0 | 1 | 0 | 0 | 0 |
| 9.3 | 1 | O | 1 | 0 | 0 | 0 | 0 |
| 10 | 2 | Z | 0 | 0 | 0 | 0 | 0 |
| 11.1 | 1 | O | 1 | 1 | 0 | 0 | 0 |
| 11.2 | 1 | Z | 1 | 1 | 1 | 1 | 1 |
| 12 | 1 | O | 1 | 1 | 0 | 0 | 0 |
| 13.1 | 1 | O | 0 | 0 | 0 | 0 | 0 |
| 13.2 | 1 | Z | 1 | 1 | 1 | 0 | 1 |
| 14.1 | 1 | O | 0 | 0 | 0 | 0 | 0 |
| 14.2 | 1 | O | 0 | 1 | 0 | 0 | 0 |
| 15 | 1 | O (obraz) | 1 | 0 | 0 | 1 | 1 |
| 16.1 | 1 | O | 0 | 0 | 0 | 0 | 0 |
| 16.2 | 1 | O | 1 | 1 | 0 | 0 | 1 |
| 17 | 1 | O | 0 | 0 | 0 | 0 | 0 |
| 18 | 3 | O | 1 | 1 | 0 | 0 | 0 |
| 19 | 2 | Z | 2 | 0 | 2 | 2 | 2 |
| 20 | 1 | O | 0 | 0 | 0 | 0 | 0 |
| 21 | 2 | Z | 1 | 0 | 2 | 0 | 1 |
| 22 | 1 | O | 1 | 1 | 0 | 0 | 1 |
| 23 | 1 | O | 1 | 1 | 0 | 0 | 0 |
| 24 | 1 | O | 0 | 0 | 0 | 0 | 0 |
| 25.1 | 1 | O | 0 | 0 | 0 | 0 | 0 |
| 25.2 | 1 | O | 1 | 1 | 0 | 0 | 0 |
| 26 | 15 | W | 2 | 6 | 0 | 1 | 1 |
| **razem** | **60** | | **25** | **27** | **8** | **8** | **12** |

Pozycje, których nie trafił żaden system: 2.2, 5.2, 5.3, 8, 10, 13.1, 14.1, 16.1, 17, 20, 24 i 25.1, razem 14 pkt. Dominują w nich rozstrzygnięcia „Tak/Nie” (16.1, 17, 20, 24 i 13.1) oraz interpretacja elementów graficznych (5.3, 8).

## Wypracowania (zadanie 26)

| System | Temat | Słowa | A /12 | B /3 | Razem | Uwagi |
|---|---|---|---|---|---|---|
| `bielik45-base-raw` | 3 | 356 | 0 | 2 | 2 | Forma listy. Dwa z trzech wydarzeń (kryzys kubański, test rakiety) leżą poza latami 50. Korea opisana powierzchownie, są błędy rzeczowe. |
| `bielik45-harness-v3` | 3 | 678 | 4 | 2 | 6 | Korea zadowalająco (3), kryzys berliński 1958 i Algieria powierzchownie (1+1). 2 błędy (−1). Formułowe powtórzenia. |
| `qwen08-base-raw` | 1 | 1044 | 0 | 0 | 0 | Pętla, 4% unikalnych słów. |
| `qwen08-harness-v2-bm25` | 2 | 454 | 0 | 1 | 1 | Ponad 5 błędów rzeczowych, np. zmyśleni władcy i daty. |
| `qwen08-harness-v3-bm25` | 2 | 630 | 0 | 1 | 1 | Ponad 5 błędów rzeczowych. Stanowisko sprzeczne z argumentacją. |

## Werdykty graniczne

Te pozycje najpewniej rozjadą się z oficjalną oceną. Każda to ±1 pkt.

- **`bielik45-harness-v3`:**
  - 9.2 (1): obok przyczyny wykluczonej podaje też poprawną.
  - 18 (1): elementy i kontekst 1917 są poprawne, ale wymowa jest odwrócona w krytykę.
  - 23 (1): istota wyjaśnienia jest poprawna, ale nazwiska są zmyślone.
- **`bielik45-base-raw`:**
  - 18 (1): jak wyżej, do tego błąd faktograficzny w kontekście.
  - 25.1 (0): nazwisko poprawne, ale „choroba” utożsamiona z okresem stanu wojennego. Ocena spójna z raw z 26.09.
  - 26 (2): B = 2 mimo formy listy.
- **`qwen08-base-raw`:**
  - 1 (1): rozstrzygnięcie sformułowane jako „nie paleolit”.
  - 4.2 (0): „prawo lokacyjne” zamiast właściwej nazwy prawa.
- **`qwen08-harness-v2-bm25`:** 1 (1): jak wyżej.
- **`qwen08-harness-v3-bm25`:** 15 (1): cecha stylu podana ogólnikowo.

Surowy egzaminator mógłby dać około −2 pkt dla każdego Bielika. Łagodny oceniający LLM mógłby dać +1–3 pkt, głównie za zadanie 18 i wypracowania.

## Metodyka

- **Ocena ślepa.** Pięć odpowiedzi na pozycję dostało losowe etykiety A–E, a mapowanie zostało w notatniku. Style systemów bywają rozpoznawalne:
  - Bielik raw pisze markdown i wypunktowania.
  - Qwen raw wpada w pętle i wkleja fragmenty promptu.
- **Reguły** są takie same jak w `docs/cke_full_eval.md`:
  - Każda pozycja „wszystko albo nic”, chyba że klucz przewiduje punkty częściowe.
  - P/F: 3/3 → 2 pkt, 2/3 → 1 pkt.
  - Liczy się jawny wybór końcowy.
  - Kilka odpowiedzi naraz albo sprzeczne odpowiedzi → 0.
  - Rozstrzygnięcie bez poprawnego uzasadnienia z odwołaniem do wymaganych źródeł → 0.
  - Wypracowanie: pierwszy temat, poniżej 300 słów B = 0, kary za błędy w A.
- **Zadania z obrazami (7, 8, 15)** oceniałem według zasad CKE z PDF. W pozostałych zadaniach klucz pochodzi z `rubric_text`.
- **Jeden oceniający AI, jeden przebieg.** Szum około ±3 pkt na system.
