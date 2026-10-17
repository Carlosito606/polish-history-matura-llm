"""Protocol-agnostic exam runner.

The organisers announce the exact exam procedure only the morning of the exam, so this script
does not assume their upload/run format -- it only assumes our harness is up on :18000. It reads
questions in whatever shape they hand out, POSTs each one at the harness (or at the untouched base
model through the harness's passthrough), and writes graded-ready output files.

Input formats (auto-detected from extension, then sniffed from content):
  .json   a JSON list of question objects, OR an object with a "questions" (or "items"/"data") array
  .jsonl  one JSON question object per line
  .csv    header row with id/question columns (see field-name tolerance below)
  .txt    plain questions separated by one or more blank lines

Field names are tolerant of the organisers' own naming and of Polish column names:
  id      <- id | qid | nr
  question<- question | text | tresc | treść | pytanie
  type    <- type | typ
  points  <- points | pkt

Modes:
  --mode harness (default)  POST {"question": ..., "type": <hint>} -> {url}/answer
  --mode base               POST {"model": ..., "messages":[{"role":"user","content": question}],
                                  "temperature": 0} -> {url}/base/v1/chat/completions
                             (no system prompt; <think>...</think> blocks are stripped from the answer)
  --both                    runs both modes in one invocation, into two suffixed sets of output files

Output (per mode, at --out, e.g. results/run1 -> results/run1_harness.{json,csv,jsonl}):
  <out>.json   {"answers": [{"id", "answer", "raw", "latency_s", "error"}], "meta": {...}}
               (--format simple -> just {"<id>": "<answer>", ...})
  <out>.csv    id,answer
  <out>.jsonl  one line per completed question, written as it finishes (also the resume log)

Resume: if <out>.jsonl already has a (non-error) record for an id, that id is skipped on rerun;
use --no-resume to start over, --resume-errors-too to also skip previously-errored ids.

Examples:
  python -m harness.batch questions.json --mode harness --out results/probny
  python harness/batch.py questions.jsonl --both --concurrency 8 --out results/probny
  python -m harness.batch questions.csv --mode base --max-tokens 128 --out results/probny
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import json
import os
import re
import statistics
import sys
import time
import unicodedata

import httpx

# ----------------------------------------------------------------------------- field-name tolerance
ID_KEYS = ("id", "qid", "nr")
Q_KEYS = ("question", "text", "tresc", "pytanie")
TYPE_KEYS = ("type", "typ")
POINTS_KEYS = ("points", "pkt")

# organisers' 'type' -> our harness/qtype.py kinds (harness/README.md "Question types")
KNOWN_TYPES = {"abcd", "abj", "pf", "chrono", "match", "open", "generic"}
TYPE_ALIASES = {
    "single": "abcd", "choice": "abcd", "abcd": "abcd",
    "truefalse": "pf", "tf": "pf", "pf": "pf",
    "order": "chrono", "chronology": "chrono", "chrono": "chrono",
    "match": "match", "matching": "match",
    "open": "open", "short": "open",
}


def _deaccent(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _norm_key(k: str) -> str:
    return _deaccent((k or "").strip().lower())


def _pick(d: dict, keys: tuple[str, ...]):
    nd = {_norm_key(k): v for k, v in d.items()}
    for k in keys:
        v = nd.get(k)
        if v not in (None, ""):
            return v
    return None


def map_type(raw_type) -> tuple[str | None, str | None]:
    """-> (hint to send to /answer, human-readable note for the log). None hint = let harness auto-detect."""
    if raw_type in (None, ""):
        return None, None
    raw = str(raw_type).strip()
    key = re.sub(r"[^a-z0-9]", "", raw.lower())
    mapped = TYPE_ALIASES.get(key)
    if mapped:
        return mapped, (f"alias:{raw}->{mapped}" if mapped != raw.lower() else None)
    if key in KNOWN_TYPES:
        return key, None
    return raw.lower(), f"unmapped-type:{raw}"


def normalize_record(raw, idx: int) -> dict:
    if isinstance(raw, str):
        return {"id": f"Q{idx:04d}", "question": raw.strip(), "type_raw": None, "points": None}
    if not isinstance(raw, dict):
        raw = {"question": str(raw)}
    qid = _pick(raw, ID_KEYS)
    question = _pick(raw, Q_KEYS)
    typ = _pick(raw, TYPE_KEYS)
    points = _pick(raw, POINTS_KEYS)
    return {"id": str(qid) if qid not in (None, "") else f"Q{idx:04d}",
            "question": str(question or "").strip(), "type_raw": typ, "points": points}


# ----------------------------------------------------------------------------- loaders
def _load_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("questions")
        if items is None:
            items = data.get("items")
        if items is None:
            items = data.get("data")
        if items is None:
            items = [data]  # a single question object
    else:
        raise ValueError(f"{path}: unsupported JSON shape ({type(data).__name__})")
    return [normalize_record(r, i) for i, r in enumerate(items, 1)]


def _load_jsonl(path: str) -> list[dict]:
    items = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return [normalize_record(r, i) for i, r in enumerate(items, 1)]


def _load_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [normalize_record(r, i) for i, r in enumerate(rows, 1)]


_TXT_ID = re.compile(r"^\s*([\w\-]{1,24})\s*[\.\):]\s*(.*)$", re.S)


def _load_txt(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        raw = f.read()
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", raw) if b.strip()]
    items = []
    for i, b in enumerate(blocks, 1):
        m = _TXT_ID.match(b)
        # only treat the leading token as an id if it contains a digit (organisers' ids: H001, dev-a-001, ...)
        # -- otherwise a question that happens to start "Word: ..." would wrongly lose its first word.
        if m and any(ch.isdigit() for ch in m.group(1)) and m.group(2).strip():
            items.append({"id": m.group(1), "question": m.group(2).strip(), "type_raw": None, "points": None})
        else:
            items.append({"id": f"T{i:04d}", "question": b, "type_raw": None, "points": None})
    return items


def load_questions(path: str) -> list[dict]:
    ext = os.path.splitext(path)[1].lower()
    loaders = {".json": _load_json, ".jsonl": _load_jsonl, ".csv": _load_csv, ".txt": _load_txt}
    if ext in loaders:
        return loaders[ext](path)
    # unknown extension: sniff
    with open(path, encoding="utf-8-sig", errors="ignore") as f:
        head = f.read(4096).lstrip()
    if head.startswith("[") or head.startswith("{"):
        try:
            return _load_json(path)
        except Exception:
            pass
    first_line = head.splitlines()[0] if head.splitlines() else ""
    if "," in first_line:
        try:
            return _load_csv(path)
        except Exception:
            pass
    try:
        return _load_jsonl(path)
    except Exception:
        return _load_txt(path)


# ----------------------------------------------------------------------------- think-stripping (base mode)
_THINK_CLOSED = re.compile(r"<think>.*?</think>", re.S | re.I)
_THINK_OPEN = re.compile(r"<think>.*$", re.S | re.I)


def strip_think(text: str) -> str:
    text = _THINK_CLOSED.sub("", text or "")
    text = _THINK_OPEN.sub("", text)
    return text.strip()


# ----------------------------------------------------------------------------- calling
async def call_harness(client: httpx.AsyncClient, url: str, item: dict, type_hint: str | None) -> tuple[str, str]:
    body = {"question": item["question"], "id": item["id"]}
    if type_hint:
        body["type"] = type_hint
    r = await client.post(f"{url}/answer", json=body)
    r.raise_for_status()
    d = r.json()
    return str(d.get("answer") or ""), json.dumps(d.get("raw"), ensure_ascii=False) if not isinstance(d.get("raw"), str) else d.get("raw", "")


async def call_base(client: httpx.AsyncClient, url: str, item: dict, model: str, max_tokens: int) -> tuple[str, str]:
    body = {"model": model, "messages": [{"role": "user", "content": item["question"]}],
            "temperature": 0, "max_tokens": max_tokens}
    r = await client.post(f"{url}/base/v1/chat/completions", json=body)
    r.raise_for_status()
    d = r.json()
    raw = d["choices"][0]["message"].get("content") or ""
    return strip_think(raw), raw


# ----------------------------------------------------------------------------- run
async def process_one(client, url, item, args, sem, log_lock, log_f) -> dict:
    type_hint, type_note = (None, None)
    if args.mode == "harness":
        type_hint, type_note = map_type(item.get("type_raw"))
    t0 = time.time()
    answer, raw, err = "", "", None
    async with sem:
        try:
            async with asyncio.timeout(args.timeout):
                if args.mode == "harness":
                    answer, raw = await call_harness(client, url, item, type_hint)
                else:
                    answer, raw = await call_base(client, url, item, args.base_model, args.max_tokens)
        except asyncio.TimeoutError:
            err = f"timeout>{args.timeout}s"
        except httpx.HTTPStatusError as e:
            err = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
        except Exception as e:  # noqa: BLE001 - fallback answer must never crash the batch
            err = f"{type(e).__name__}: {e}"
    lat = round(time.time() - t0, 3)
    rec = {"id": item["id"], "answer": answer, "raw": raw, "latency_s": lat, "error": err}
    if type_note:
        rec["type_note"] = type_note
    async with log_lock:
        log_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log_f.flush()
    mark = "ERR" if err else "OK "
    print(f"[{mark}] {item['id']:<14} {lat:6.2f}s  {(err or answer)[:80]!r}", flush=True)
    return rec


def load_done(jsonl_path: str, skip_errors_too: bool) -> dict[str, dict]:
    done = {}
    if not os.path.exists(jsonl_path):
        return done
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("id") is None:
                continue
            if rec.get("error") and not skip_errors_too:
                continue  # will be retried
            done[rec["id"]] = rec
    return done


async def run_mode(items: list[dict], args, mode: str, out_prefix: str) -> dict:
    url = args.url.rstrip("/")
    json_path, csv_path, jsonl_path = out_prefix + ".json", out_prefix + ".csv", out_prefix + ".jsonl"
    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)

    ns = argparse.Namespace(**vars(args))
    ns.mode = mode

    done = {} if args.no_resume else load_done(jsonl_path, args.resume_errors_too)
    if args.no_resume and os.path.exists(jsonl_path):
        os.remove(jsonl_path)
    todo = [it for it in items if it["id"] not in done]
    print(f"[{mode}] {len(items)} questions, {len(done)} already done (resume), {len(todo)} to run "
          f"(concurrency={args.concurrency}, timeout={args.timeout}s)")

    started = dt.datetime.now().isoformat(timespec="seconds")
    t_start = time.time()
    sem = asyncio.Semaphore(max(1, args.concurrency))
    log_lock = asyncio.Lock()
    new_recs: list[dict] = []
    if todo:
        async with httpx.AsyncClient(timeout=httpx.Timeout(args.timeout + 10.0, connect=10.0)) as client:
            with open(jsonl_path, "a", encoding="utf-8") as log_f:
                tasks = [process_one(client, url, it, ns, sem, log_lock, log_f) for it in todo]
                new_recs = await asyncio.gather(*tasks)
    finished = dt.datetime.now().isoformat(timespec="seconds")
    wall = time.time() - t_start

    by_id = dict(done)
    for r in new_recs:
        by_id[r["id"]] = r
    answers = [by_id[it["id"]] for it in items if it["id"] in by_id]

    errors = sum(1 for a in answers if a.get("error"))
    lats = [a["latency_s"] for a in answers if not a.get("error")]
    meta = {"mode": mode, "model": args.base_model if mode == "base" else args.model_label, "url": url,
            "started": started, "finished": finished, "n": len(answers), "errors": errors,
            "avg_latency_s": round(statistics.mean(lats), 3) if lats else None, "wall_s": round(wall, 1),
            "input_file": os.path.basename(args.questions_file)}

    if args.format == "simple":
        out_json = {a["id"]: a["answer"] for a in answers}
    else:
        out_json = {"answers": [{"id": a["id"], "answer": a["answer"], "raw": a.get("raw"),
                                  "latency_s": a["latency_s"], "error": a.get("error")} for a in answers],
                    "meta": meta}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out_json, f, ensure_ascii=False, indent=2)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "answer"])
        for a in answers:
            w.writerow([a["id"], a["answer"]])

    avg_str = f"{meta['avg_latency_s']}s" if meta["avg_latency_s"] is not None else "n/a"
    print(f"[{mode}] done: n={len(answers)} errors={errors} avg_latency={avg_str} "
          f"wall={wall:.1f}s -> {json_path}")
    return meta


async def amain(args) -> int:
    items = load_questions(args.questions_file)
    if args.limit:
        items = items[: args.limit]
    if not items:
        print(f"no questions parsed from {args.questions_file}", file=sys.stderr)
        return 2
    seen = set()
    for it in items:
        if it["id"] in seen:
            print(f"[warn] duplicate id {it['id']!r} in input -- later record wins on resume", file=sys.stderr)
        seen.add(it["id"])

    # one preflight /health check (also reports the effective model, used in meta)
    args.model_label = "unknown"
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            h = (await c.get(f"{args.url.rstrip('/')}/health")).json()
            args.model_label = (h.get("config") or {}).get("llm_model", "unknown")
            print(f"[health] harness ok={h.get('status')} llm_ok={h.get('llm_ok')} model={args.model_label} "
                  f"kb={h.get('kb')}")
    except Exception as e:
        print(f"[warn] /health check failed ({e}); proceeding anyway -- every question may time out", file=sys.stderr)

    modes = ["base", "harness"] if args.both else [args.mode]
    metas = []
    for mode in modes:
        out_prefix = f"{args.out}_{mode}"
        metas.append(await run_mode(items, args, mode, out_prefix))
    total_errors = sum(m["errors"] for m in metas)
    return 1 if total_errors == len(items) and items else 0


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("questions_file", help="JSON / JSONL / CSV / TXT questions file")
    ap.add_argument("--mode", choices=["harness", "base"], default="harness",
                    help="harness = RAG pipeline via /answer; base = untouched model via /base/v1/chat/completions")
    ap.add_argument("--both", action="store_true", help="run --mode base then --mode harness, two output sets")
    ap.add_argument("--url", default=os.environ.get("HARNESS_URL", "http://127.0.0.1:18000"), help="harness base URL")
    ap.add_argument("--out", default=None, help="output prefix (default: results/batch_<timestamp>)")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=120.0, help="per-question timeout in seconds")
    ap.add_argument("--base-model", default="base", help="'model' field sent to /base/v1/chat/completions")
    ap.add_argument("--max-tokens", type=int, default=256, help="max_tokens for --mode base")
    ap.add_argument("--format", choices=["full", "simple"], default="full",
                    help="full = {answers:[...],meta:{...}}; simple = {id: answer}")
    ap.add_argument("--no-resume", action="store_true", help="ignore any existing .jsonl log, start clean")
    ap.add_argument("--resume-errors-too", action="store_true",
                    help="also skip ids whose previous attempt errored (default: those are retried)")
    ap.add_argument("--limit", type=int, default=0, help="only run the first N parsed questions (0 = all)")
    return ap


def main() -> None:
    args = build_argparser().parse_args()
    if not args.out:
        ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        args.out = os.path.join("results", f"batch_{ts}")
    rc = asyncio.run(amain(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
