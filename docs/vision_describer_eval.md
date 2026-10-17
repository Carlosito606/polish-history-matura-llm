# Ocena modeli wizyjnych (opisywacz obrazów), mock CKE 2023

Stan z 26.09.2026. Jedna osoba oceniała 5 kandydatów na 19 obrazach z `data_cke/mock2023/images/`. Dla każdego obrazu kandydaci dostali losowe etykiety A–E, a mapę etykieta→model otworzyłem dopiero po ocenieniu wszystkich 95 opisów. Skrypt i arkusz ocen leżą w scratchpadzie sesji, poza repo.

Każdy opis dostał ocenę 0–10 za cztery rzeczy naraz:
- zgodność z obrazem (zmyślone nazwy, daty i relacje mocno obniżały ocenę),
- kompletność: przepisane napisy, legendy i daty,
- przydatność dla Bielika, który obrazu nie widzi,
- polszczyznę.

Wzorcem był oficjalny opis dla ucznia niewidomego (`image_desc.json`), a tam, gdzie jest tylko podpis, sam obraz.

„Halucynacje” to liczba zmyślonych albo błędnych konkretów, liczona ręcznie: nazwy, napisy, daty, relacje w drzewach, przedmioty. Literówki się nie liczą. Wszystkie przebiegi szły z tym samym promptem (`6ddd83756917` ze `scripts/describe_images.py`), przy temperaturze 0 i limicie 600 tokenów.

## Wyniki

| model | kwantyzacja | GB (z mmproj) | średnia 0–10 | halucynacje | wygrane obrazy* | s/obraz średnio / maks. | szczyt VRAM MiB |
|---|---|---|---|---|---|---|---|
| **Qwen3.5-9B** | Q5_K_M + mmproj F16 | 7.50 | **6.82** | **12** | **14** | 10.6 / 17.6 | 7664 |
| Gemma-4-12B-it QAT | q4_0 + mmproj | 7.15 | 5.97 | 20 | 7 | 13.0 / 21.9 | 9108 |
| Qwen3-VL-8B-Instruct | Q6_K + mmproj F16 | 7.89 | 5.68 | 20 | 2 | 12.0 / 18.2 | 9276 |
| Gemma-4-E4B-it | Q5_K_M + mmproj F16 | 6.47 | 4.95 | 14 | 1 | 6.8 / 14.2 | 5464 |
| Qwen3-VL-4B-Instruct | Q8_0 + mmproj F16 | 5.12 | 4.68 | 28 | 2 | 10.3 / 14.7 | 7006 |

\* Liczba obrazów z najwyższą oceną; remisy liczą się każdemu z remisujących.

Średnie według rodzaju obrazu:

| model | mapy/plany (5) | drzewa genealogiczne (2) | ilustracje/zdjęcia (6) | karykatury/moneta (3) | teksty (3) |
|---|---|---|---|---|---|
| Qwen3.5-9B | **6.3** | **8.0** | 5.5 | **7.2** | **9.2** |
| Gemma-4-12B QAT | 5.3 | 5.5 | **6.0** | 5.7 | 7.7 |
| Qwen3-VL-8B | 4.6 | 7.2 | 4.4 | 6.0 | 8.7 |
| Gemma-4-E4B | 4.7 | 3.0 | 3.8 | 5.2 | 8.7 |
| Qwen3-VL-4B | 3.1 | 3.5 | 3.8 | 6.0 | 8.5 |

## Obserwacje

- **Qwen3.5-9B:**
  - Tylko ten model powiązał bitwy z datami na mapie wojen punickich i przepisał legendę razem z kolorami.
  - Jako jedyny oprócz Qwen3-VL-8B odtworzył drzewo Jagiellonów bez błędu.
  - Poprawnie odczytał napis na monecie.
  - Nie zapętlił się na żadnym obrazie.
  - Słabsze strony:
    - na zdjęciu kościoła zmyślił tablicę z napisem i datą (1928),
    - w drzewie Kapetyngów podał złego rodzica Izabeli,
    - w dwóch planach bitew źle odczytał legendę jazdy,
    - dwojaki na obrazie wziął za instrument.
- **Gemma-4-12B QAT** najlepiej opisuje ilustracje i zdjęcia: kościół, plan miasta, rycinę z wagą, rycinę z kolonii. Kosztem są zmyślone konkrety:
  - rzeka „Dunajec” na planie bitwy,
  - „GAZOWEGO” zamiast napisu z monety,
  - wymyślony adres redakcji gazety,
  - błędy w obu drzewach genealogicznych,
  - pętla powtórzeń na mapie granic II RP („Świnoujście” kilkadziesiąt razy, ocena 1).

  Ma też najwyższe VRAM i czas, a bez `-b 2048 -ub 2048` serwer pada.
- Małe modele (Qwen3-VL-4B, Gemma-4-E4B) dobrze przepisują czysty tekst: gazety, depeszę, nagłówki. Na mapach i w drzewach ich opisy są bezużyteczne albo mylące.
- **Wszystkie modele:**
  - Mapa granic II RP (Z19-S2) okazała się najtrudniejsza. Żaden model nie powiązał obszaru „A” z Warmią i Mazurami, a trzy modele wpadły w pętlę listy miast.
  - Żaden nie nazwał Wuja Sama, czapki frygijskiej ani sutanny.
  - Żaden nie zauważył wieszanych łbów byków w Çatalhöyük.

## Rekomendacja

**Wybór: Qwen3.5-9B, Q5_K_M z mmproj F16** (`unsloth/Qwen3.5-9B-GGUF`, 7.50 GB, apache-2.0).
- Prompt zostaje bez zmian (`6ddd83756917`: system „opis jak w arkuszu 660” plus sam podpis obrazu, bez pytania).
- Parametry wywołania:
  - `enable_thinking=false`,
  - temperatura 0,
  - `max_tokens` podnieść do 800, bo na mapie wojen punickich opis dotarł do limitu,
  - rozważyć `repeat_penalty` 1.05, bo inne modele zapętlały się przy temperaturze 0.
- Serwer: `-c 8192 -np 1 --cache-ram 0 -fa on`, szczyt około 7.7 GB VRAM.
- Opisy: `data_cke/mock2023/image_vlm_qwen35-9b-q5km.json`.

**Drugi wybór: Gemma-4-12B-it QAT q4_0** (`google/gemma-4-12B-it-qat-q4_0-gguf`, 7.15 GB).
- Lepiej radzi sobie z ilustracjami i zdjęciami.
- Ma jednak o 8 halucynacji więcej, zapętla się na gęstych mapach i potrzebuje 9.1 GB VRAM.
- Uruchamiać tylko z `-b 2048 -ub 2048`.

Zastrzeżenia: oceniała jedna osoba, na 19 obrazach, ocenami subiektywnymi. Różnica między 1. a 2. miejscem (0.85 pkt średnio, 14 do 7 wygranych) jest wyraźna, ale nie mierzono jej na punktach za odpowiedzi Bielika. Następny krok to przebieg Bielika na mocku z opisami obu modeli i porównanie zdobytych punktów.
