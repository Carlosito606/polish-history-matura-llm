# Konfiguracja finału (decyzja zespołu, 26.09.2026 ~20:40)

**System „progress”: Bielik-4.5B-v3 Q8_0 (zarejestrowana baza, bez LoRA) w trybie hybrydowym + Qwen3.5-9B jako opisywacz obrazów.**

| Element | Ustawienie |
|---|---|
| Model odpowiadający | Bielik-4.5B-v3.0-Instruct Q8_0, sha256 `562f2291…1b7f`, bez adaptera |
| Zadania krótkie (zamknięte, otwarte, rozstrzygnięcia) | surowy Bielik (`exam_runner --mode hybrid` → tryb raw), temperatura 0 |
| Wypracowanie (zadanie 26) | harness v3 (`CKE_MODE=1 QTYPE_V2=1 RERANK=1`): plan, retrieval z Wikipedii na każdy element, akapity, zakończenie, weryfikacja faktów |
| Obrazy | Qwen3.5-9B Q5_K_M + mmproj F16 (≤ 8 GB), prompt „literal” (tylko to, co widać; litery/strzałki/legenda; napisy dosłownie; „nieczytelne” zamiast zgadywania), max 800 tokenów; opis trafia do promptu z dopiskiem „automatyczny, może zawierać błędy”, nie trafia do zapytań wyszukiwarki |
| OCR | brak (decyzja zespołu) |
| Serwer | llama.cpp b11185, `-np 1`, `--cache-ram 0`; model wizyjny uruchamiany przed Bielikiem i wyłączany po opisaniu obrazów |
| Uruchomienie | `scripts/run_final.sh PKG_DIR [OUT_DIR]` (całość offline, na jednej maszynie) |

## Dlaczego hybryda

Na arkuszach, których nie używaliśmy do strojenia (CKE 2024 i 2026, 88 pkt; ocena rubryką CKE, `devset/cke_full/grades.jsonl`):

| System | zamknięte /11 | otwarte /47 | wypracowanie /30 | razem |
|---|---|---|---|---|
| surowy Bielik (baza) | 5 | **25** | 4 | 34 |
| harness v3 | 5 | 20 | **9** | 34 |
| harness v3 + LoRA v3 | 4 | 21 | 7 | 32 |
| **hybryda (szacunek z tych samych ocen)** | 5 | 25 | 9 | **39** |

- Harness pomaga tylko przy wypracowaniu. Na czterech arkuszach (2023–2026) wypracowania harnessu mają 22 pkt, surowego Bielika 6.
- Na zadaniach krótkich harness na nowych arkuszach nie pomaga (zamknięte) albo szkodzi (otwarte); zysk na arkuszach 2023 i 2025 wynikał ze strojenia na nich.
- LoRA v3 (RFT na własnych poprawnych rozumowaniach, `docs/cke_v3_lora_eval.md`) nie poprawia wyniku: 32 wobec 34 na odłożonych arkuszach. Zostaje poza finałem.
- Harness v4 (`harness/README.md`, flagi `V4_*`) poprawia ABCD, psuje P/F; na pełnych arkuszach nieoceniony. Poza finałem.
- Model wizyjny: wybór na ślepo spośród 5 kandydatów (`docs/vision_describer_eval.md`). Na próbnym egzaminie z harnessem v3 domyślne opisy wypadły gorzej niż OCR na zadaniach z obrazami (8 wobec 13 pkt z 31). Poprawki (prompt „literal”, dopisek o błędach, opis poza wyszukiwarką) nie zostały ocenione rubryką, bo zespół zdecydował o oszczędzaniu tokenów. Nawet oficjalne opisy CKE (arkusz 660) dawały surowemu Bielikowi tylko +1–2 pkt.

## Ryzyka

- Pojedynczy przebieg na zajętym serwerze waha się o ±4 pkt; finał idzie na wolnym GPU z `-np 1`.
- Oczekiwany przyrost nad bazą na nowym arkuszu: ok. +5 pkt (wypracowanie), niepewność kilka punktów.
