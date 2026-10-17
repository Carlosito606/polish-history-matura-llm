# Ocena CKE: harness v3 (`CKE_MODE=1`) na dwóch arkuszach (26.09.2026)

Oceniłem odpowiedzi z `devset/cke_full/answers_harness_v3_{mentor2023,cke2025}.jsonl` tą samą metodą co w `docs/cke_full_eval.md`: rubryka CKE dla każdej pozycji, wypracowanie A 0–12 + B 0–3 z karą za błędy rzeczowe. Arkusze to tekstowy benchmark mentora 2023 (34 pozycje, 55 pkt) i część tekstowa CKE 2025 (24 pozycje, 43 pkt), razem 98 pkt. Wiersze z `system="harness_v3"` dopisałem do `devset/cke_full/grades.jsonl` (58 wierszy; plik jest git-ignored). Dokument nie cytuje treści arkuszy.

v3 działa bez LoRA: adapter jest załadowany, ale każde wywołanie w trybie CKE wysyła skalę 0.

## Wynik

| System | Arkusz | Zamknięte | Otwarte | Wypracowanie | Razem | % |
|---|---|---|---|---|---|---|
| (a) raw | mentor 2023 | 6/11 | 14/29 | 1/15 | 21/55 | 38,2 |
| (b) harness + LoRA | mentor 2023 | 4/11 | 20/29 | 1/15 | 25/55 | 45,5 |
| (c) harness bez LoRA | mentor 2023 | 3/11 | 21/29 | 4/15 | 28/55 | 50,9 |
| **(d) harness v3** | mentor 2023 | 6/11 | 17/29 | 6/15 | **29/55** | **52,7** |
| (a) raw | CKE 2025 | 4/6 | 12/22 | 1/15 | 17/43 | 39,5 |
| (b) harness + LoRA | CKE 2025 | 5/6 | 11/22 | 5/15 | 21/43 | 48,8 |
| (c) harness bez LoRA | CKE 2025 | 4/6 | 10/22 | 5/15 | 19/43 | 44,2 |
| **(d) harness v3** | CKE 2025 | 4/6 | 13/22 | 7/15 | **24/43** | **55,8** |
| (a) raw | razem | 10/17 | 26/51 | 2/30 | 38/98 | 38,8 |
| (b) harness + LoRA | razem | 9/17 | 31/51 | 6/30 | 46/98 | 46,9 |
| (c) harness bez LoRA | razem | 7/17 | 31/51 | 9/30 | 47/98 | 48,0 |
| **(d) harness v3** | **razem** | **10/17** | **30/51** | **13/30** | **53/98** | **54,1** |

Oceny (a)–(c) pochodzą z poprzedniej oceny i nie były zmieniane.

## Zysk względem raw (98 pkt)

| | zamknięte | otwarte | wypracowanie | razem |
|---|---|---|---|---|
| (b) − (a) | −1 | +5 | +4 | +8 (+8,2 pp) |
| (c) − (a) | −3 | +5 | +7 | +9 (+9,2 pp) |
| **(d) − (a)** | **0** | **+4** | **+11** | **+15 (+15,3 pp)** |
| (d) − (b) | +1 | −1 | +7 | +7 |

- **Wypracowanie daje większość zysku.** v3 zdobywa 6 i 7 pkt wobec 1 i 5 dla (b). Oba wypracowania mają po jednym nagłówku, stanowisko, trzy elementy w ramie czasowej tematu i ponad 650 słów. Wynik A wynosi jednak nadal tylko 4/12 na pracę.
- **Zamknięte wracają do poziomu raw (10/17).** Rozumowanie przed odpowiedzią odzyskuje mentor 3 i 21 (+3 pkt). v3 traci natomiast mentor 13.2 i CKE 2025 10 (−2 pkt).
- **Rozstrzygnięcia: 10/15 pkt.** Wynik (b) i (c) to 9/15, raw 7/15. Pole „Rozstrzygnięcie:” ma teraz wariant z polecenia (CKE 2025 2 i 15.2). Nie trzeba więc już łagodnie uznawać gołego „Tak”, jak w poprzedniej ocenie. Uwaga: tryb rozstrzygnięć stroiłem na tych samych arkuszach, więc ten zysk nie jest niezależnym pomiarem.
- **Pozostałe otwarte spadają: 20/36 wobec 22/36 dla (b).** Zyski to mentor 14.1 oraz CKE 2025 1.2 i 4 (przyporządkowanie nazwami, +2). Straty:
  - mentor 18 (rysunek 0–3, **−3**): wymowa odczytana jako pomoc dla rewolucji amerykańskiej, bez kontekstu 1917;
  - mentor 5.2: błędny odczyt tablicy genealogicznej;
  - mentor 9.2: przyczyna dynastyczna, którą podaje już źródło;
  - CKE 2025 9.2: opisowa nazwa zamiast „konfederacja warszawska”.

## Gdzie v3 wciąż traci (45 pkt)

| Typ straty | Pkt | Pozycje |
|---|---|---|
| Wypracowanie (A 4/12 w obu, B 2 i 3) | 17 | mentor 26, CKE 2025 25 |
| Wiedza, identyfikacja i warunek polecenia w krótkich odpowiedziach | 7 | mentor 9.2, 9.3, 25.1; CKE 2025 5.1, 9.2, 9.3, 19 (1 z 2) |
| Zamknięte (P/F z wiedzą, ABCD, tabela) | 6 | mentor 2.2, 3 (1 z 2), 13.2, 19 (2); CKE 2025 10 |
| Rozstrzygnięcia (zły werdykt albo brak wiedzy w uzasadnieniu) | 5 | mentor 17, 20, 24; CKE 2025 11.2, 22 |
| Rysunek i odczyt źródła graficznego lub tablicy | 5 | mentor 18 (3), 5.2, 5.3 |
| Tylko obraz | 3 | CKE 2025 8 (2), 23 |
| Porównania: podobieństwo niepoparte oboma źródłami | 2 | mentor 6, CKE 2025 24.1 |

- **Próg „Tak” ≥ 0,7 działa w obie strony.** Na 8 rozstrzygnięć tak/nie werdykt jest dobry w 5. Mentor 17 (klucz „Tak”) spadł poniżej progu i zmienił się na „Nie”. Mentor 20 i CKE 2025 22 (klucz „Nie”) nadal dostały „Tak”. Oba ostatnie to ta sama pułapka: źródła o podobnym temacie, ale inne zdarzenie lub formacja (Saara 1935 zgodna z Wersalem; armia Andersa, a nie dywizja kościuszkowska).
- **Wypracowania: błędy, które kosztują.**
  - Mentor: dygresja do 1963, „kryzys berliński 1950”, akapit o Berlinie z jednym faktem.
  - CKE 2025: Zygmunt Stary nazwany synem Jagiełły, tylko Grunwald w aspekcie militarnym.
  - Weryfikator nie łapie błędów relacji (pokrewieństwo, przyczyna–skutek), bo sprawdza tylko daty i nazwy.

## Następne 3 poprawki (według oczekiwanego zysku)

1. **Wypracowanie: głębia elementu, nie tylko forma. Oczekiwany zysk: +2–3 pkt na pracę.**
   - Każdy element ma dostać 3–4 datowane fakty z odzyskanych fragmentów, jeden termin i jedno zdanie refleksji wiążące go z tezą. To poziom „zadowalający” (3 pkt), dziś zwykle 1.
   - Odrzucać fakty spoza ramy czasowej także wewnątrz akapitu (Wietnam 1963).
   - Weryfikator rozszerzyć o relacje: pokrewieństwo, „syn/wnuk”, „w wyniku”. Zdanie usunąć, jeśli relacji nie ma w kontekście.
   - Usunąć powtarzane formułki („bezsprzeczne potwierdzenie tezy”). Obniżają B do 2.
2. **Rysunek i źródła graficzne: osobna ścieżka. Oczekiwany zysk: +3 pkt na arkusz z rysunkiem.**
   - Mentor 18 w (b) i (c) dostał 3/3, w v3 0/3. Polecenie „wymowa rysunku… kontekst z roku X” trzeba kierować do szablonu:
     - wymowa;
     - element 1 i element 2 (napisy z opisu);
     - tytuł;
     - „w roku X trwało…” (osobne zapytanie RAG o rok).
   - Tablice genealogiczne (mentor 5.2) czytać deterministycznie z opisu: rodzic → dziecko. Nie wolno pozwolić modelowi zgadywać relacji.
3. **Rozstrzygnięcia „czy to samo zdarzenie/formacja” oraz nazwy historiograficzne. Oczekiwany zysk: +1–2 pkt na arkusz.**
   - Po kroku kto/co/kiedy porównać nazwane byty. Różne nazwy własne albo daty oddalone o ponad 2 lata → „Nie” bez pytania modelu o prawdopodobieństwo (mentor 20, CKE 2025 22).
   - Próg „Tak” stosować tylko wtedy, gdy byty się zgadzają. To odzyskuje mentor 17.
   - Dla „Podaj stosowaną w historiografii nazwę” brać tytuł artykułu Wikipedii z top-1 retrievalu (konfederacja warszawska, noc św. Bartłomieja), a nie parafrazę modelu.
   - Dla „inną niż w źródle” dodać filtr: odrzucić przyczynę, jeśli jej słowa kluczowe występują w źródle (mentor 9.2).

## Metodyka i zastrzeżenia

- **Ocena ślepa, w parach.** Dla każdej pozycji odpowiedź v3 i odpowiedź (b) dostały losowe etykiety X/Y, a mapowanie zostało w notatniku. Wypracowań nie da się w pełni zaślepić (styl nagłówka), a poprawki v3 są znane.
- **Kontrola spójności z poprzednią oceną.** Ponownie oceniona ślepo (b) różni się od starych ocen o −2 pkt na 58 pozycjach: mentor 18 (2 zamiast 3) i CKE 2025 5.2 (0 zamiast 1, goły „Tak”). Obie różnice idą w stronę surowszą. Stare oceny (a)–(c) zostawiłem bez zmian.
- **Werdykty graniczne w v3** mogą przesunąć wynik o ±2–3 pkt:
  - mentor 16.2: „Karl Mark”, uznane;
  - mentor 22: B umieszczone po stronie wschodniej, bez nazwy Układu Warszawskiego, uznane;
  - CKE 2025 1.2: poprawne ogniwo z halucynacjami pobocznymi, uznane;
  - CKE 2025 8: sklepienie wewnątrz nie jest widoczną cechą, 0.
- **Szum:** jeden oceniający AI i jeden przebieg na system, około ±3 pkt na arkusz. Przewaga v3 nad (b) i (c) (+6–7 pkt na 98) wynika głównie z wypracowań. Jest powyżej szumu, ale na dwóch arkuszach, z których jeden był użyty do strojenia.
- **Nie ocenione:** CKE 2024 i 2026 (v3 nie był na nich uruchomiony). To one byłyby niezależnym testem. Pełne porównanie na 186 pkt wymaga dwóch przebiegów v3 na tych arkuszach.
