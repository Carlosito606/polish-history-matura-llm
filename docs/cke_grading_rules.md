# CKE grading rules: history matura, extended level (May 2023)

Sources (copyrighted CKE material; local copies live only in the git-ignored `data_cke/`):

- Exam paper: [MHIP-R0-100-2305.pdf](https://cke.gov.pl/images/_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2023/Historia/MHIP-R0-100-2305.pdf) (18 May 2023, 180 min, 60 pts, tasks 1–26, 37 scored items)
- Marking rules: [MHIP-R0-100-2305-zasady.pdf](https://cke.gov.pl/images/_EGZAMIN_MATURALNY_OD_2023/Arkusze_egzaminacyjne/2023/Historia/MHIP-R0-100-2305-zasady.pdf) (published 28 June 2023)
- Mentor benchmark that uses this paper: <https://warsaw-matura-method.ania-olchowik.chatgpt.site/> (`methodology.md`, `astra-descriptions.exam.json`)

This document quotes only the scoring rules and short answer keys. It does not reproduce exam sources.

## 1. How the mentor benchmark uses this paper

This section matters most for us, because it is how we will actually be scored on this paper.

- **Text-only track (our case):** 34 scored items worth 55 pts. Tasks 7, 8 and 15 are removed (architecture photo, Reformation engraving, painting). Every other image is replaced by a frozen Polish description. The descriptions transcribe scanned text, keep tables as data and keep family-tree relationships. They add no solutions or interpretations. Each subtask is sent separately, with all the sources of its task group, sources first and then the original CKE command. The system instruction is: *„Rozwiąż zadanie z historii po polsku. Otrzymujesz tekst źródeł, a obrazy zastąpiono opisami. Wykorzystaj źródła i własną wiedzę zgodnie z poleceniem. Udziel tylko odpowiedzi na podane zadanie. Nie dopisuj innych zadań. Nie masz dostępu do narzędzi ani internetu.”*
- **Point split:** closed items 11 pts, other open items 29 pts, essay 15 pts. Closed items are checked deterministically only when the answer is unambiguous; unparseable formatting goes to review instead of an automatic zero. Open items and the essay are graded by an AI against the CKE rubric, accepting valid alternatives to the sample wording. No human review is planned.
- **Only the final answer is graded.** For thinking models, only the text after `</think>` counts. If the thinking budget runs out before a final answer, the item scores 0. An empty answer scores 0, and an answer to a different question on the same page gets no credit.
- **Token budgets (v0.2):** short items get 8192 thinking tokens plus 2048 answer tokens. The essay gets 16384 plus 4096. A truncated answer is graded as produced.
- **Reported subsets:** the "original text-only" subset is task groups 2, 6, 11, 12, 16, 22, 23, 25 and 26 (13 items, 28 pts). Adding task 10's table gives 14 items and 30 pts.
- **Essay with several topics:** only the first explicitly selected topic is assessed.
- The event site still says the contest questions are generated from Wikipedia. The real-paper benchmark does not replace that commitment, so we should expect both styles.

## 2. General rules in the 2023 documents

- Zasady, page 2: **„Uwaga: Akceptowane są wszystkie odpowiedzi merytorycznie poprawne i spełniające warunki zadania.”** A correct answer in other words scores. An answer that ignores a condition of the command, such as "use both sources", does not.
- Exam instruction 3: *„Zapoznaj się uważnie ze źródłami, a następnie wykonaj zadania umieszczone pod nimi. Odpowiadaj tylko na podstawie źródeł i tylko własnymi słowami – chyba że w zadaniu polecono inaczej. Udzielaj tylu odpowiedzi, o ile Cię poproszono.”* So we give exactly as many answers as requested, and we write in our own words, not by copying the source.
- **Every item is all-or-nothing** unless its rule lists partial scores. Two different zero-point clauses appear:
  - short identification and closed items: *„0 pkt – za odpowiedź błędną albo za brak odpowiedzi”*;
  - decision, explanation and multi-element items: *„0 pkt – za odpowiedź niepełną lub błędną albo za brak odpowiedzi”*. An incomplete answer is worth exactly as much as a wrong one.
- **Surplus or contradictory answers:** the 2023 zasady have **no explicit rule** for them. The only textual basis is „Udzielaj tylu odpowiedzi, o ile Cię poproszono”. CKE practice elsewhere is that a surplus or mutually contradictory answer is treated as wrong. We did not verify that in these two PDFs, so treat any hedging ("A lub C", two names where one was asked) as a likely zero.
- **Key notation:** square brackets mark optional or alternative parts, and commas separate accepted variants. Examples: `[Ignacy] Łukasiewicz` means the surname alone is enough, `Hanza [hanza niemiecka, związek hanzeatycki]`, `Zygmunt III [Waza], Zygmunt Waza`, `Zabór austriacki [Galicja]`, `[Fryderyk] Engels, [Karol] Marks`.
- **Spelling of names and dates:** the zasady contain **no explicit rule** on spelling, first-name/surname order, or dates with or without an era. Observed practice:
  - For „Podaj nazwisko”, the surname is enough and a first name is optional.
  - For „Podaj imię władcy”, the key requires the ordinal or the dynasty (`Zygmunt III` / `Zygmunt Waza`). A bare „Zygmunt” is ambiguous and is not in the key.
  - No 2023 item asks for a date. The exam writes ancient dates with „p.n.e.” (e.g. „264 p.n.e.”). The essay rules count wrong dating as a factual error.
  - Our reading: always add „p.n.e.” to BCE dates, and give the full standard name form, with first name and ordinal for rulers.

## 3. Rules by task type (with every 2023 instance)

| Type | CKE command phrasing | Official rule (verbatim) | Answer form in the key | 2023 items |
|---|---|---|---|---|
| **Single choice (ABCD)** | „Dokończ zdanie. Zaznacz właściwą odpowiedź spośród podanych.” | „1 pkt – za prawidłową odpowiedź. 0 pkt – za odpowiedź błędną albo za brak odpowiedzi.” | one letter: `C` | 11.2 (C), 13.2 (C) |
| **Two choices in one item** | „Dokończ zdania 1. i 2. Zaznacz właściwą odpowiedź spośród podanych.” | „2 pkt – za dwie prawidłowe odpowiedzi. 1 pkt – za jedną prawidłową odpowiedź. 0 pkt – za odpowiedź błędną albo za brak odpowiedzi.” | `1 – B`, `2 – C` | 21 (1–B, 2–C) |
| **True/false (P/F), 3 statements** | „Oceń prawdziwość poniższych stwierdzeń. Zaznacz P, jeśli stwierdzenie jest prawdziwe, albo F – jeśli jest fałszywe.” | „2 pkt – odpowiedź zawierająca trzy prawidłowe wskazania. 1 pkt – odpowiedź zawierająca dwa prawidłowe wskazania. 0 pkt – odpowiedź niepoprawna lub niepełna albo brak odpowiedzi.” | `1 – F`, `2 – P`, `3 – P` | 3 (F,P,P), 10 (P,F,P), 19 (F,P,F) |
| **Matching / table fill** | „Na podstawie tekstów i własnej wiedzy uzupełnij tabelę – obok opisu wpisz numer fragmentu tekstu …” | „1 pkt – za dwa prawidłowe wskazania. 0 pkt – za odpowiedź niepełną lub błędną albo za brak odpowiedzi.” (both pairs or nothing) | `A – 3`, `B – 2` (description letter → fragment number) | 2.2 |
| **Ordering / chronology** | — | **No ordering task in the 2023 paper.** Chronology is tested through P/F statements (10, 19) and a before/after choice (13.2: „Do bitwy … doszło A. przed … C. po …”). | — | — |
| **Short identification** | „Podaj stosowaną w historiografii nazwę …”, „Podaj nazwisko …”, „Podaj imię władcy …”, „Podaj nazwę zaboru …”, „Podaj nazwisko jednego z autorów …” | „1 pkt – za podanie prawidłowej nazwy / prawidłowego nazwiska / prawidłowego imienia władcy. 0 pkt – za odpowiedź błędną albo za brak odpowiedzi.” | bare term: `Hanza`, `Wojna stuletnia`, `Zygmunt III [Waza]`, `[Ignacy] Łukasiewicz`, `Zabór austriacki [Galicja]`, `[Karol] Marks` | 4.1, 5.1, 9.1, 14.1, 14.2, 16.2 |
| **Name + explanation** | „Podaj nazwisko polityka A i wyjaśnij, … W odpowiedzi odwołaj się do faktografii.” | „1 pkt – za podanie prawidłowego nazwiska wraz z wyjaśnieniem zawierającym odwołanie do faktografii.” | `Nazwisko: [Leonid] Breżniew` + explanation (Solidarność strikes); `[Wojciech] Jaruzelski` + martial law | 25.1, 25.2 |
| **Name + feature** (image) | „Podaj nazwy dwóch stylów … oraz po jednej widocznej … cesze”; „Podaj nazwę stylu … Odpowiedź uzasadnij, podając jedną widoczną … cechę” | 7: „2 pkt – za podanie dwóch prawidłowych nazw stylów i po jednej cesze każdego z nich. 1 pkt – za podanie jednej prawidłowej nazwy stylu i jego cechy albo za podanie dwóch prawidłowych nazw stylów.” 15: „1 pkt – za podanie prawidłowej nazwy i jednej cechy stylu.” | gotycki + renesansowy; realizm | 7, 15 (not in text track) |
| **Decision + justification** | „Rozstrzygnij, czy … Odpowiedź uzasadnij, odwołując się do [ilustracji i własnej wiedzy / informacji z tego fragmentu / informacji z obu źródeł / treści obu źródeł / treści obu traktatów i własnej wiedzy].” | „1 pkt – za prawidłowe rozstrzygnięcie wraz z uzasadnieniem zawierającym odwołanie do [ilustracji / informacji z tekstu / informacji z obu źródeł / obu źródeł].” 13.1 adds: „… zawierającym nazwę bitwy oraz odwołanie do informacji zawartych w obu źródłach.” 12: „… wraz z uzasadnieniem.” | `Rozstrzygnięcie: …` + `Uzasadnienie: …`. Keys: 1 neolitu, 2.1 Fragment 2., 4.2 Tak, 12 Nie, 13.1 B, 16.1 Tak, 17 Tak, 20 Nie, 22 Nie, 24 Nie | 1, 2.1, 4.2, 12, 13.1, 16.1, 17, 20, 22, 24 |
| **Explanation** | „Wyjaśnij, odwołując się do źródła 2., w jakich okolicznościach …”, „Wyjaśnij, na czym polegało …”, „Wyjaśnij różnicę między …”, „Wyjaśnij, dlaczego …” | „1 pkt – za prawidłowe wyjaśnienie [zawierające odwołanie do tablicy genealogicznej / ilustracji].” | 1–2 sentences of cause and effect with facts | 5.2, 5.3, 9.3, 11.1, 23 |
| **Cause** | „Przedstaw inną – niż wspomniane w źródle 1. – przyczynę …” | „1 pkt – za przedstawienie prawidłowej przyczyny.” | a cause **not** named in the source (Baltic dominium / Inflanty) | 9.2 |
| **Comparison** | „Porównaj … opinie historyków … Przedstaw jedno podobieństwo i jedną różnicę między nimi.” | „2 pkt – za przedstawienie jednego podobieństwa i jednej różnicy między opiniami. 1 pkt – za przedstawienie jednego podobieństwa albo jednej różnicy …” | `Podobieństwo: …` / `Różnica: …` | 6 |
| **Arguments** (image) | „Sformułuj dwa argumenty potwierdzające tezę, że …” | „2 pkt – za sformułowanie dwóch prawidłowych argumentów. 1 pkt – za sformułowanie jednego …” | two bullets | 8 (not in text track) |
| **Cartoon interpretation (0–3)** | „Wyjaśnij wymowę rysunku, interpretując jego dwa elementy graficzne i tytuł. W odpowiedzi uwzględnij kontekst historyczny z roku powstania tego rysunku.” | 3 pkt: meaning + two graphic elements **and** title + 1917 context. 2 pkt: meaning + two elements **or** title + 1917 context. 1 pkt: meaning + two elements or title, without context. 0 pkt: wrong or none. | one paragraph | 18 |
| **Essay (0–15)** | „Zadanie zawiera trzy tematy. Wybierz jeden z nich do opracowania. Twoja wypowiedź powinna liczyć minimum 300 wyrazów.” Each topic: „Zajmij stanowisko wobec powyższej tezy i je uzasadnij, uwzględniając w swojej argumentacji [trzy wybrane …].” | see below | `WYPRACOWANIE na temat nr …` | 26 |

### Essay (task 26) in detail

- **A. Narracja historyczna (0–12).** The rubric crosses two things: how functionally the knowledge serves each of the **three elements** of the topic (fully functional, partially functional, not functional), and how rich the argumentation is per element.
  - A **rich** element is worth 4 pts, a **satisfactory** one 3 pts and a **superficial** one 1 pt. So 12 = rich × 3, 9 = satisfactory × 3 and 3 = superficial × 3.
  - If the knowledge is not used functionally anywhere, or there is no text, the essay gets 0.
  - The writer **must take a stance on the thesis** and argue it. „Bezrefleksyjne referowanie” (dumping everything one knows without reference to the thesis), or argumentation that contradicts one's own stance, counts as non-functional.
  - Rich argumentation means „rzeczowa, pogłębiona, poparta trafnie dobraną i szczegółową faktografią oraz adekwatną … terminologią”.
- **Factual-error deductions in A** (never below 0): 1–2 errors −1, 3–5 errors −2, more than 5 errors −3. An error is an evident mistake of chronology (wrong century or period), terminology, or cause and effect.
- **B. Spójność (0–3).**
  - 3 pts: at least 300 words and coherent.
  - 2 pts: at least 300 words with minor coherence problems.
  - 1 pt: at least 300 words with major coherence problems.
  - 0 pts: under 300 words, or a set of loose elements.
  - Coherent means intro, body and conclusion form one logical whole, and each paragraph follows from the previous one. Things that break coherence: conclusions that do not follow, off-topic threads, digressions, interleaved threads, skipped reasoning steps, filler sentences.
- The 2023 topics were: (1) decentralisation in 11th–12th-century Poland, three rulers; (2) causes of the American and French revolutions, political, socio-economic and cultural aspects; (3) the Cold War's apogee in the 1950s, three events.

## 4. Official instruction phrasings used in the 2023 paper

- Decision: „Rozstrzygnij, czy …” / „Rozstrzygnij, który z fragmentów 1–3 …” / „Rozstrzygnij, na którym z planów … (A czy B) …”. Followed by „Odpowiedź uzasadnij, odwołując się do …” or „W uzasadnieniu podaj nazwę bitwy i odwołaj się do informacji zawartych w obu źródłach.”
- True/false: „Oceń prawdziwość poniższych stwierdzeń. Zaznacz P, jeśli stwierdzenie jest prawdziwe, albo F – jeśli jest fałszywe.”
- Choice: „Dokończ zdanie. Zaznacz właściwą odpowiedź spośród podanych.” / „Dokończ zdania 1. i 2. …”
- Table: „Na podstawie tekstów i własnej wiedzy uzupełnij tabelę – obok opisu wpisz numer fragmentu tekstu zawierającego informacje o grupach, których opis dotyczy.”
- Identification: „Podaj stosowaną w historiografii nazwę …”, „Podaj imię władcy, za panowania którego …”, „Podaj nazwisko postaci przedstawionej na monecie.”, „Podaj nazwę zaboru, na którego terenie …”, „Podaj nazwisko jednego z autorów …”
- Explanation: „Wyjaśnij, odwołując się do źródła 2., w jakich okolicznościach …”, „Wyjaśnij, odwołując się do elementów graficznych ze źródła 1., w jaki sposób …”, „Wyjaśnij, na czym polegało wypaczenie …”, „Wyjaśnij różnicę między …”, „Wyjaśnij, dlaczego w PRL nie można było …”
- Other: „Przedstaw inną – niż wspomniane w źródle 1. – przyczynę …”, „Porównaj … Przedstaw jedno podobieństwo i jedną różnicę …”, „Sformułuj dwa argumenty potwierdzające tezę, że …”, „Wyjaśnij wymowę rysunku, interpretując jego dwa elementy graficzne i tytuł. W odpowiedzi uwzględnij kontekst historyczny …”
- Answer-sheet labels (the grader expects them): `Rozstrzygnięcie:` / `Uzasadnienie:`, `Podobieństwo:` / `Różnica:`, `Nazwa stylu 1.:` / `Cecha:`, `Nazwisko:` / `Wyjaśnienie:`, `WYPRACOWANIE na temat nr …`.
- Knowledge cue: „… i własnej wiedzy” appears in 1, 2.2, 22 and 24. Many other items also silently need outside facts, for example 3.1 (Corsica annexed after the 1st Punic War), 19 (dating the ambassador's text to 17–20 III 1921) and 20 (the Saar plebiscite was lawful under Versailles).

## Implications for our harness

### Canonical output per type

| Type | Output exactly | Notes |
|---|---|---|
| abcd | `C` | One letter. No option text needed; if added, only after the letter. |
| two-part choice („Dokończ zdania 1. i 2.”) | `1-B, 2-C` | **Two answers.** Each sentence has its own A–D list, and each correct letter is worth 1 pt. |
| pf (3 statements) | `F, P, P` | Exactly n values in statement order, only P/F (not T/N, not Prawda). Points are non-linear: 3/3 → 2, 2/3 → 1, 1/3 → 0. |
| table fill / matching | `A-3, B-2` | Keep the question's direction: here the lettered descriptions receive fragment numbers. Our `match` convention (`1-B`) is number → letter. Never flip labels. |
| chrono (not in 2023) | `C, A, D, B` | Labels exactly as printed, earliest first unless the command says otherwise. |
| short identification | `Hanza` / `wojna stuletnia` / `Zygmunt III Waza` / `Ignacy Łukasiewicz` / `zabór austriacki (Galicja)` / `Karol Marks` | Use the historiographic standard name, a full ruler designation with ordinal, and first name plus surname (safe: the surname alone scores, and the first name is harmless). Give **one** answer when one is asked. |
| decision + justification | `Rozstrzygnięcie: Nie`<br>`Uzasadnienie: …` | 1–3 sentences. They must cite concrete details **from every source the command names** (quote a phrase) plus a knowledge fact (name, date, term, e.g. „remilitaryzacja Nadrenii 1936”). A decision without a valid justification is 0. |
| explanation / cause | 1–3 full sentences | Cause and effect, with concrete facts. When told „odwołując się do źródła X”, name the detail from X. For „inną niż w źródle”, do not repeat the source's causes. |
| name + explanation | `Nazwisko: Breżniew`<br>`Wyjaśnienie: …` | Both parts are required („odwołanie do faktografii” means naming events: strikes of 1980, Solidarność, stan wojenny 13 XII 1981). |
| comparison | `Podobieństwo: …`<br>`Różnica: …` | One of each. Each half is worth 1 pt. |
| cartoon (0–3) | one paragraph | Interpret **two** graphic elements **and** the title, and state the **year's context**. Missing the context caps the score at 1. |
| essay | `WYPRACOWANIE na temat nr X` + intro with an explicit stance + 3 paragraphs (one per element) + conclusion | Aim for 450–700 words (hard floor 300). Every paragraph needs facts, dates and terms tied to the thesis. Fewer claims beats wrong claims (factual errors cost 1–3 pts). |

### Pitfalls that lose points

1. **Answering one sentence of a two-part item.** The harness classifies task 21 as plain `abcd`: its parser sees only the first A–D list and would answer a single letter, losing 1 pt.
2. **Truncated P/F statements.** CKE statements wrap across lines, for example „…została przyłączona do Rzymu⏎w wyniku II wojny punickiej.” `harness/qtype.py` keeps only the first line of each numbered statement. The count is still right (3), but the text drops the key clause. That breaks `PF_MODE=split` and statement-based retrieval queries. Continuation lines must be joined to the previous item.
3. **False ABCD detection.** Items 2.2 (table fill with descriptions A/B) and 13.1 („Plan oznaczony literą A … (A czy B)”) are detected as `abcd`. They are a letter → number mapping and a decision + justification respectively.
4. **Newline stop and length caps on justified answers.** Short open detection (≤ 600 characters) applies `stop=["\n"]` and `max_chars=200` (plus `year_only` for year questions). Item 23, an explanation, is detected as `open`, so a multi-line or longer answer gets cut. Most CKE items exceed 600 characters because they embed sources and fall back to `generic` (1200 characters). For decision, explanation and name + explanation items, the harness should allow about 2–4 sentences and never stop at the first newline.
5. **Type detection should run on the command, not the sources.** In benchmark inputs the sources come first and contain bullets, `1/` numbering, markdown tables and „literą A/B”. Detect on the text after the last source block, i.e. the CKE command at the end.
6. **Surplus or hedged answers** („A lub C”, two surnames where one is asked, extra P/F values) are likely scored as wrong.
7. **Bare decision** („Tak”/„Nie”) without justification, or a justification that uses only one of two required sources, scores 0. So does copying the source verbatim without interpreting it („własnymi słowami”).
8. **Ambiguous names:** „Zygmunt” instead of „Zygmunt III Waza”; a dynasty instead of a person; an English exonym instead of the Polish form.
9. **Label changes:** renaming „Fragment 2.” to „B”, renumbering statements, or reordering P/F values breaks deterministic checking.
10. **Budget:** the answer must finish within the 2048-token final allowance (4096 for the essay). A model that thinks too long gets 0.

### Devset built from this paper

`devset/cke-2023.jsonl` (git-ignored, rebuilt by `data_cke/build_cke2023.py`) holds 33 short items worth 40 pts. The essay is in `data_cke/cke-2023-essay.jsonl`.

- **Inputs:** the question text is exactly the mentor benchmark's frozen input, sources first and then the command.
- **Extra fields:**
  - `rubric` / `rubric_text`: official criteria plus the sample solution;
  - `source_kind`: `text`, `table`, `tree`, `transcribed-scan` or `image-description`;
  - `text_only`: false only when the item depends on a lossy image description;
  - `task_group`, `note`, `format`.
- **Counts:** 13 deterministic items (17 pts) and 20 rubric items (23 pts). 23 items (26 pts) are text-only and 10 items (14 pts) rely on image descriptions.
- **Grading caveats in `devset/eval.py`:**
  - The `match` grader only parses digit → letter pairs. A letter → number gold such as 2.2 would pass any prediction, which is why 2.2 is stored as `open` with normalised variants.
  - `lenient` open grading is meaningless for „Tak”/„Nie” golds.
  - Rubric items need an LLM judge that uses `rubric_text`.
