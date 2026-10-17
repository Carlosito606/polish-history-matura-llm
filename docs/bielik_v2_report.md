# Bielik-4.5B-v3: LoRA v2 i Qwen3.5-0.8B (26.09.2026), raport stanu

**Stan: v2 NIE jest wytrenowany.** Sesja L40S `01a0dac1` padła o 09:59:31 UTC. Forgehand podał powód `terminationReason: "agent unreachable for 15 minutes"`. To ten sam incydent NFS co w nocy: od około 09:40 SSH zrywał się na etapie banneru, a potem nie było już połączenia TCP. Razem z sesją zniknął `/scratch`, a więc trwający trening Bielika v2 i pierwsze ewaluacje. Nowej sesji nie uruchomiłem, bo uruchomienie płatnej sesji wymaga zgody użytkownika (`fh session ls` pokazuje `no live sessions`).

## Co jest gotowe

### SFT v2 (zbudowany, zapisany na `/workspace`)

- Pliki: `/workspace/data/sft_v2.jsonl` (surowy), `/workspace/data/sft_v2_train.jsonl` (widok treningowy: pf w numerowanym formacie harnessu `1: P\n2: F…` i `meta.type`, tak jak w v1), `sft_v2.jsonl.stats.json`, `sft_v2_samples.md`. Build zakończył się o 09:33 UTC, a pliki skopiowano na NFS przed awarią.
- Snapshot danych z laptopa (08:46 UTC):
  - `claude_verified`: 71 plików, 3053 wiersze;
  - `zpe_verified`: 3 pliki, 203 wiersze;
  - `cke_items`: 59 plików, 1231 wierszy, z czego 1160 ma `split=train` i `verified`.
- Prompty jak na egzaminie: `QTYPE_V2=1`, `RERANK=1` (bge-reranker-v2-m3, `scripts/l40s_rerank.sh`), `top_k=5`, `ctx_tokens=1200`, 10% kopii bez kontekstu (closed-book).
- Dekontaminacja względem 17 plików `devset/` (444 tytuły, 726 pytań): odpadły 2 pozycje (po jednej z CKE i od Claude'a).
- Arkusze CKE w treningu pochodzą z lat 2003–2022. `cke-2023` i `cke-more` to lata 2023–2026, więc żaden arkusz się nie powtarza.

| | v1 | v2 |
|---|---|---|
| pozycje wejściowe | 2157 | 4416 |
| wiersze SFT | 2245 | **4622** |
| claude / cke / zpe | 1860 / 385 / 0 | 3332 / 1065 / 225 |
| abcd / pf / chrono / match / open+generic+explain | 648 / 385 / 283 / 182 / 747 | 1318 / 745 / 540 / 354 / 1662 (+3 abcd_parts) |
| has_gold_ctx / has_evidence (claude + zpe) | 0.872 / 0.819 | 0.813 / 0.762 |
| tokeny Bielik-4.5B p50 / p95 / max | 1316 / 1589 / 2671 | 1320 / 1621 / 3060 → `max_seq_len` 3328 |

Odrzucone przy budowie: głównie CKE `type_mismatch` (163) i `gold_unparsable` (38) oraz 71 pozycji CKE bez weryfikacji.

**Dane nadal przybywają.** O 10:12 UTC na laptopie było już 3446 / 562 / 1399 wierszy (claude / zpe / cke), czyli około 25% więcej niż w snapshocie. Przy restarcie warto przebudować zbiór (`REBUILD=1`, około 30–45 min).

### Kod (laptop, bez commita; `build_sft.py` i `train_lora.py` są też w `/workspace/wmt-matura`)

- `train/build_sft.py`: `--claude-dir` przyjmuje kilka katalogów. Katalog `zpe*` dostaje źródło `zpe` i jest traktowany jak dane od Claude'a (gold ctx, evidence).
- `train/train_lora.py`: poprawka dla Qwen3.5. Unsloth zwraca `Qwen3VLProcessor`, więc skrypt bierze z niego `.tokenizer`.
- `train/export.sh`: nowa opcja `--merge-only`, która robi merge i Q8_0 z istniejącego adaptera bez ponownej konwersji. Dzięki temu ewaluacja adaptera nie czeka na merge.
- `train/v2/`:
  - `launch_v2.sh`: jedno polecenie po świeżej sesji. Odtwarza `/scratch/ovl` (venvy, llama.cpp, modele z `sha256sum -c`, indeks KB, wagi HF Bielika i Qwena) i uruchamia `run_all.sh`.
  - `run_all.sh`: dwa łańcuchy. Łańcuch A trenuje: Bielik v2 r16e2, potem eksport adaptera, merge Q8_0, Bielik v2 r16e3 i Qwen3.5-0.8B r16e2. Łańcuch B ewaluuje: Qwen B i T(v2), powtórkę adaptera v1, v2, merged, B(merged), r16e3 i Qwen T(v2+LoRA).
  - `lib.sh`, `env.sh`, `sync_back.sh`: po każdym kamieniu milowym wyniki są od razu zapisywane na `/workspace`, żeby kolejna awaria sesji ich nie zabrała.
  - `summarize_v2.py`: tabela końcowa.

### Qwen3.5-0.8B: smoke test przeszedł

- Środowisko: `unsloth` 2026.9.11 („Fast Qwen3_5 patching”), transformers 5.5.0, trening bf16 LoRA.
- Adapter obejmuje wyłącznie wieże językowe: MLP we wszystkich 24 warstwach oraz q/k/v/o w 6 warstwach full-attention, razem 192 tensory. Warstwy liniowe Gated DeltaNet i wieża wizyjna nie mają adaptera.
- Eksport: adapter GGUF ma 12,8 MB. Baza i adapter razem to 0,825 GB (limit PASS).
- `llama-server` ładuje adapter, a harness z `enable_thinking=false` odpowiada poprawnie.
- Baza GGUF `/workspace/models/qwen35-0.8b/Qwen3.5-0.8B-Q8_0.gguf` była już na dysku. Jej sha256 `0ad885ff…6a6c` zgadza się z `models/SHA256SUMS`.
- Uwaga praktyczna: pierwszy krok treningu trwa około 165 s, bo biblioteka `fla` nie jest zainstalowana i Gated DeltaNet działa w czystym torchu. Każdy następny krok zajmuje około 1 s.

## Którego adaptera Bielika użyć: na dziś v1

Zmierzony jest tylko v1, więc to on idzie do wysyłki. Wyniki z nocy (673 pytania, strict / lenient %):

| zbiór | n | B | T(v2) | T(v2 + LoRA v1) |
|---|---|---|---|---|
| tourney160 | 160 | 3.1 / 36.9 | 59.4 / 61.9 | 75.6 / 75.6 |
| dev-a | 70 | 0.0 / 28.6 | 74.3 / 77.1 | 84.3 / 85.7 |
| dev-b | 72 | 5.6 / 40.3 | 70.8 / 70.8 | 81.9 / 81.9 |
| dev-c | 77 | 0.0 / 31.2 | 64.9 / 66.2 | 76.6 / 76.6 |
| dev-f | 60 | 3.3 / 36.7 | 75.0 / 78.3 | 78.3 / 81.7 |
| dev-g | 60 | 1.7 / 45.0 | 65.0 / 66.7 | 80.0 / 80.0 |
| dev-h | 70 | 8.6 / 42.9 | 67.1 / 70.0 | 72.9 / 74.3 |
| cke-2023 | 33 | 0.0 / 57.6 | 45.5 / 54.5 | 45.5 / 54.5 |
| cke-more | 71 | 1.4 / 45.1 | 52.1 / 56.3 | 69.0 / 69.0 |
| **łącznie** | 673 | **2.8** / 38.9 | **64.0** / 66.7 | **75.5** / 76.5 |

Gain strict wynosi +72,7 pp. v2 zastąpi v1 tylko wtedy, gdy wygra łącznie (strict) i nie przegra na tourney160.

### Pliki do wysłania (sha256 z manifestów z nocy)

| plik | bajty | sha256 |
|---|---|---|
| `/workspace/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf` (baza, nietknięta) | 5 061 215 424 | `562f2291de257890adf2b4a914da8b194affe6a7a838a6b7ef3d342f306c1b7f` |
| `/workspace/loras/final-bielik-4.5b-v3-r16-e2.gguf` (adapter v1) | 99 836 544 | `c4d012381af3e2e37c7ae37e59dfada354e67f546605c5f9479145eb57e8aa65` |

- Razem 5,161 GB, więc limit 8 GB jest spełniony.
- Scalonej kopii zapasowej (merged Q8_0) nie ma. Zbudowałaby ją `run_all.sh` (`export.sh --merge-only`), albo można ją zrobić ręcznie dla v1: `bash train/export.sh --run final-bielik-4.5b-v3-r16-e2 --base-gguf bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf --merge-only`.
- Pipeline mierzy też B(merged), czyli surowy model po scaleniu. Jeśli organizatorzy zarejestrują model scalony jako bazę, B wzrośnie i gain spadnie.

## Wyniki Qwen3.5-0.8B

Brak. Ewaluacja przepadła razem z sesją.

## Jak wznowić (po zgodzie na nową sesję L40S)

```bash
fh session start vibers --class gpu-l40s-small --wait      # nowe IP -> zaktualizować HostName l40s w ~/.ssh/config
cd $HOME/wmt-matura
scp -r train/v2 l40s:/workspace/wmt-matura/train/ && scp train/export.sh train/train_lora.py train/build_sft.py l40s:/workspace/wmt-matura/train/
# opcjonalnie świeże dane: tar claude_verified zpe_verified cke_items -> /workspace/data/src/ i REBUILD=1
ssh l40s 'mkdir -p /scratch/v2; REBUILD=1 setsid nohup bash /workspace/wmt-matura/train/v2/launch_v2.sh > /scratch/v2/launch.out 2>&1 < /dev/null &'
# postęp: /scratch/v2/{launch.out,trainA.status,evalB.status}; tabela:
ssh l40s 'cd /scratch/ovl/wmt-matura && /scratch/ovl/venvs/wmt/bin/python /scratch/v2/summarize_v2.py bielik; /scratch/ovl/venvs/wmt/bin/python /scratch/v2/summarize_v2.py qwen'
```

Szacowany czas: mirror 10–15 min, rebuild około 40 min, Bielik v2 r16e2 około 70 min (około 560 kroków), eksport i merge około 15 min, ewaluacja jednego wariantu na 673 pytaniach około 15 min, r16e3 około 105 min, Qwen 0.8B około 30 min. Pierwszy werdykt v1 kontra v2 będzie około 2,5 h od startu.

Etykiety w `devset/experiments.csv`:

- `bielik45-v2-harness-v2-lora-v1` (powtórka v1, szum), `bielik45-v2-harness-v2-lora-r16e2`, `bielik45-v2-harness-v2-lora-r16e3`;
- `bielik45-v2-harness-v2-merged-r16e2`, `bielik45-v2-merged-r16e2-base-raw`;
- `qwen08-v2-{base-raw,harness-v2,harness-v2-lora-r16e2}`.

Dopisanie wierszy do CSV na Macu (`~/wmt-matura/devset/experiments.csv`) zostaje do zrobienia po przebiegu.
