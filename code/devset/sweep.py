#!/usr/bin/env python
""""Go lower" model sweep: raw untouched base vs harness(+KB) for many small base GGUFs.

For every model: start llama-server on 127.0.0.1:18081, a harness instance on 127.0.0.1:18001, then run
devset/eval.py on devset/tourney160.jsonl:
  t-<model>-base-raw      /base passthrough, question as the only user message, no system prompt,
                          template defaults (hybrid models think), max_tokens 1024; llama-server
                          (--jinja, reasoning-format auto) returns the thinking in reasoning_content,
                          so graded `content` has no <think> block.
  t-<model>-harness-kb    harness defaults, KB on (thinking disabled via chat_template_kwargs)
  t-<model>-harness-nokb  same, use_kb=0 (every 3rd model)
Both processes are stopped afterwards. Ports 18080/18000 (another agent) are never touched.

The harness runs from a FROZEN copy (sweep/rt/harness) so edits by other agents during the sweep do not
change the comparison; the copy adds a persistent BM25 retrieval cache (RETRIEVAL_CACHE). BM25 is
deterministic and query building does not depend on the LLM, so the cache changes speed, not results.

Usage (Mac, from ~/wmt-matura with .venv):
  python devset/sweep.py prewarm [--procs 4]
  python devset/sweep.py run [--only k1,k2] [--deadline-min 150]
  python devset/sweep.py report

L40S profile (auto when /workspace/opt/llama/current exists, or SWEEP_PROFILE=l40s), run from /workspace/wmt-matura:
  /workspace/venvs/wmt/bin/python devset/sweep.py prewarm --procs 2
  /workspace/venvs/wmt/bin/python devset/sweep.py run --order <keys>
  llama.cpp b11185 CUDA from /workspace/opt/llama/current (glibc-2.39 shim via patchelf, as scripts/l40s_serve.sh),
  models /workspace/models, KB /workspace/kb_data/index, frozen harness + BM25 cache on /scratch/sweep (local NVMe).
  Labels l40s-<key>-{base-raw,harness-kb,harness-nokb}; base max_tokens 512 (thinking OFF for the hybrid Qwens);
  -np 8 -c 32768 -kvu -fa on; 8 eval workers; kb -> nokb -> base run one after another (clean latencies);
  nokb for every model. Report: devset/sweep_results_l40s.md sorted by GAIN_strict = T_kb_strict - B_strict.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import time

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L40S = os.environ.get("SWEEP_PROFILE", "l40s" if os.path.isdir("/workspace/opt/llama/current") else "mac") == "l40s"
SWEEP = os.path.join(ROOT, "sweep")
RT = os.path.join(SWEEP, "rt")
CACHE = os.path.join(SWEEP, "retrieval_cache.sqlite")
RESULTS_JSON = os.path.join(SWEEP, "results.json")
RESULTS_MD = os.path.join(ROOT, "devset", "sweep_results.md")
DEVSET = os.path.join(ROOT, "devset", "tourney160.jsonl")
LLAMA = os.path.join(ROOT, "bin", "llama", "llama-b11185", "llama-server")
KB_INDEX = os.path.join(ROOT, "kb_data", "index")
MODELS_DIR = os.path.join(ROOT, "models")
LOG_DIR = os.path.join(ROOT, "logs")
LLM_PORT, H_PORT = 18081, 18001
FORBIDDEN_PORTS = {18080, 18000}
# 256 = eval.py default. 1024 was planned for thinking runs only; with thinking off for the hybrid models and the
# GPU saturated by other agents, 1024-token verbose base answers cost ~3 min/item (qwen3-4b-2507) -> infeasible.
BASE_MAX_TOKENS = 256
NO_THINK = json.dumps({"chat_template_kwargs": {"enable_thinking": False}})
# Hybrid-thinking models (template default = think). On the shared, saturated GPU a thinking raw-base run is
# infeasible (Qwen3.5-4B: >600 reasoning tokens without an answer for "Grunwald?", ~1 tok/s/slot under load),
# so their llama-server gets --chat-template-kwargs enable_thinking=false and the base label is *-base-raw-nothink.
THINKERS = {"qwen35-4b", "qwen35-2b", "qwen35-0.8b", "qwen3-1.7b", "qwen3-0.6b", "qwen3-8b", "qwen35-9b"}
LABEL_PREFIX = "t"
BASE_NOTHINK_SUFFIX = True
SERIAL_PHASES = False   # Mac: kb+nokb together, then base; L40S: kb, nokb, base one after another
LLAMA_FLAGS: list[str] = []
if L40S:
    SWEEP = os.path.join(ROOT, "sweep")
    RT = "/scratch/sweep/rt"                      # many small files -> local NVMe, not the network FS
    CACHE = "/scratch/sweep/retrieval_cache.sqlite"  # sqlite on NFS locks badly
    RESULTS_JSON = os.path.join(SWEEP, "results_l40s.json")
    RESULTS_MD = os.path.join(ROOT, "devset", "sweep_results_l40s.md")
    LLAMA = "/workspace/opt/llama/current/llama-server"  # patchelf'd onto /workspace/opt/glibc-2.39 (l40s_serve.sh)
    KB_INDEX = "/workspace/kb_data/index"
    MODELS_DIR = "/workspace/models"
    LOG_DIR = "/workspace/logs"
    BASE_MAX_TOKENS = 512
    LABEL_PREFIX = "l40s"
    BASE_NOTHINK_SUFFIX = False
    SERIAL_PHASES = True
    LLAMA_FLAGS = ["-fa", "on"]

# key, models/<dir>, nominal params, family
MODELS = [
    ("qwen35-4b", "qwen35-4b", "4B", "qwen35"),
    ("qwen3-4b-2507", "qwen3-4b-2507", "4.0B", "qwen3"),
    ("gemma-3-4b", "gemma-3-4b", "4.3B", "gemma3"),
    ("bielik-4.5b", "bielik-4.5b-v3", "4.6B", "bielik"),
    ("gemma-4-e4b", "gemma-4-e4b", "E4B (~8B w/ PLE)", "gemma4"),
    ("gemma-4-e2b", "gemma-4-e2b", "E2B (~5B w/ PLE)", "gemma4"),
    ("llama-3.2-3b", "llama-3.2-3b", "3.2B", "llama"),
    ("qwen35-2b", "qwen35-2b", "2B", "qwen35"),
    ("qwen3-1.7b", "qwen3-1.7b", "1.7B", "qwen3"),
    ("bielik-1.5b", "bielik-1.5b-v3", "1.6B", "bielik"),
    ("llama-3.2-1b", "llama-3.2-1b", "1.2B", "llama"),
    ("gemma-3-1b", "gemma-3-1b", "1.0B", "gemma3"),
    ("qwen35-0.8b", "qwen35-0.8b", "0.8B", "qwen35"),
    ("qwen3-0.6b", "qwen3-0.6b", "0.6B", "qwen3"),
    ("bielik-11b", "bielik-11b-v3", "11.2B", "bielik"),
    ("qwen3-8b", "qwen3-8b", "8.2B", "qwen3"),
    ("minitron-7b", "bielik-minitron-7b", "7B", "bielik"),
    ("qwen35-9b", "qwen35-9b", "9B", "qwen35"),
    ("gemma-4-12b", "gemma-4-12b", "12B", "gemma4"),
]
if L40S:  # keys = run labels; dirs = /workspace/models layout (qwen3.5-9b, bielik-minitron-7b-v3, bielik-1.5b)
    MODELS = [
        ("qwen35-4b", "qwen35-4b", "4B", "qwen35"),
        ("qwen3-4b-2507", "qwen3-4b-2507", "4.0B", "qwen3"),
        ("gemma-3-4b", "gemma-3-4b", "4.3B", "gemma3"),
        ("bielik-4.5b-v3", "bielik-4.5b-v3", "4.6B", "bielik"),
        ("gemma-4-e4b", "gemma-4-e4b", "E4B (~8B w/ PLE)", "gemma4"),
        ("gemma-4-e2b", "gemma-4-e2b", "E2B (~5B w/ PLE)", "gemma4"),
        ("llama-3.2-3b", "llama-3.2-3b", "3.2B", "llama"),
        ("qwen35-2b", "qwen35-2b", "2B", "qwen35"),
        ("qwen3-1.7b", "qwen3-1.7b", "1.7B", "qwen3"),
        ("bielik-1.5b", "bielik-1.5b", "1.6B", "bielik"),
        ("llama-3.2-1b", "llama-3.2-1b", "1.2B", "llama"),
        ("gemma-3-1b", "gemma-3-1b", "1.0B", "gemma3"),
        ("qwen35-0.8b", "qwen35-0.8b", "0.8B", "qwen35"),
        ("qwen3-0.6b", "qwen3-0.6b", "0.6B", "qwen3"),
        ("bielik-11b-v3", "bielik-11b-v3", "11.2B", "bielik"),
        ("qwen3-8b", "qwen3-8b", "8.2B", "qwen3"),
        ("bielik-minitron-7b", "bielik-minitron-7b-v3", "7B", "bielik"),
        ("qwen35-9b", "qwen3.5-9b", "9B", "qwen35"),
        ("gemma-4-12b", "gemma-4-12b", "12B", "gemma4"),
    ]
PARAMS_B = {"qwen35-4b": 4.0, "qwen3-4b-2507": 4.0, "gemma-3-4b": 4.3, "bielik-4.5b-v3": 4.6, "gemma-4-e4b": 8.0,
            "gemma-4-e2b": 5.1, "llama-3.2-3b": 3.2, "qwen35-2b": 2.0, "qwen3-1.7b": 1.7, "bielik-1.5b": 1.6,
            "llama-3.2-1b": 1.2, "gemma-3-1b": 1.0, "qwen35-0.8b": 0.8, "qwen3-0.6b": 0.6, "bielik-11b-v3": 11.2,
            "qwen3-8b": 8.2, "bielik-minitron-7b": 7.0, "qwen35-9b": 9.0, "gemma-4-12b": 12.0}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ----------------------------------------------------------------------------- frozen harness copy
CACHE_PATCH = r'''

# ---- sweep-only: persistent BM25 retrieval cache (deterministic -> same results, faster) ----
_SWEEP_CACHE = os.environ.get("RETRIEVAL_CACHE", "")
if _SWEEP_CACHE:
    import json as _sjson
    import sqlite3 as _ssql

    _s_orig_search = Retriever.search
    _s_db = _ssql.connect(_SWEEP_CACHE, check_same_thread=False, timeout=120)
    _s_db.execute("create table if not exists c (k text primary key, v text)")
    _s_db.commit()
    _s_lock = threading.Lock()

    def _s_default(o):
        return o.item() if hasattr(o, "item") else str(o)

    def _s_cached_search(self, query, k):
        key = f"{os.path.realpath(self.index_dir or '')}|{k}|{query}"
        with _s_lock:
            row = _s_db.execute("select v from c where k=?", (key,)).fetchone()
        if row is not None:
            return _sjson.loads(row[0])
        res = _s_orig_search(self, query, k)
        with _s_lock:
            _s_db.execute("insert or replace into c values (?,?)",
                          (key, _sjson.dumps(res, ensure_ascii=False, default=_s_default)))
            _s_db.commit()
        return _sjson.loads(_sjson.dumps(res, ensure_ascii=False, default=_s_default))

    Retriever.search = _s_cached_search
'''


def ensure_rt() -> None:
    dst = os.path.join(RT, "harness")
    if os.path.exists(os.path.join(dst, "retrieval.py")):
        return
    os.makedirs(RT, exist_ok=True)
    shutil.copytree(os.path.join(ROOT, "harness"), dst,
                    ignore=shutil.ignore_patterns("__pycache__", "_kb_snapshot", "*.pyc"))
    with open(os.path.join(dst, "retrieval.py"), "a", encoding="utf-8") as f:
        f.write(CACHE_PATCH)
    log(f"frozen harness copy -> {dst}")


def rt_env(extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = RT + os.pathsep + ROOT
    env["KB_INDEX_DIR"] = KB_INDEX
    env["RETRIEVAL_CACHE"] = CACHE
    env.update(extra or {})
    return env


# ----------------------------------------------------------------------------- prewarm
def load_items() -> list[dict]:
    with open(DEVSET, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def prewarm_worker(shard: int, nshards: int) -> None:
    sys.path.insert(0, RT)
    sys.path.insert(1, ROOT)
    os.environ["KB_INDEX_DIR"] = KB_INDEX
    os.environ["RETRIEVAL_CACHE"] = CACHE
    from harness.config import Settings
    from harness.qtype import detect
    from harness.retrieval import Retriever, retrieve
    s = Settings()
    r = Retriever(s)
    items = load_items()[shard::nshards]
    t0 = time.time()
    for i, it in enumerate(items, 1):
        pq = detect(it["question"], None)
        retrieve(r, pq, s)
        if i % 10 == 0:
            log(f"shard {shard}: {i}/{len(items)} ({time.time() - t0:.0f}s)")
    log(f"shard {shard} done: {len(items)} items in {time.time() - t0:.0f}s")


def cmd_prewarm(args) -> None:
    ensure_rt()
    procs = [subprocess.Popen([sys.executable, __file__, "_prewarm_shard", str(i), str(args.procs)], cwd=ROOT,
                              env=rt_env()) for i in range(args.procs)]
    for p in procs:
        p.wait()


# ----------------------------------------------------------------------------- processes
def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_http(url: str, timeout: float, proc: subprocess.Popen) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def stop(proc: subprocess.Popen | None, name: str) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    log(f"stopped {name} (pid {proc.pid})")


def find_gguf(d: str) -> str | None:
    fs = [f for f in glob.glob(os.path.join(MODELS_DIR, d, "*.gguf"))
          if "mmproj" not in os.path.basename(f).lower() and not os.path.basename(f).lower().startswith("mtp-")]
    fs = [f for f in fs if os.path.exists(f)]
    return sorted(fs)[0] if fs else None


def probe_thinking(key: str) -> dict:
    """Does the default chat template think? (direct to our llama-server, not via harness)."""
    out = {}
    q = [{"role": "user", "content": "W którym roku odbyła się bitwa pod Grunwaldem? Odpowiedz krótko."}]
    for name, extra in (("default", {}), ("no_think", json.loads(NO_THINK))):
        try:
            r = httpx.post(f"http://127.0.0.1:{LLM_PORT}/v1/chat/completions",
                           json={"messages": q, "max_tokens": 600, "temperature": 0, **extra}, timeout=180).json()
            m = r["choices"][0]["message"]
            rc = m.get("reasoning_content") or ""
            c = m.get("content") or ""
            out[name] = {"reasoning_chars": len(rc), "think_tag_in_content": "<think>" in c or "</think>" in c,
                         "content": c[:160], "completion_tokens": (r.get("usage") or {}).get("completion_tokens")}
        except Exception as e:
            out[name] = {"error": f"{type(e).__name__}: {e}"}
    return out


DEADLINE = [float("inf")]  # absolute epoch; evals are cut at the sweep deadline


HARNESS_WORKERS = 8   # eval workers = harness LLM_CONCURRENCY for the harness runs
BASE_WORKERS = 16     # raw-base eval workers (one llama-server slot each; base runs alone after the harness phases)


def run_eval(label: str, endpoint: str, extra: list[str], logf, timeout: float, workers: int = HARNESS_WORKERS,
             files: str = DEVSET) -> str | None:
    cmd = [sys.executable, "-u", os.path.join(ROOT, "devset", "eval.py"), "--endpoint", endpoint,
           "--url", f"http://127.0.0.1:{H_PORT}", "--files", files, "--label", label,
           "--workers", str(workers)] + extra
    timeout = max(60.0, min(timeout, DEADLINE[0] - time.time()))
    log(f"eval {label} (timeout {timeout:.0f}s)")
    logf.write(f"\n$ {' '.join(cmd)}\n")
    logf.flush()
    env = dict(os.environ, GIT_SHA="sweep", PYTHONUNBUFFERED="1")
    # stream output line by line into the per-model log (progress is visible while it runs)
    p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    _CHILDREN.append(p)
    lines: list[str] = []
    t0 = time.time()
    import threading
    def pump():
        for line in p.stdout:
            lines.append(line)
            logf.write(line)
            logf.flush()
    th = threading.Thread(target=pump, daemon=True)
    th.start()
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait(timeout=10)
        logf.write(f"\nTIMEOUT after {time.time() - t0:.0f}s\n")
        log(f"eval {label} TIMEOUT")
        return None
    finally:
        if p in _CHILDREN:
            _CHILDREN.remove(p)
    th.join(timeout=10)
    outp = "".join(lines)
    m = re.search(r"per-question results -> (\S+)", outp)
    tail = [l for l in outp.splitlines() if l.startswith(("===", "overall", "latency"))]
    for l in tail:
        log("   " + l)
    return m.group(1) if m else None


# ----------------------------------------------------------------------------- metrics
try:  # reuse eval.py grading for re-grading think-stripped predictions
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("_sweep_eval", os.path.join(ROOT, "devset", "eval.py"))
    _evmod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_evmod)
    _grade = _evmod.grade
except Exception:  # pragma: no cover
    _grade = None


def run_metrics(path: str | None, max_tokens: int | None = None) -> dict | None:
    if not path or not os.path.exists(path):
        return None
    rs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    n = len(rs)
    if not n:
        return None
    # strip <think> blocks that leaked into content (llama-server normally moves them to reasoning_content)
    leaked = 0
    for r in rs:
        pred = r.get("pred") or ""
        if "<think>" in pred or "</think>" in pred:
            leaked += 1
            clean = re.sub(r"<think>.*?(</think>|$)", "", pred, flags=re.S)
            clean = clean.split("</think>")[-1].strip()
            if _grade is not None:
                acc = next((x.get("accept") for x in load_items() if x["id"] == r["id"]), None)
                it = {"type": r["type"], "answer": r["gold"], "accept": acc}
                r.update(_grade(it, clean))
            r["pred"] = clean
    lats = [r["latency_s"] for r in rs if not r.get("error")]
    d = {"n": n, "strict": sum(r["strict"] for r in rs) / n * 100, "extract": sum(r["extract"] for r in rs) / n * 100,
         "lenient": sum(r["lenient"] for r in rs) / n * 100, "errors": sum(1 for r in rs if r.get("error")),
         "empty": sum(1 for r in rs if not (r.get("pred") or "").strip() and not r.get("error")),
         "p50": statistics.median(lats) if lats else None, "run_file": os.path.relpath(path, ROOT),
         "think_leaked": leaked}
    by_type, by_type_s = {}, {}
    for t in sorted({r["type"] for r in rs}):
        sub = [r for r in rs if r["type"] == t]
        by_type[t] = round(sum(r["lenient"] for r in sub) / len(sub) * 100, 1)
        by_type_s[t] = round(sum(r["strict"] for r in sub) / len(sub) * 100, 1)
    d["by_type_lenient"] = by_type
    d["by_type_strict"] = by_type_s
    if d["errors"] > n / 2:  # server died mid-run -> not a measurement
        return None
    if max_tokens:  # base: completion-token stats -> truncation / thinking evidence
        cts = [((r.get("meta") or {}).get("usage") or {}).get("completion_tokens") for r in rs]
        cts = [c for c in cts if isinstance(c, int)]
        if cts:
            d["ct_mean"] = statistics.mean(cts)
            d["ct_capped"] = sum(1 for c in cts if c >= max_tokens - 2)
        thought = 0
        for r in rs:
            c = ((r.get("meta") or {}).get("usage") or {}).get("completion_tokens")
            if isinstance(c, int) and c > len(r.get("pred") or "") / 2.5 + 40:
                thought += 1
        d["thought_q"] = thought
    return d


def load_results() -> dict:
    if os.path.exists(RESULTS_JSON):
        with open(RESULTS_JSON, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_results(res: dict) -> None:
    os.makedirs(SWEEP, exist_ok=True)
    tmp = RESULTS_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.replace(tmp, RESULTS_JSON)


def fmt(x, nd=1):
    return "–" if x is None else f"{x:.{nd}f}"


TYPES = ("abcd", "chrono", "match", "open", "pf")


def write_report_l40s(res: dict) -> None:
    rows = []
    for key, r in res.items():
        b, t, tn = r.get("base"), r.get("kb"), r.get("nokb")
        g_s = (t["strict"] - b["strict"]) if (b and t) else None
        g_l = (t["lenient"] - b["lenient"]) if (b and t) else None
        rows.append((key, r, b, t, tn, g_s, g_l))
    rows.sort(key=lambda x: (x[5] is None, -(x[5] if x[5] is not None else (x[3]["strict"] if x[3] else -1e6))))
    grp = {x["id"]: x.get("group", "?") for x in load_items()}
    groups = ["curriculum", "longtail", "histgeo", "cke"]

    def by_group(m):
        if not m or not m.get("run_file"):
            return {}
        p = m["run_file"] if os.path.isabs(m["run_file"]) else os.path.join(ROOT, m["run_file"])
        rs = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        out = {}
        for g in groups:
            sub = [x for x in rs if grp.get(x["id"]) == g]
            if sub:
                out[g] = 100 * sum(x["lenient"] for x in sub) / len(sub)
        return out

    L = ["# Model sweep on the L40S (devset/tourney160.jsonl)", "",
         f"Updated {time.strftime('%Y-%m-%d %H:%M')} UTC. 160 history items (curriculum 56, long tail 34, historical "
         "geography 25, real CKE 45), same subset as devset/sweep_results.md (Mac). All numbers are % of items.", "",
         f"- **B** = raw untouched base GGUF through the harness `/base` passthrough: question as the only user message, "
         f"no system prompt, temperature 0, max_tokens {BASE_MAX_TOKENS}, chat-template defaults; the hybrid Qwen models "
         "(Qwen3.5-*, Qwen3-1.7B/0.6B/8B) run with thinking OFF (`--chat-template-kwargs enable_thinking=false`).",
         "- **T_kb** = harness defaults + full Wikipedia BM25 KB; **T_nokb** = same with `use_kb=0`. Harness = frozen copy "
         "of the L40S/Mac harness (identical md5 to the Mac sweep's copy), thinking off, retrieval cache on.",
         "- **GAIN_strict** = T_kb strict - B strict, **GAIN_len** = T_kb lenient - B lenient (percentage points). "
         "Sorted by GAIN_strict.",
         "- llama.cpp b11185 CUDA, one model at a time on :18081 (`-c 32768 -np 8 -kvu -fa on`), 8 eval workers, phases "
         "run one after another (kb, nokb, base); p50 = per-item latency in s. The main :18080 Bielik-11B server "
         "shared the GPU.", "",
         "| # | model | params | GB | B_strict | B_len | T_kb strict | T_kb len | T_nokb strict | T_nokb len | GAIN_strict "
         "| GAIN_len | T_kb len per type (abcd/chrono/match/open/pf) | pass>=35% (T_kb s/l) | p50 T_kb | p50 B | notes |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, (key, r, b, t, tn, g_s, g_l) in enumerate(rows, 1):
        notes = []
        if b:
            if b.get("empty"):
                notes.append(f"B empty={b['empty']}")
            if b.get("ct_capped"):
                notes.append(f"B hit {BASE_MAX_TOKENS}-tok cap={b['ct_capped']}")
            if b.get("errors"):
                notes.append(f"B err={b['errors']}")
            if b.get("think_leaked"):
                notes.append(f"B <think> in content={b['think_leaked']} (stripped)")
        for nm, m in (("T_kb", t), ("T_nokb", tn)):
            if m and m.get("errors"):
                notes.append(f"{nm} err={m['errors']}")
        if key in THINKERS:
            notes.append("thinking off")
        elif r.get("thinks") == "yes":
            notes.append("template thinks by default")
        if r.get("note"):
            notes.append(r["note"])
        pt = "/".join(fmt((t.get("by_type_lenient") or {}).get(x), 0) for x in TYPES) if t else "–"
        p35 = (("yes" if t["strict"] >= 35 else "no") + "/" + ("yes" if t["lenient"] >= 35 else "no")) if t else "–"
        L.append(f"| {n} | {key} | {r.get('params', '')} | {fmt(r.get('gb'), 2)} | {fmt(b and b['strict'])} | "
                 f"{fmt(b and b['lenient'])} | {fmt(t and t['strict'])} | {fmt(t and t['lenient'])} | "
                 f"{fmt(tn and tn['strict'])} | {fmt(tn and tn['lenient'])} | **{fmt(g_s)}** | {fmt(g_l)} | {pt} | "
                 f"{p35} | {fmt(t and t['p50'], 2)} | {fmt(b and b['p50'], 2)} | {'; '.join(notes)} |")
    done = [x for x in rows if x[2] and x[3]]
    L += ["", "## Headlines", ""]
    if done:
        bs = max(done, key=lambda x: x[5])
        bl = max(done, key=lambda x: x[6])
        L.append(f"- highest GAIN_strict: **{bs[0]}** {bs[5]:+.1f} pp (T_kb {bs[3]['strict']:.1f} vs B {bs[2]['strict']:.1f})")
        L.append(f"- highest GAIN_len: **{bl[0]}** {bl[6]:+.1f} pp (T_kb {bl[3]['lenient']:.1f} vs B {bl[2]['lenient']:.1f})")
    tk = [x for x in rows if x[3]]
    if tk:
        ts = max(tk, key=lambda x: x[3]["strict"])
        tl = max(tk, key=lambda x: x[3]["lenient"])
        L.append(f"- highest T_kb strict: **{ts[0]}** {ts[3]['strict']:.1f}; highest T_kb lenient: **{tl[0]}** "
                 f"{tl[3]['lenient']:.1f}")
        ok = [x for x in tk if x[3]["strict"] >= 45]
        if ok:
            sm = min(ok, key=lambda x: (PARAMS_B.get(x[0], 99), x[1].get("gb") or 99))
            L.append(f"- smallest model with T_kb strict >= 45%: **{sm[0]}** ({sm[1].get('params')}, "
                     f"{sm[1].get('gb', 0):.2f} GB, T_kb strict {sm[3]['strict']:.1f})")
        else:
            L.append("- no model reached T_kb strict >= 45% yet")
    L += ["", "## Per-type T_kb strict / lenient %", "", "| model | " + " | ".join(TYPES) + " |",
          "|---|" + "---|" * len(TYPES)]
    for key, r, b, t, tn, *_ in rows:
        if t:
            s, l = t.get("by_type_strict") or {}, t.get("by_type_lenient") or {}
            L.append(f"| {key} | " + " | ".join(f"{fmt(s.get(x), 0)} / {fmt(l.get(x), 0)}" for x in TYPES) + " |")
    L += ["", "## Per-type B strict / lenient %", "", "| model | " + " | ".join(TYPES) + " |",
          "|---|" + "---|" * len(TYPES)]
    for key, r, b, t, tn, *_ in rows:
        if b:
            s, l = b.get("by_type_strict") or {}, b.get("by_type_lenient") or {}
            L.append(f"| {key} | " + " | ".join(f"{fmt(s.get(x), 0)} / {fmt(l.get(x), 0)}" for x in TYPES) + " |")
    try:
        L += ["", "## Per-group lenient % (T_kb / B)", "",
              "| model | " + " | ".join(f"T {g}" for g in groups) + " | " + " | ".join(f"B {g}" for g in groups) + " |",
              "|---|" + "---|" * (2 * len(groups))]
        for key, r, b, t, tn, *_ in rows:
            if t:
                tg, bg = by_group(t), by_group(b)
                L.append(f"| {key} | " + " | ".join(fmt(tg.get(g)) for g in groups) + " | "
                         + " | ".join(fmt(bg.get(g)) for g in groups) + " |")
    except Exception as e:  # report must never crash the sweep
        L += ["", f"(per-group section failed: {e})"]
    L += ["", "## Runs", "", "| model | server | B mean completion tokens | wall s | run files |", "|---|---|---|---|---|"]
    for key, r, b, t, tn, *_ in rows:
        files = ", ".join(os.path.basename(m["run_file"]) for m in (b, t, tn) if m and m.get("run_file"))
        L.append(f"| {key} | {r.get('server', '')} | {fmt(b and b.get('ct_mean'), 0)} | {r.get('wall_s', '–')} | {files} |")
    L += ["", "## Thinking probes (non-Qwen models, default template vs enable_thinking=false)", ""]
    for key, r, *_ in rows:
        if r.get("probe"):
            L.append(f"- {key}: " + json.dumps(r["probe"], ensure_ascii=False))
    os.makedirs(os.path.dirname(RESULTS_MD), exist_ok=True)
    tmp = RESULTS_MD + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    os.replace(tmp, RESULTS_MD)


def write_report(res: dict) -> None:
    if L40S:
        return write_report_l40s(res)
    rows = []
    for key, r in res.items():
        b, t, tn = r.get("base"), r.get("kb"), r.get("nokb")
        o_s = o_l = None
        if b and t:
            o_s = 0.8 * t["strict"] - 0.4 * b["strict"]
            o_l = 0.8 * t["lenient"] - 0.4 * b["lenient"]
        rows.append((key, r, b, t, tn, o_s, o_l))
    rows.sort(key=lambda x: -(x[6] if x[6] is not None else (-1e6 + (x[3]["lenient"] if x[3] else 0))))
    L = ["# Model sweep (\"go lower\") on devset/tourney160.jsonl", "",
         f"Updated {time.strftime('%Y-%m-%d %H:%M')}. 160 history items (curriculum 56, long tail 34, historical "
         "geography 25, real CKE 45). B = raw untouched base via /base (no system prompt, max_tokens "
         f"{BASE_MAX_TOKENS}, template default; hybrid-thinking Qwen models: thinking OFF, see 'base thinks'). "
         "T = harness defaults (frozen copy), thinking off. Latencies are under heavy shared-GPU load "
         "(3 other llama-servers active) and concurrent phases -> only relative. "
         "obj_s = 0.8*T_strict - 0.4*B_strict, obj_l = 0.8*T_len - 0.4*B_len (percentage points; gain term "
         "counted as 0.4*(T-B) + 0.4*T final). Sorted by obj_l.", "",
         "| model | params | GB | B_strict | B_len | T_kb strict | T_kb len | T_nokb | gain T-B_len | obj_s | obj_l "
         "| harness p50 s | raw p50 s | base thinks | pass>=35% (T strict/len) | notes |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, r, b, t, tn, o_s, o_l in rows:
        think = r.get("thinks")
        notes = []
        if b:
            if b.get("empty"):
                notes.append(f"base empty={b['empty']}")
            if b.get("ct_capped"):
                notes.append(f"base hit cap={b['ct_capped']}")
            if b.get("errors"):
                notes.append(f"base err={b['errors']}")
            if b.get("think_leaked"):
                notes.append(f"base <think> in content={b['think_leaked']} (stripped)")
            if b.get("thought_q") is not None:
                notes.append(f"base thought on {b['thought_q']}/{b['n']}")
        if t and t.get("errors"):
            notes.append(f"kb err={t['errors']}")
        if r.get("note"):
            notes.append(r["note"])
        gain = (t["lenient"] - b["lenient"]) if (b and t) else None
        p35 = (("yes" if t["strict"] >= 35 else "no") + "/" + ("yes" if t["lenient"] >= 35 else "no")) if t else "–"
        L.append(f"| {key} | {r.get('params', '')} | {fmt(r.get('gb'), 2)} | {fmt(b and b['strict'])} | "
                 f"{fmt(b and b['lenient'])} | {fmt(t and t['strict'])} | {fmt(t and t['lenient'])} | "
                 f"{fmt(tn and tn['strict'])} | {fmt(gain)} | {fmt(o_s)} | {fmt(o_l)} | {fmt(t and t['p50'], 2)} | "
                 f"{fmt(b and b['p50'], 2)} | {think if think is not None else '–'} | {p35} | {'; '.join(notes)} |")
    L += ["", "## Per-type T_kb lenient %", "", "| model | abcd | chrono | match | open | pf |", "|---|---|---|---|---|---|"]
    for key, r, b, t, tn, o_s, o_l in rows:
        if t:
            bt = t.get("by_type_lenient", {})
            L.append(f"| {key} | " + " | ".join(fmt(bt.get(x)) for x in ("abcd", "chrono", "match", "open", "pf")) + " |")
    L += ["", "## Per-type B lenient %", "", "| model | abcd | chrono | match | open | pf |", "|---|---|---|---|---|---|"]
    for key, r, b, t, tn, o_s, o_l in rows:
        if b:
            bt = b.get("by_type_lenient", {})
            L.append(f"| {key} | " + " | ".join(fmt(bt.get(x)) for x in ("abcd", "chrono", "match", "open", "pf")) + " |")
    # per-group (curriculum / longtail / histgeo / cke) lenient accuracy from the run files
    try:
        grp = {x["id"]: x.get("group", "?") for x in load_items()}
        groups = ["curriculum", "longtail", "histgeo", "cke"]

        def by_group(m, level="lenient"):
            if not m or not m.get("run_file"):
                return {}
            rs = [json.loads(l) for l in open(os.path.join(ROOT, m["run_file"]), encoding="utf-8") if l.strip()]
            out = {}
            for g in groups:
                sub = [r for r in rs if grp.get(r["id"]) == g]
                if sub:
                    out[g] = 100 * sum(r[level] for r in sub) / len(sub)
            return out
        L += ["", "## Per-group lenient % (T_kb / B)", "",
              "| model | " + " | ".join(f"T {g}" for g in groups) + " | " + " | ".join(f"B {g}" for g in groups) + " |",
              "|---|" + "---|" * (2 * len(groups))]
        for key, r, b, t, tn, o_s, o_l in rows:
            if t:
                tg, bg = by_group(t), by_group(b)
                L.append(f"| {key} | " + " | ".join(fmt(tg.get(g)) for g in groups) + " | "
                         + " | ".join(fmt(bg.get(g)) for g in groups) + " |")
        # Bielik-11B reference on the overlap with the other agent's dev_all runs (current harness, not frozen)
        refs = {}
        for lab in ("integ-devall-bielik-harness-kb", "integ-devall-bielik-harness-nokb", "integ-devall-bielik-base-raw"):
            fs = sorted(glob.glob(os.path.join(ROOT, "devset", "runs", f"*_{lab}.jsonl")))
            if fs:
                refs[lab] = {json.loads(l)["id"]: json.loads(l) for l in open(fs[-1], encoding="utf-8") if l.strip()}
        if refs.get("integ-devall-bielik-harness-kb"):
            ov = set(refs["integ-devall-bielik-harness-kb"]) & set(grp)
            L += ["", f"## Reference: Bielik-11B on the {len(ov)}-item overlap (dev-a/b/c curriculum items of "
                      "tourney160 that are also in dev_all; other agent's integ-devall-* runs, current harness)", "",
                  "| system | strict | lenient |", "|---|---|---|"]
            for lab, d in refs.items():
                sub = [d[i] for i in ov if i in d]
                if sub:
                    L.append(f"| bielik-11b {lab.replace('integ-devall-bielik-', '')} | "
                             f"{100 * sum(x['strict'] for x in sub) / len(sub):.1f} | "
                             f"{100 * sum(x['lenient'] for x in sub) / len(sub):.1f} |")
            for key, r, b, t, tn, o_s, o_l in rows:
                for nm, m in (("harness-kb", t), ("harness-nokb", tn), ("base-raw", b)):
                    if m and m.get("run_file"):
                        rs = [json.loads(l) for l in open(os.path.join(ROOT, m["run_file"]), encoding="utf-8")
                              if l.strip()]
                        sub = [x for x in rs if x["id"] in ov]
                        if sub:
                            L.append(f"| {key} {nm} | {100 * sum(x['strict'] for x in sub) / len(sub):.1f} | "
                                     f"{100 * sum(x['lenient'] for x in sub) / len(sub):.1f} |")
    except Exception as e:  # report must never crash the sweep
        L += ["", f"(per-group section failed: {e})"]
    L += ["", "## Thinking probes", ""]
    for key, r, *_ in rows:
        if r.get("probe"):
            L.append(f"- {key}: " + json.dumps(r["probe"], ensure_ascii=False))
    with open(RESULTS_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


# ----------------------------------------------------------------------------- main loop
_CHILDREN: list[subprocess.Popen] = []


def _on_term(signum, frame):
    # newest first: eval clients die before the servers, so a killed run never writes an all-errors result
    for p in reversed(list(_CHILDREN)):
        try:
            stop(p, "child")
        except Exception:
            pass
    sys.exit(1)


def sweep_one(idx: int, key: str, d: str, params: str, fam: str, gguf: str, res: dict, do_nokb: bool) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    rec = res.get(key, {})
    rec.update({"params": params, "family": fam, "gguf": gguf if L40S else os.path.relpath(gguf, ROOT),
                "gb": os.path.getsize(os.path.realpath(gguf)) / 1e9})
    rec.pop("note", None)
    tag = f"sweep-{LABEL_PREFIX}-{key}" if L40S else f"sweep-{key}"
    logf = open(os.path.join(LOG_DIR, f"{tag}.log"), "a", encoding="utf-8")
    llama = harness = None
    try:
        for p in (LLM_PORT, H_PORT):
            assert p not in FORBIDDEN_PORTS
            if port_open(p):
                raise RuntimeError(f"port {p} already in use")
        t0 = time.time()
        # Throughput on the shared GPU: 16 slots over one UNIFIED KV cache (-kvu) so the raw-base eval can run
        # 16-wide; every sequence still gets >= the 4096-token slot of "-c 16384 -np 4". Greedy decoding, so
        # the slot count changes speed, not answers. Big (>=7B) models: 8 slots, 16k cache (memory).
        big = idx >= 14
        ctx, npar = ("16384", "8") if big else ("32768", "16")
        if L40S:  # 46 GB GPU: 8 slots over a 32k unified KV for every model (>= 4k per slot even when all 8 are busy)
            ctx, npar = "32768", "8"
        rec["server"] = f"-c {ctx} -np {npar} -kvu" + (" " + " ".join(LLAMA_FLAGS) if LLAMA_FLAGS else "")
        think_off = key in THINKERS
        extra_srv = ["--chat-template-kwargs", json.dumps({"enable_thinking": False})] if think_off else []
        if think_off:
            rec["server"] += " --chat-template-kwargs enable_thinking=false"
        llama = subprocess.Popen([LLAMA, "-m", gguf, "--host", "127.0.0.1", "--port", str(LLM_PORT), "-ngl", "999",
                                  "-c", ctx, "-np", npar, "-kvu", "--jinja", "--alias", key] + LLAMA_FLAGS + extra_srv,
                                 cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT)
        _CHILDREN.append(llama)
        if not wait_http(f"http://127.0.0.1:{LLM_PORT}/health", 600, llama):
            raise RuntimeError("llama-server failed to become healthy")
        log(f"{key}: llama-server up in {time.time() - t0:.0f}s (pid {llama.pid})")
        if think_off:
            rec["thinks"] = "yes (template default); base run with thinking OFF"
        else:
            if not rec.get("probe"):
                rec["probe"] = probe_thinking(key)
            pr = rec["probe"].get("default", {})
            rec["thinks"] = "yes" if (pr.get("reasoning_chars") or pr.get("think_tag_in_content")) else "no"
            log(f"{key}: probe {json.dumps(rec['probe'], ensure_ascii=False)[:300]}")
        henv = rt_env({"HARNESS_HOST": "127.0.0.1", "HARNESS_PORT": str(H_PORT),
                       "LLM_BASE_URL": f"http://127.0.0.1:{LLM_PORT}/v1", "LLM_MODEL": key,
                       "LLM_EXTRA_BODY": NO_THINK, "LLM_CONCURRENCY": str(HARNESS_WORKERS),
                       "REQUEST_LOG": os.path.join(LOG_DIR, f"sweep-{LABEL_PREFIX}-harness-requests.jsonl")})
        harness = subprocess.Popen([sys.executable, "-m", "harness"], cwd=RT, env=henv, stdout=logf,
                                   stderr=subprocess.STDOUT)
        _CHILDREN.append(harness)
        if not wait_http(f"http://127.0.0.1:{H_PORT}/health", 180, harness):
            raise RuntimeError("harness failed to become healthy")
        h = httpx.get(f"http://127.0.0.1:{H_PORT}/health", timeout=5).json()
        rec["harness_kb"] = (h.get("kb") or {})
        log(f"{key}: harness up, kb={rec['harness_kb']}")

        # kb/nokb run concurrently (they share the harness' 8 LLM slots); the raw base runs after them, 16-wide.
        # Greedy decoding -> answers do not depend on concurrency; latencies are "under load" numbers.
        # Phases already present in results.json are skipped (idempotent restarts).
        import threading
        lock = threading.Lock()
        phases = []
        P = LABEL_PREFIX
        if not rec.get("kb"):
            phases.append(("kb", f"{P}-{key}-harness-kb", "answer", [], 2400, HARNESS_WORKERS, None))
        if not rec.get("base"):
            phases.append(("base", f"{P}-{key}-base-raw" + ("-nothink" if think_off and BASE_NOTHINK_SUFFIX else ""),
                           "base", ["--max-tokens", str(BASE_MAX_TOKENS)], 3000,
                           HARNESS_WORKERS if L40S else BASE_WORKERS, BASE_MAX_TOKENS))
        if do_nokb and not rec.get("nokb"):
            phases.append(("nokb", f"{P}-{key}-harness-nokb", "answer", ["--cfg", "use_kb=0"], 2400,
                           HARNESS_WORKERS, None))

        def run_phase(ph):
            name, label, ep, extra, tmo, workers, mt = ph
            with open(os.path.join(LOG_DIR, f"{tag}-{name}.log"), "a", encoding="utf-8") as plog:
                path = run_eval(label, ep, extra, plog, tmo, workers=workers)
            m = run_metrics(path, mt)
            with lock:
                if m:
                    rec[name] = m
                res[key] = rec
                save_results(res)
                write_report(res)
            log(f"{key}: phase {name} done: " + (f"strict={m['strict']:.1f} lenient={m['lenient']:.1f} "
                                                   f"p50={m['p50']}" if m else "NO RESULT"))

        # harness phases (kb, nokb) together; the raw base afterwards ALONE: mixing 1.8k-token harness prompts
        # into the batch stalls every decode step of the long base generations (measured 0.4 tok/s/slot).
        groups = ([ph for ph in phases if ph[0] != "base"], [ph for ph in phases if ph[0] == "base"])
        if SERIAL_PHASES:  # one phase at a time: kb, nokb, base -> latency p50 is not inflated by a parallel phase
            order = {"kb": 0, "nokb": 1, "base": 2}
            groups = tuple([ph] for ph in sorted(phases, key=lambda ph: order[ph[0]]))
        for group in groups:
            ths = [threading.Thread(target=run_phase, args=(ph,), daemon=True) for ph in group]
            for th in ths:
                th.start()
            for th in ths:
                th.join()
        rec["wall_s"] = round(time.time() - t0)
    except Exception as e:
        rec["note"] = f"FAILED: {e}"
        log(f"{key}: FAILED {e}")
    finally:
        stop(harness, "harness")
        stop(llama, "llama-server")
        for p in (harness, llama):
            if p in _CHILDREN:
                _CHILDREN.remove(p)
        logf.close()
        res[key] = rec
        save_results(res)
        write_report(res)


def cmd_run(args) -> None:
    signal.signal(signal.SIGTERM, _on_term)
    ensure_rt()
    deadline = time.time() + args.deadline_min * 60
    DEADLINE[0] = deadline
    only = set(args.only.split(",")) if args.only else None
    queue = [(i, m) for i, m in enumerate(MODELS) if not only or m[0] in only]
    if args.order:
        pos = {k: n for n, k in enumerate(args.order.split(","))}
        queue.sort(key=lambda x: pos.get(x[1][0], 1000 + x[0]))
    res = load_results()
    nokb_keys = set(args.nokb.split(",")) if args.nokb else None

    def want_nokb(i, key):  # --nokb k1,k2 -> only those keys; otherwise every model on L40S, every 3rd on the Mac
        return key in nokb_keys if nokb_keys is not None else (L40S or i % 3 == 0)

    if not args.redo:
        def missing(i, m):
            r = res.get(m[0], {})
            return not r.get("kb") or not r.get("base") or (want_nokb(i, m[0]) and not r.get("nokb"))
        queue = [(i, m) for i, m in queue if missing(i, m)]
    waited = 0
    while queue:
        if time.time() > deadline - args.min_left_min * 60:
            log(f"deadline reached; skipping {[m[0] for _, m in queue]}")
            break
        pick = next(((i, m) for i, m in queue if find_gguf(m[1])), None)
        if pick is None:
            if waited > 1800:
                log(f"gave up waiting for {[m[0] for _, m in queue]}")
                break
            time.sleep(30)
            waited += 30
            continue
        # keep the requested order unless the next model is still downloading
        queue.remove(pick)
        i, (key, d, params, fam) = pick
        gguf = find_gguf(d)
        log(f"=== {key} ({params}) {gguf}")
        sweep_one(i, key, d, params, fam, gguf, res, do_nokb=want_nokb(i, key))
    log("sweep finished")


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "_prewarm_shard":
        prewarm_worker(int(sys.argv[2]), int(sys.argv[3]))
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prewarm")
    p.add_argument("--procs", type=int, default=4)
    p = sub.add_parser("run")
    p.add_argument("--only", default="")
    p.add_argument("--deadline-min", type=float, default=150)
    p.add_argument("--min-left-min", type=float, default=6, help="do not start a model with less time left")
    p.add_argument("--redo", action="store_true")
    p.add_argument("--order", default="", help="comma list of keys to run first, in this order")
    p.add_argument("--nokb", default="", help="comma list of keys that also get the harness-nokb run")
    sub.add_parser("report")
    args = ap.parse_args()
    if args.cmd == "prewarm":
        cmd_prewarm(args)
    elif args.cmd == "run":
        cmd_run(args)
    else:
        write_report(load_results())


if __name__ == "__main__":
    main()
