# Raport nocny: LoRA na zwycięzcy i wicemistrzu sweepu (26.09.2026)

Wszystko liczone na L40S (Forgehand), jedna sesja GPU. Skala: % poprawnych, strict / lenient.
B = nietknięty model bazowy bez harnessu (`eval.py --endpoint base --max-tokens 512`, osobny llama-server bez LoRA).
T(v2) = harness v2 (`QTYPE_V2=1 RERANK=1`) bez LoRA. T(v2+LoRA) = ten sam harness z adapterem ładowanym w runtime (`--lora-scaled adapter:1.0`).
Gain = T − B (strict / lenient), w punktach procentowych. Delta LoRA = T(v2+LoRA) − T(v2).

## Wynik w skrócie

- **Bielik-4.5B-v3 z LoRA wyprzedza Qwen3-8B z LoRA.** Na tourney160 ma 75,6% strict przy B 3,1%, czyli gain +72,5 pp. Qwen3-8B ma 65,0% przy B 3,8%, czyli +61,2 pp. Na wszystkich 673 pytaniach łącznie: Bielik +72,7 pp, Qwen +63,0 pp.
- **LoRA pomaga obu modelom.** Qwen3-8B zyskuje +3,0 pp (łącznie), Bielik-4.5B +11,4 pp. Bielik nie spada na żadnym zbiorze.
- **Źródło przewagi Bielika.** Bez adaptera Bielik nie trzyma formatu odpowiedzi: gen-eval bez adaptera daje 0,24 exact, w tym abcd 0,00 i chrono 0,00. Z adapterem ma 0,73. Qwen już przed treningiem trzymał format (0,58, po treningu 0,76), więc zyskał mniej.
- **Rekomendacja do decyzji zespołu:** finałowy system = Bielik-4.5B-v3 Q8_0 + `final-bielik-4.5b-v3-r16-e2.gguf`, razem 5,16 GB (limit 8 GB).
  - To zadziała tylko wtedy, gdy zarejestrowanym modelem bazowym jest Bielik-4.5B-v3 Q8_0, bo gain liczy się względem nietkniętej bazy.
  - Trzeba też potwierdzić, że aplikacja egzaminacyjna przyjmuje adapter LoRA jako osobny plik obok niezmienionego GGUF. Scalenia modelu (`--merge`) nie robiłem.

## Tabela

| model | zbiór | n | B strict/len | T(v2) strict/len | T(v2+LoRA) strict/len | gain T(v2)−B | gain T(v2+LoRA)−B | delta LoRA |
|---|---|---|---|---|---|---|---|---|
| qwen3-8b | tourney160 | 160 | 3.8 / 25.6 | 61.3 / 61.9 | 65.0 / 66.2 | +57.5 / +36.3 | +61.2 / +40.6 | +3.7 / +4.4 |
| qwen3-8b | dev-a | 70 | 5.7 / 28.6 | 80.0 / 81.4 | 85.7 / 85.7 | +74.3 / +52.9 | +80.0 / +57.1 | +5.7 / +4.3 |
| qwen3-8b | dev-b | 72 | 6.9 / 23.6 | 73.6 / 73.6 | 76.4 / 77.8 | +66.7 / +50.0 | +69.5 / +54.2 | +2.8 / +4.2 |
| qwen3-8b | dev-c | 77 | 0.0 / 16.9 | 72.7 / 74.0 | 72.7 / 74.0 | +72.7 / +57.2 | +72.7 / +57.2 | +0.0 / +0.0 |
| qwen3-8b | dev-f | 60 | 5.0 / 25.0 | 68.3 / 68.3 | 73.3 / 76.7 | +63.3 / +43.3 | +68.3 / +51.7 | +5.0 / +8.3 |
| qwen3-8b | dev-g | 60 | 8.3 / 33.3 | 70.0 / 70.0 | 75.0 / 75.0 | +61.7 / +36.7 | +66.7 / +41.7 | +5.0 / +5.0 |
| qwen3-8b | dev-h | 70 | 8.6 / 32.9 | 68.6 / 70.0 | 70.0 / 70.0 | +60.0 / +37.1 | +61.4 / +37.1 | +1.4 / +0.0 |
| qwen3-8b | cke-2023 | 33 | 3.0 / 45.5 | 33.3 / 36.4 | 36.4 / 42.4 | +30.3 / −9.1 | +33.3 / −3.0 | +3.0 / +6.1 |
| qwen3-8b | cke-more | 71 | 8.5 / 35.2 | 49.3 / 50.7 | 49.3 / 49.3 | +40.8 / +15.5 | +40.8 / +14.1 | +0.0 / −1.4 |
| **qwen3-8b** | **łącznie** | 673 | 5.3 / 28.1 | 65.4 / 66.3 | 68.4 / 69.5 | +60.0 / +38.2 | **+63.0** / +41.5 | +3.0 / +3.3 |
| bielik-4.5b-v3 | tourney160 | 160 | 3.1 / 36.9 | 59.4 / 61.9 | 75.6 / 75.6 | +56.3 / +25.0 | +72.5 / +38.7 | +16.2 / +13.7 |
| bielik-4.5b-v3 | dev-a | 70 | 0.0 / 28.6 | 74.3 / 77.1 | 84.3 / 85.7 | +74.3 / +48.6 | +84.3 / +57.1 | +10.0 / +8.6 |
| bielik-4.5b-v3 | dev-b | 72 | 5.6 / 40.3 | 70.8 / 70.8 | 81.9 / 81.9 | +65.3 / +30.5 | +76.4 / +41.7 | +11.1 / +11.1 |
| bielik-4.5b-v3 | dev-c | 77 | 0.0 / 31.2 | 64.9 / 66.2 | 76.6 / 76.6 | +64.9 / +35.1 | +76.6 / +45.5 | +11.7 / +10.4 |
| bielik-4.5b-v3 | dev-f | 60 | 3.3 / 36.7 | 75.0 / 78.3 | 78.3 / 81.7 | +71.7 / +41.7 | +75.0 / +45.0 | +3.3 / +3.3 |
| bielik-4.5b-v3 | dev-g | 60 | 1.7 / 45.0 | 65.0 / 66.7 | 80.0 / 80.0 | +63.3 / +21.7 | +78.3 / +35.0 | +15.0 / +13.3 |
| bielik-4.5b-v3 | dev-h | 70 | 8.6 / 42.9 | 67.1 / 70.0 | 72.9 / 74.3 | +58.6 / +27.1 | +64.3 / +31.4 | +5.7 / +4.3 |
| bielik-4.5b-v3 | cke-2023 | 33 | 0.0 / 57.6 | 45.5 / 54.5 | 45.5 / 54.5 | +45.5 / −3.0 | +45.5 / −3.0 | +0.0 / +0.0 |
| bielik-4.5b-v3 | cke-more | 71 | 1.4 / 45.1 | 52.1 / 56.3 | 69.0 / 69.0 | +50.7 / +11.3 | +67.6 / +23.9 | +16.9 / +12.7 |
| **bielik-4.5b-v3** | **łącznie** | 673 | 2.8 / 38.9 | 64.0 / 66.7 | 75.5 / 76.5 | +61.2 / +27.8 | **+72.7** / +37.6 | +11.4 / +9.8 |

Każdy wiersz pochodzi z przebiegu z `errors=0`. Przebiegi z błędami serwera zostały powtórzone, a ich wiersze są pomijane przez `summarize.py` i `done.py`.
B na tourney160 zgadza się ze sweepem: 3,8 wobec 3,75 dla Qwena i 3,1 wobec 2,5 dla Bielika. T(v2) też: 61,3 wobec 61,9 i 59,4 wobec 58,8.

## Co zadziałało, a co wymaga sprawdzenia

- **Zadziałało:** SFT v1 (krótkie kanoniczne odpowiedzi z kontekstem KB) plus LoRA r16 przez 2 epoki. Adapter uczy głównie formatu (abcd, chrono, match, pf w formacie numerowanym harnessu), a harness v2 dostarcza wiedzę. Największe zyski Bielika są na tourney160 (+16,2), cke-more (+16,9) i dev-g (+15,0).
- **Sprawdzić przed decyzją: zbiory CKE.**
  - SFT zawiera 385 wierszy z CKE train. Dekontaminacja z buildu SFT sprawdzała nakładanie się pytań i tytułów źródeł z 17 plikami dev.
  - Warto jednak potwierdzić, że `cke-more` (arkusze 2023–2026) nie dzieli arkuszy z CKE train, bo +16,9 pp dla Bielika to dużo.
  - `cke-2023` (prawdziwy arkusz, n=33) daje LoRA +0 dla Bielika i +3,0 dla Qwena.
- **Sprawdzić przed decyzją: zbiory Claude'owe.** dev-a…h i tourney160 mają ten sam styl co dane SFT od Claude'a. Zysk na prawdziwym egzaminie może więc być mniejszy niż tutaj.
- **B lenient na CKE jest wysokie** (45–58%) przy strict 0–3%. Surowy model odpowiada opisowo, więc gain lenient jest tam mały albo ujemny. Gain strict jest miarą właściwą dla formatu egzaminu.

## Trening (oba modele tak samo)

- Dane: `/workspace/data/sft_v1_train.jsonl`, czyli sft_v1 z odpowiedziami pf w numerowanym formacie harnessu (`1: P\n2: F…`). Podział: 2178 wierszy train i 67 eval (3%, seed 42). Nic nie zostało odrzucone za długość, a `boundary_token_mismatch` i `template_fallback_used` wynoszą 0.
- Hiperparametry: bf16 LoRA r=16, alpha=32, na q/k/v/o/gate/up/down, lr 1e-4 (cosine, warmup 3%), 2 epoki, 274 kroki, batch 4 × grad-accum 4, loss tylko na odpowiedzi, Unsloth.
- `max_seq_len`: Qwen 2816 (p95 2066 tokenów, max 2685), Bielik 3072 (p95 1589, max 2671).

| | train loss | eval loss | czas | peak VRAM | gen-eval exact (bez → z adapterem) |
|---|---|---|---|---|---|
| Qwen3-8B (`--chat-template-kwargs '{"enable_thinking": false}'`) | 0.270 | 0.295 | 52 min | 24.8 GB | 0.58 → 0.76 |
| Bielik-4.5B-v3 | 0.187 | 0.287 | 34 min | 12.8 GB | 0.24 → 0.73 |

## Pliki i sumy kontrolne (sha256)

| co | ścieżka (L40S) | bajty | sha256 |
|---|---|---|---|
| baza Qwen3-8B Q4_K_M | `/workspace/models/qwen3-8b/Qwen3-8B-Q4_K_M.gguf` | 5 027 783 488 | `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785` |
| adapter Qwen | `/workspace/loras/final-qwen3-8b-r16-e2.gguf` | 87 328 896 | `ef90a8a05a8822e967c99b82f4aff08a5b1706647df9b05cbd98d9ff0398c30d` |
| baza Bielik-4.5B-v3 Q8_0 | `/workspace/models/bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf` | 5 061 215 424 | `562f2291de257890adf2b4a914da8b194affe6a7a838a6b7ef3d342f306c1b7f` |
| adapter Bielik | `/workspace/loras/final-bielik-4.5b-v3-r16-e2.gguf` | 99 836 544 | `c4d012381af3e2e37c7ae37e59dfada354e67f546605c5f9479145eb57e8aa65` |

- Test 8 GB (baza + adapter) przechodzi dla obu: Qwen 5,115 GB, Bielik 5,161 GB. Manifesty leżą obok adapterów (`*.gguf.json`).
- Sumy baz sprawdziłem `sha256sum -c` względem `models/SHA256SUMS` (05:05 UTC): obie OK. Bazowe GGUF-y były tylko czytane.
- Adaptery PEFT i metryki treningu: `/workspace/runs/final-{qwen3-8b,bielik-4.5b-v3}-r16-e2/` (pliki `adapter/`, `metrics.json`, `data_stats.json`, `gen_eval.jsonl`).
- Wyniki:
  - L40S: `/workspace/wmt-matura/devset/experiments.csv`.
  - Mac: `~/wmt-matura/devset/experiments.csv`, dopisane 54 wiersze `final-<model>-{base-raw,harness-v2,harness-v2-lora}`, po jednym czystym na (etykietę, plik).
- Logi i statusy:
  - `/workspace/data/overnight/` (przebiegi 00:36–04:11 UTC).
  - `/scratch/overnight/` (kopia w `/workspace/data/overnight/scratch_copy/`).
- Skrypty: `train/overnight/` w repo, czyli `run_model.sh`, `rerun.sh`, `driver.sh` z pierwszego przebiegu oraz `sup.sh`, `mirror.sh`, `sup2.sh`, `sync_back.sh`, `launch.sh`, `done.py`, `summarize.py`.

## Incydent: NFS `/workspace` na L40S

- **Objawy:** `/workspace` (nfs4 przez 127.0.0.1) okresowo zwraca `EACCES`. Zdarzyło się to około 01:36, 03:33 i 04:35 UTC i za każdym razem kończyło się tak samo:
  - zabite drivery ewaluacji;
  - trening Bielika przerwany w kroku 135/274 (`PermissionError` przy zapisie `train_log.jsonl`);
  - `exit 126` przy starcie pythonów z venvów;
  - przez 10–20 minut `ssh` zrywał połączenie na etapie `kex_exchange_identification`, bo HOME jest na NFS.
- **Obejście:** `mirror.sh` kopiuje kod, venvy (dla train robi shim), llama.cpp, modele, KB i wagi HF na lokalny `/scratch/ovl`. `sup2.sh` prowadzi cały pipeline stamtąd, a `sync_back.sh` odsyła wyniki na `/workspace`. Od tej zmiany nie było żadnej awarii.
- **Rada dla zespołu:** długie zadania uruchamiać z `/scratch`. Trzeba jednak pamiętać, że `/scratch` znika po zakończeniu sesji.

## Jak odtworzyć

```bash
ssh l40s
cd /workspace/wmt-matura && source /workspace/env.sh      # HF_TOKEN, nie wypisywać

# 1. trening (Bielik; dla Qwena: --base Qwen/Qwen3-8B --max-seq-len 2816 --chat-template-kwargs '{"enable_thinking": false}')
/workspace/venvs/train/bin/python train/train_lora.py --data /workspace/data/sft_v1_train.jsonl --eval-frac 0.03 \
  --base speakleash/Bielik-4.5B-v3.0-Instruct --name final-bielik-4.5b-v3-r16-e2 --r 16 --alpha 32 --lr 1e-4 \
  --epochs 2 --max-seq-len 3072 --batch 4 --grad-accum 4 --seed 42 --gen-eval-n 67 --gen-eval-base

# 2. eksport + test 8 GB
bash train/export.sh --run final-bielik-4.5b-v3-r16-e2 --base-gguf bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf

# 3. T(v2+LoRA); dla T(v2) to samo bez LORA_FILE
#    dla Qwena dodatkowo: CHAT_TEMPLATE_KWARGS='{"enable_thinking": false}' LLM_EXTRA_BODY='{"chat_template_kwargs": {"enable_thinking": false}}'
bash scripts/l40s_rerank.sh start                                   # bge-reranker-v2-m3 Q8_0 na :18092
LLM_PORT=18082 HARNESS_PORT=18002 MODEL_FILE=bielik-4.5b-v3/Bielik-4.5B-v3.0-Instruct.Q8_0.gguf CTX=32768 NP=8 \
  LORA_FILE=/workspace/loras/final-bielik-4.5b-v3-r16-e2.gguf LORA_SCALE=1.0 QTYPE_V2=1 RERANK=1 \
  RERANK_URL=http://127.0.0.1:18092 LLM_CONCURRENCY=8 bash scripts/l40s_serve.sh start
/workspace/venvs/wmt/bin/python devset/eval.py --endpoint answer --url http://127.0.0.1:18002 \
  --files devset/tourney160.jsonl --workers 8 --label final-bielik-4.5b-v3-harness-v2-lora

# 4. B: serwer BEZ LoRA (osobny proces), surowy model przez --endpoint base
/workspace/venvs/wmt/bin/python devset/eval.py --endpoint base --max-tokens 512 --url http://127.0.0.1:18003 \
  --files devset/tourney160.jsonl --workers 8 --label final-bielik-4.5b-v3-base-raw

# całość odporna na NFS (idempotentna, pomija przebiegi z errors=0 w experiments.csv):
#   skopiuj train/overnight/*.sh,*.py do /scratch/overnight i uruchom:
setsid nohup bash /scratch/overnight/launch.sh > /scratch/overnight/launch.out 2>&1 < /dev/null &
# tabela:
CSV=/workspace/wmt-matura/devset/experiments.csv /workspace/venvs/wmt/bin/python train/overnight/summarize.py qwen3-8b bielik-4.5b-v3
```

Harness v2 w tych przebiegach: `ctx_tokens=1200`, `top_k=5`, gramatyka włączona, `chrono_mode=hybrid`, `pf_mode=joint`, KB BM25 z `/scratch/kb_index` (kopia `/workspace/kb_data/index`).
