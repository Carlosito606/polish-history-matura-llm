# Ocena CKE: harness v3 + LoRA v3 (26.09.2026, wieczór)

Sprawdziłem, czy adapter LoRA v3 (`bielik45-v3-r16-e2`, SFT z RFT i przykładowych odpowiedzi CKE) poprawia wynik harnessu v3 na pełnych arkuszach. **Nie poprawia.** Na arkuszach odłożonych (CKE 2024 i 2026) wynik z LoRA jest o 2 pkt niższy niż bez niej. Na pozycjach, na których adapter w ogóle działa (wszystko poza wypracowaniem), różnica wynosi +2 pkt na 126, czyli mieści się w szumie. Próbny egzamin: 27/60 z LoRA i 27/60 bez niej.

Oceny pozycja po pozycji są w `devset/cke_full/grades.jsonl`. Dokument nie cytuje treści arkuszy.

## Konfiguracja

- **Model:** Bielik-4.5B-v3 Q8_0 (zarejestrowany GGUF, bez zmian) + `--lora bielik45-v3-r16-e2.gguf` (sha256 `232bdd8f…1daee`, zgodny z raportem treningu).
- **Harness v3:** `CKE_MODE=1 QTYPE_V2=1 RERANK=1 DENSE=0`, reranker współdzielony na :18092.
- **Włączanie LoRA:** `CKE_LORA_TYPES=abcd,abj,pf,match,abcd_parts,chrono,open,generic,explain`. Adapter działa ze skalą 1 dla wszystkich typów poza `essay`. Wypracowanie idzie ze skalą 0, tak samo jak w v3 bez LoRA.
- **Uruchomienie:** L40S, kopia robocza `/scratch/lora3eval/wmt-matura` (kod harnessu identyczny z laptopem, zgodność md5). llama-server :18083 z `--cache-ram 0`, harness :18003.
  - Cztery arkusze i próbny egzamin wygenerowały się w 12 minut (20:03–20:15).
  - Serwery zatrzymane po zakończeniu.
- **Porównanie bez LoRA:** `answers_harness_v3_cke2024/2026.jsonl` już istniały, więc nie uruchamiałem v3 ponownie. Oceniłem je teraz po raz pierwszy (system `harness_v3`, 55 wierszy).

## Wynik

Kolumny: zamknięte / otwarte / wypracowanie, potem razem. Dane (a)–(c) pochodzą z `docs/cke_full_eval.md` i `docs/cke_v3_eval.md`, (c) na arkuszach 2024 i 2026 oraz (d) oceniłem teraz.

### Arkusze odłożone (v3 nie był na nich strojony): CKE 2024 i CKE 2026

| System | CKE 2024 (47) | CKE 2026 (41) | Razem (88) | % |
|---|---|---|---|---|
| (a) raw | 2/14/2 = 18 | 3/11/2 = 16 | 34 | 38,6 |
| (b) harness_lora (v1) | 2/13/3 = 18 | 2/9/6 = 17 | 35 | 39,8 |
| (c) harness_v3 bez LoRA | 2/11/3 = 16 | 3/9/6 = 18 | 34 | 38,6 |
| **(d) harness_v3 + LoRA v3** | **1/10/3 = 14** | **3/11/4 = 18** | **32** | **36,4** |

### Arkusze strojenia v3: benchmark mentora 2023 i CKE 2025

| System | mentor 2023 (55) | CKE 2025 (43) | Razem (98) | % |
|---|---|---|---|---|
| (a) raw | 6/14/1 = 21 | 4/12/1 = 17 | 38 | 38,8 |
| (b) harness_lora (v1) | 4/20/1 = 25 | 5/11/5 = 21 | 46 | 46,9 |
| (c) harness_v3 bez LoRA | 6/17/6 = 29 | 4/13/7 = 24 | 53 | 54,1 |
| **(d) harness_v3 + LoRA v3** | **6/18/3 = 27** | **3/15/7 = 25** | **52** | **53,1** |

### Wszystkie cztery arkusze (186 pkt)

| System | Zamknięte /28 | Otwarte /98 | Wypracowanie /60 | Razem | % |
|---|---|---|---|---|---|
| (a) raw | 15 | 51 | 6 | 72 | 38,7 |
| (b) harness_lora (v1) | 13 | 53 | 15 | 81 | 43,5 |
| (c) harness_v3 bez LoRA | 15 | 50 | 22 | 87 | 46,8 |
| **(d) harness_v3 + LoRA v3** | **13** | **54** | **17** | **84** | **45,2** |

## Zysk względem raw

| | odłożone (88) | strojenie (98) | razem (186) |
|---|---|---|---|
| (b) − (a) | +1 | +8 | +9 |
| (c) − (a) | 0 | +15 | +15 |
| **(d) − (a)** | **−2** | **+14** | **+12** |
| (d) − (c) | −2 | −1 | −3 |

**Bez wypracowań (126 pkt), czyli tam, gdzie adapter działa:**

| | odłożone (58) | strojenie (68) | razem (126) |
|---|---|---|---|
| (a) raw | 30 | 36 | 66 |
| (b) harness_lora | 26 | 40 | 66 |
| (c) harness_v3 | 25 | 40 | 65 |
| (d) harness_v3 + LoRA v3 | 25 | 42 | 67 |

- **Harness v3 nie przenosi się na arkusze odłożone.** Na CKE 2024 i 2026 ma 34 pkt, tyle samo co raw. Całe +15 pkt v3 pochodzi z arkuszy, na których był strojony, i z wypracowań. Bez wypracowań v3 na arkuszach odłożonych przegrywa z raw 25 do 30.
- **LoRA v3 przestawia odpowiedzi, ale nie podnosi wyniku.**
  - Na 126 pkt zmieniły się oceny 23 pozycji w obie strony, netto +2 (0 na odłożonych, +2 na strojeniu).
  - Zamknięte: −2 (13 wobec 15). Otwarte: +4.
- **Różnica w wypracowaniach (17 wobec 22) to szum, a nie efekt LoRA.** W obu systemach wypracowanie idzie ze skalą 0. Wynik zmienia się między przebiegami, bo tryb wypracowania generuje z próbkowaniem: mentor 3 wobec 6, CKE 2026 4 wobec 6, pozostałe dwa bez zmian. To rozrzut do ±3 pkt na pracę.

## Próbny egzamin (mock2023, pełny arkusz, 60 pkt)

`submissions/mock/bielik45-harness-v3-lora3/answers.json` (+ `debug.jsonl`): ten sam pakiet i te same flagi co w `scripts/l40s_run_mock.sh`, `--image-desc data_cke/mock2023/image_desc.json`. Walidacja `harness.exam_runner --validate`: **VALID**.

| System | Zamknięte /11 | Otwarte /34 | w tym obrazy /5 | Wypracowanie /15 | Razem /60 | % |
|---|---|---|---|---|---|---|
| `bielik45-base-raw` | 7 | 16 | 2 | 2 | 25 | 41,7 |
| `bielik45-harness-v3` | 4 | 17 | 1 | 6 | 27 | 45,0 |
| **`bielik45-harness-v3-lora3`** | **4** | **17** | **1** | **6** | **27** | **45,0** |

Zmiany LoRA względem v3 znoszą się (+3 / −3):

- zyski: 5.2 (wygaśnięcie Kapetyngów), 15 (realizm), 21 (1 z 2);
- straty: 3 (P/F 2/3 zamiast 3/3), 7 (drugi styl bez cechy), 9.2 (tylko przyczyna dynastyczna).

Oceny zapisane jako `mock_bielik45-harness-v3-lora3` / `mock2023` (37 wierszy).

## Pozycje, na których LoRA zmieniła ocenę (d − c, bez wypracowań)

| Arkusz | Zyski | Straty |
|---|---|---|
| CKE 2024 | 15.1 (+1, v3 ucięło odpowiedź do „Pow”), 23.1 (+1) | 6 (−1), 10 (−1, ABCD), 17.1 (−1, odwrócony związek przyczynowy), 22.2 (−1) |
| CKE 2026 | 5.1, 10.1, 17, 22 (po +1; 22 to dobre „Nie” zamiast „Tak”) | 2 (−1, P/F), 9 (−1) |
| mentor 2023 | 5.3, 9.2, 13.2, 19 (po +1) | 16.1 (−1, „Nie” przy kluczu „Tak”), 21 (−2, obie litery złe) |
| CKE 2025 | 8, 10, 11.2 (po +1) | 15.1 (−1, P/F), 17.2 (−1, ABCD) |

Nie widać wzorca, który dawałby się przypisać adapterowi. Zmiany wyglądają jak losowe przesunięcia w obie strony. Uwaga z raportu treningu pasuje do tego obrazu: wiersze RFT próbkowano bez początku „Rozumowanie:”, który harness dopisuje w ścieżkach zamkniętej i otwartej. Model w treningu widział więc inny początek odpowiedzi niż przy użyciu.

## Gdzie (d) wciąż traci (102 pkt z 186)

| Typ straty | Pkt | Pozycje (przykłady) |
|---|---|---|
| Wypracowanie: A 2–4/12, B 1–3 | 43 | wszystkie cztery prace; mentor 2023 A2/B1 (odprężenie 1955–57 jako „dowód apogeum”, 5 błędów dat) |
| Czytanie źródła lub grafiki, wyjaśnienia, porównania | 17 | 2024: 4, 6, 17.1, 22.2; 2026: 5.2, 9, 11; mentor: 5.2, 6, 18 (3 pkt); 2025: 8, 23, 24.1 |
| Zamknięte (ABCD, P/F, przyporządkowanie) | 15 | 2024: 10, 11.1, 16.2, 20.2; 2026: 2, 3.2, 15.2; mentor: 2.2, 3, 19, 21; 2025: 5.1, 15.1, 17.2 |
| Wiedza i identyfikacja (nazwa dokumentu, postać, państwo zamiast miasta) | 14 | 2024: 3.1, 3.2, 5.2, 8.1, 11.2, 12.1 (ucięte); 2026: 12.1, 16.2, 21; mentor: 9.3, 25.1; 2025: 9.2, 9.3, 19 |
| Rozstrzygnięcia: zły werdykt albo uzasadnienie na błędnej dacie | 13 | 2024: 2, 7, 8.2, 9, 12.3; 2026: 6.2, 14.2, 23.1; mentor: 16.1, 17, 20, 24; 2025: 22 |

- **Werdykty tak/nie mylą się w obie strony.** Z 13 strat w rozstrzygnięciach siedem to zły werdykt tak/nie:
  - cztery razy „Nie” przy kluczu „Tak”: 2024 8.2, 2026 14.2, mentor 16.1 i 17;
  - trzy razy „Tak” przy kluczu „Nie”: 2026 23.1, mentor 20, 2025 22.
  - Skrzywienie na „Tak” z v1 zniknęło, ale próg P(Tak) ≥ 0,7 odrzuca teraz także poprawne „Tak”.
- **Wypracowanie to nadal 42% strat.** Rozrzut między przebiegami sięga ±3 pkt na pracę. Przy jednym przebiegu na egzaminie wynik wypracowania jest w dużej mierze kwestią losowania.

## Wnioski

1. **LoRA v3 nie daje mierzalnego zysku.** Na odłożonych: −2 pkt ogółem i 0 bez wypracowań. Próbny egzamin bez zmian (27/60). Włączenie adaptera nie szkodzi ponad szum, ale nie ma czego nim uzasadnić.
2. **Zysk harnessu v3 nad raw jest widoczny tylko na arkuszach strojenia.** Na CKE 2024 i 2026 v3 = raw (34/88). Uczciwa liczba „gain” to około 0 pkt na odłożonych i około +2 pkt na próbnym. +15 pkt na czterech arkuszach jest zawyżone przez strojenie.
3. **Jeśli ma być jeszcze jedna iteracja LoRA:**
   - dane SFT z dokładnie takim początkiem odpowiedzi, jaki wysyła harness („Rozumowanie:”);
   - ocena najpierw na samych pozycjach zamkniętych i rozstrzygnięciach arkuszy odłożonych, bo tam jest sygnał.
   - Cykl: trening około 80 min + generacja 12 min + ocena około 30 min.
4. **Największa dźwignia bez treningu leży w harnessie, nie w wagach:**
   - wypracowanie generuje dziś z temperaturą 0,3; pomogłaby temperatura 0 albo wybór najlepszej z kilku wersji weryfikatorem;
   - rozstrzygnięcia tak/nie potrzebują innego progu „Tak”.

## Metodyka i zastrzeżenia

- **Ocena ślepa, w parach.** Dla każdej pozycji odpowiedź (d) i odpowiedź (c) dostały losowe etykiety X/Y (ziarno per arkusz), a mapowanie zostało w notatniku. Wypracowań nie da się w pełni zaślepić.
- **Reguły** jak w `docs/cke_full_eval.md` i `docs/cke_grading_rules.md`: rubryka CKE, P/F 3/3 → 2 i 2/3 → 1, rozstrzygnięcie bez poprawnego uzasadnienia = 0, kary za błędy w wypracowaniu −1/−2/−3. Pozycje graniczne oceniałem tak jak w poprzednich ocenach tych samych pozycji.
- **Kontrola spójności:** (c) na mentor 2023, CKE 2025 i próbnym oceniłem ponownie ślepo, obok (d).
  - Mentor 2023 i próbny: 0 różnic wobec starych ocen na 71 pozycjach.
  - CKE 2025: jedna różnica (wypracowanie 6 zamiast 7).
  - Do tabel wziąłem stare oceny (c). Ponownej oceny nie dopisywałem do `grades.jsonl`.
- **Szum:** jeden oceniający AI i jeden przebieg na system, około ±3 pkt na arkusz, głównie przez wypracowanie. Różnica (d) − (c) = −3 na 186 pkt jest poniżej szumu.

## Pliki

- `devset/cke_full/answers_harness_v3_lora3_{cke2024,cke2026,mentor2023,cke2025}.jsonl`: odpowiedzi (d), 113 pozycji, 0 błędów.
- `devset/cke_full/grades.jsonl`: dopisane 205 wierszy:
  - `harness_v3_lora3` (113);
  - `harness_v3` dla cke2024 i cke2026 (55);
  - `mock_bielik45-harness-v3-lora3` (37).
- `submissions/mock/bielik45-harness-v3-lora3/answers.json` + `debug.jsonl` (VALID).
- Skrypt uruchomienia na L40S: `/scratch/lora3eval/run.sh` (`up | papers | mock | down`).
