# Próbny egzamin: ocena panelu trzech niezależnych egzaminatorów Opus 5.5 (26.09.2026)

Pięć plików `submissions/mock/<system>/answers.json` (history-2023-mock-v1, CKE maj 2023, 37 pozycji, 60 pkt) oceniło trzech niezależnych egzaminatorów (Claude Opus 5.5), na ślepo:

- każdy dostał własną losową permutację etykiet S1–S5 i losową kolejność odpowiedzi w każdej pozycji;
- czytali tylko swój pakiet, zasady oceniania CKE 2023 (`data_cke/MHIP-R0-100-2305-zasady.txt`), obrazy i `docs/cke_grading_rules.md`; nie widzieli naszych wcześniejszych ocen;
- wynik systemu = suma median z trzech ocen w każdej pozycji.

Uwaga: te przebiegi dostawały opisy obrazów napisane przez Claude'a (`image_desc.json`). W finale opisów nie będzie (organizatorzy dają same PNG), więc to górna granica. Wersje `-noimg` / `-ocr` liczymy osobno.

## Wynik

| System | Zamknięte /11 | Otwarte /34 | w tym obrazy /5 | Wypracowanie /15 | Razem /60 (mediana) | % | Egzaminatorzy 1/2/3 |
|---|---|---|---|---|---|---|---|
| `bielik45-base-raw` | 7 | 16 | 2 | 1 | **24** | **40,0** | 24 / 24 / 24 |
| `bielik45-harness-v3` | 4 | 17 | 1 | 10 | **31** | **51,7** | 31 / 30 / 27 |
| `qwen08-base-raw` | 7 | 0 | 0 | 0 | 7 | 11,7 | 7 / 7 / 7 |
| `qwen08-harness-v2-bm25` | 4 | 2 | 1 | 1 | 7 | 11,7 | 7 / 7 / 7 |
| `qwen08-harness-v3-bm25` | 7 | 3 | 0 | 1 | 11 | 18,3 | 11 / 10 / 11 |

## Wnioski

- **Przyrost harnessu v3: +7 pkt (+11,7 pp)**, nie +2, jak w pojedynczej ocenie wewnętrznej (`docs/mock_internal_eval.md`). Różnicę robi wypracowanie: panel dał 10 / 10 / 6, pojedynczy oceniający 6.
- **Zgodność egzaminatorów jest bardzo wysoka.** Poza wypracowaniem harnessu v3 i pozycją 9.2 wszystkie 185 ocen są identyczne u całej trójki. Szum oceny dotyczy praktycznie tylko wypracowań.
- **v3 traci na zamkniętych: 4 wobec 7 dla raw.** Pozycje 19 (P/F, 0 wobec 2) i 21 (dwuczęściowy wybór, 0 wobec 1): wyszukiwanie podsuwa artykuł-przynętę. Poprawki v4 (`docs/error_map_v2.md`: osobne wywołania dla podpunktów, zapytanie od identyfikacji źródła, „F tylko z dowodem”) celują dokładnie w te straty. Odzyskanie ich daje około 34–35/60.
- **v3 traci też 15 (obraz) i 9.3; zyskuje 9.1, 14.2 i wypracowanie (+9).**
- **Qwen3.5-0.8B: najwyżej 11/60 (18,3%).** Daleko od progu 35%. Kandydat do „Mały, ale wariat” to Bielik-1.5B-v3 (test trwa).

Oceny pozycja po pozycji: wynik workflow `wf_5ca843a4-7c2` (journal w katalogu sesji), mapowanie etykiet w scratchpadzie. Dokument nie cytuje treści arkusza.

## Warunki finału: bez opisów obrazów i z OCR (drugi panel, 26.09 ~17:00)

Sprostowanie: `image_desc.json` z pierwszej tabeli to nie opisy od Claude'a, tylko oficjalne opisy CKE z arkusza dla niewidomych (660), dopasowane do obrazów. W finale ich nie będzie.

Ten sam panel (3 × Opus 5.5, na ślepo, nowe permutacje etykiet) ocenił cztery przebiegi w warunkach finału: `-noimg` = same symbole `[Obraz: …]`, `-ocr` = tekst odczytany z obrazów przez tesseract (pol), podany jako opis.

| System | Zamknięte /11 | Otwarte /34 | Obrazy /5 | Wypracowanie /15 | Razem /60 | % | Egzaminatorzy 1/2/3 |
|---|---|---|---|---|---|---|---|
| `bielik45-base-raw-noimg` | 7 | 15 | 1 | 2 | **24** | 40,0 | 25 / 24 / 23 |
| `bielik45-base-raw-ocr` | 7 | 18 | 1 | 0 | **25** | 41,7 | 25 / 25 / 25 |
| `bielik45-harness-v3-noimg` | 2 | 15 | 1 | 6 | **23** | 38,3 | 24 / 22 / 23 |
| `bielik45-harness-v3-ocr` | 7 | 19 | 2 | 4 | **30** | 50,0 | 31 / 30 / 30 |

- **Szum przebiegów jest duży.** Pozycje bez obrazów mają identyczne wejście w `-noimg` i `-ocr`, a mimo to v3 ma na nich różne wyniki (np. 10: 0 wobec 2 pkt, 22: 0 wobec 1). Zajęty serwer z wieloma równoległymi slotami daje różne odpowiedzi nawet przy temperaturze 0. Pojedynczy przebieg waha się o około ±4 pkt, więc różnic poniżej ~5 pkt nie da się rozstrzygnąć na jednym arkuszu.
- **Najlepszy pojedynczy przebieg w warunkach finału: `bielik45-harness-v3-ocr`, 30/60**, wobec bazy `bielik45-base-raw-noimg` 24/60 (+6).
- **Zamknięte v3 są niestabilne (2–7/11), raw stabilny (7/11).** Poprawki v4 (głosowanie, osobne podpunkty, identyfikacja źródła) celują w to.
- **Wypracowanie v3: 4–10 pkt w zależności od przebiegu.** W `-ocr` zakończenie urwało się w pół zdania (limit 240 tokenów); egzaminatorzy odjęli za to B. Poprawione 26.09 ~17:10 w `harness/cke_flow.py`: limit zakończenia 360 i obcinanie urwanego ostatniego zdania każdego akapitu.
- **Do wysłania organizatorom (kalibracja):** `bielik45-harness-v3-ocr` (planowana konfiguracja finału) i `bielik45-base-raw-noimg` (baza do przyrostu).
