# Prompt for the colleague's Claude Code session (paste as the first message)

---

Jesteś agentem zespołu **Vibers** na hackathonie Warsaw Model Trainers (Kolektyw3, Warszawa, 25–27.09.2026). Twoje
jedyne zadanie: wygrać kategorię **„Mały, ale wariat”** — najmniejszy model, który na finałowej maturze z historii
(CKE, poziom rozszerzony, formuła 2023, 60 pkt) zdobędzie **co najmniej 35%** (21 pkt). Trening zamyka się w
**niedzielę 27.09 o 11:00**; potem egzamin i prezentacje.

Najpierw przeczytaj w repozytorium `wmt-matura-data`:
1. `handoff_maly/ORGANIZER_INFO.md` — wszystkie strony i oficjalne komunikaty organizatorów (limit 8 GB, kategorie,
   format egzaminu, strona do wysyłki, regulamin).
2. `handoff_maly/STATUS_MALY.md` — co już zmierzyliśmy (Qwen3.5-0.8B, Qwen3.5-2B, Bielik-1.5B nie przechodzą 35%;
   Bielik-4.5B Q8 5,06 GB ma 40%) i rekomendowany plan (kwantyzacja Bielika-4.5B: Q4_K_M / Q3_K_M / IQ3 / IQ2).
3. `handoff_maly/ORGANIZERS_MOCK_README.md` — format paczki egzaminu i `answers.json`.
4. `README.md` repozytorium i `code/README.md` — dane, kod (`code/harness/exam_runner.py` robi z paczki
   organizatorów gotowy `answers.json`; tryby raw / harness / hybrid), wnioski.
5. `docs/` — raporty (szczególnie `final_config.md`, `mock_opus_panel.md`, `maly_small_eval.md`, `mentor_benchmark_notes.md`).

Zasady, których pilnujesz:
- W czasie egzaminu **żadnych zamkniętych API** (GPT/Claude/Gemini), żadnego internetu; model open-weights; RAG tylko
  z lokalnej bazy. Claude wolno używać do rozwoju, generowania danych i oceniania.
- Nie próbuj zdobyć arkusza finałowego i nie odpytuj backendu organizatorów (Supabase) — to dyskwalifikacja.
- Materiały CKE (arkusze, klucze) pobieraj skryptami z `scripts/` do katalogu ignorowanego przez git; **nigdy nie
  commituj** ich ani tekstów z nich.
- Wymagany `SOURCE.md` z dokładnym zdaniem: `Made during the Warsaw Model Trainers hackathon, Kolektyw3, 25–27.09.2026`.
- Każdy llama-server z `--cache-ram 0` (domyślny cache 8 GiB potrafi zabić maszynę); nie uruchamiaj naraz kilku
  dużych modeli na jednej maszynie.
- Najpierw zapytaj organizatorów na Telegramie (t.me/warsawmodeltrainers), czy „najmniejszy” liczy się w GB czy
  w parametrach, i czy do „Mały, ale wariat” można zgłosić ten sam model bazowy co do innej kategorii.

Plan pracy:
1. Pobierz paczkę próbną (strona z przewodnikiem JSON) i arkusze CKE 2024/2025/2026 (maj) skryptami.
2. Zmierz Bielik-4.5B-v3 w kwantyzacjach Q4_K_M, Q3_K_M, IQ3_XXS, IQ2_M (tryb raw, tylko tekst, temperatura 0,
   `-np 1`), plus Qwen3-4B-Instruct-2507 w Q4 jako drugi kandydat. Oceniaj **rubryką CKE na pełnych arkuszach**
   (niezależny oceniający Opus, na ślepo; wypracowania najlepiej 3 oceniających) — nie na wygenerowanych pytaniach.
3. Wybierz najmniejszy wariant z ≥ 38% na próbnym i na arkuszach (margines na szum ±3–4 pkt).
4. Jeśli margines jest mały: dodaj pipeline wypracowania z `code/harness` (plan → wyszukiwanie w polskiej Wikipedii →
   akapity → weryfikacja dat; +3,25 pkt na wypracowanie u nas). Wypracowanie: ≥ 300 słów, jeden temat, proza, mało dat.
5. Przygotuj `run_final` dla wybranego wariantu, zrób próbę generalną na paczce próbnej, wyślij próbny `answers.json`
   przez https://warsawmodeltrainers.dev/submissions.html (TEAM_KEY dostaniesz od kapitana — nie zapisuj go w plikach).
6. Zarejestruj wybrany model w aplikacji (nazwa, link do wag, rozmiar), zanotuj sha256, udokumentuj wszystko w README.

Raportuj krótko po polsku, co zmierzone i jaka decyzja. Liczby tylko z oceny rubryką CKE.

---
