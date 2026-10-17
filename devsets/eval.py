#!/usr/bin/env python
"""Evaluate an endpoint on devset/*.jsonl and append a row to devset/experiments.csv.

Endpoints:
  answer  -> POST {url}/answer {question}                     (harness, full debug info)
  chat    -> POST {url}/v1/chat/completions                   (harness, OpenAI-compatible)
  base    -> POST {url}/base/v1/chat/completions              (raw LLM via harness passthrough)
  openai  -> POST {url}/chat/completions  (url = any OpenAI base, e.g. http://127.0.0.1:18080/v1)

Grading (three levels, all reported):
  strict   exact match after trivial normalisation (spaces/punctuation/case)
  extract  answer parsed out of free text (letters / P-F sequence / order / pairs); open = exact normalised
  lenient  like extract, plus open answers accepted if gold is contained in prediction (or vice versa)

Examples:
  python devset/eval.py --endpoint answer --label harness-kb
  python devset/eval.py --endpoint answer --cfg use_kb=0 --label harness-nokb
  python devset/eval.py --endpoint base --label base-raw
  python devset/eval.py --endpoint base --base-system "Odpowiadaj krótko." --label base-sys
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import glob
import json
import os
import re
import statistics
import subprocess
import sys
import time
import unicodedata
from collections import defaultdict

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:  # reuse the harness parsers for the 'extract' level
    from harness.postprocess import parse_letters, parse_match, parse_pf  # noqa: E402
except Exception:  # pragma: no cover
    parse_letters = parse_match = parse_pf = None


# ----------------------------------------------------------------------------- normalisation
def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ł", "l")
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(s.split())


def squash(s: str) -> str:
    return re.sub(r"[\s\.,;:\-–—\"'„”()\[\]]+", "", (s or "")).upper()


def gold_labels(gold: str) -> list[str]:
    return re.findall(r"[A-H]|\d{1,2}", gold)


def seq_found(pred: str, labels: list[str]) -> list[str]:
    region = _ans_region(pred)
    is_num = all(l.isdigit() for l in labels)
    pat = r"(?<!\d)(\d{1,2})(?!\d)" if is_num else r"(?<![A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ])([A-H])(?![A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ])"
    out = []
    for m in re.finditer(pat, region):
        if m.group(1) in labels and m.group(1) not in out:
            out.append(m.group(1))
    return out


def _ans_region(text: str) -> str:
    ms = list(re.finditer(r"(odpowied[źz]|answer)\s*(\*\*)?\s*[:\-–]\s*(.*)$", text or "", re.I | re.M))
    if ms and ms[-1].group(3).strip():
        return ms[-1].group(3)
    return text or ""


def yes_no(s: str) -> str:
    """'tak' / 'nie' when the text opens with a yes/no decision ('Tak', 'Rozstrzygnięcie: Nie, ...'), else ''."""
    m = re.match(r"^(?:rozstrzygniecie\s+)?(tak|nie)\b", norm_text(s))
    return m.group(1) if m else ""


def grade(item: dict, pred: str) -> dict:
    t = item["type"]
    gold = item["answer"]
    g = {"strict": False, "extract": False, "lenient": False, "partial": None}
    if t in ("abcd", "abj", "pf", "chrono", "match"):
        g["strict"] = squash(pred) == squash(gold)
    if t == "abcd":
        gl = sorted(gold_labels(gold))
        pl = sorted(parse_letters(pred, list("ABCDEFGH"), len(gl))) if parse_letters else []
        g["extract"] = pl == gl
    elif t == "abj":
        g["extract"] = squash(gold) in squash(_ans_region(pred))[:4]
    elif t == "pf":
        gv = [x == "P" for x in re.findall(r"[PF]", gold.upper())]
        pv = parse_pf(pred, len(gv)) if parse_pf else []
        g["extract"] = pv == gv
        g["partial"] = sum(a == b for a, b in zip(pv, gv)) / max(1, len(gv))
    elif t == "chrono":
        gl = gold_labels(gold)
        g["extract"] = seq_found(pred, gl) == gl
    elif t == "match":
        gp = dict(re.findall(r"(\d{1,2})\s*[-–:]?\s*([A-H])", gold))
        left = list(gp.keys())
        pp = dict(parse_match(pred, left, list("ABCDEFGH"))) if parse_match else {}
        # parse_match fills missing with a default; require explicit presence
        explicit = {l for l in left if re.search(rf"(?<!\d){l}\s*[\-–:→>\.\)]?\s*[A-H]", pred)}
        g["extract"] = all(pp.get(l) == gp[l] and l in explicit for l in left)
        g["partial"] = sum(pp.get(l) == gp[l] for l in left) / max(1, len(left))
    else:  # open / generic
        golds = [gold] + list(item.get("accept") or [])
        pn = norm_text(_ans_region(pred).strip().splitlines()[0] if pred.strip() else "")
        gn = [norm_text(x) for x in golds if x]
        g["strict"] = pn in gn
        g["extract"] = g["strict"]
        full = norm_text(pred)
        # pn inside a gold variant must be a whole-word match: a bare substring test accepted 'Nie' for gold 'Tak'
        # ('nie' is inside 'rozstrzygniecie tak'); a yes/no decision that contradicts the gold's is never lenient
        g["lenient"] = g["strict"] or any(x and (re.search(rf"\b{re.escape(x)}\b", full) or
                                                 (len(pn) >= 3 and re.search(rf"\b{re.escape(pn)}\b", x)))
                                          for x in gn)
        gy, py = yes_no(gold), yes_no(_ans_region(pred) if pred.strip() else "")
        if gy and py and gy != py:
            g["strict"] = g["extract"] = g["lenient"] = False
    if t != "open" and t != "generic":
        g["lenient"] = g["extract"]
    return g


# ----------------------------------------------------------------------------- calling
def call(client: httpx.Client, args, item: dict, cfg: dict) -> tuple[str, dict]:
    q = item["question"]
    if args.endpoint == "answer":
        body = {"question": q, "id": item.get("id")}
        if args.pass_type:
            body["type"] = item["type"]
        if cfg:
            body["config"] = cfg
        r = client.post(f"{args.url}/answer", json=body)
        r.raise_for_status()
        d = r.json()
        return d["answer"], {"qtype": d.get("qtype"), "raw": d.get("raw"), "votes": d.get("votes"),
                             "ctx": [c.get("title") for c in d.get("contexts", [])], "server_ms": d.get("latency_ms"),
                             "prompt_tokens": d.get("prompt_tokens"), "llm_calls": d.get("llm_calls"), "mode": d.get("mode")}
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": q})
    body = {"model": args.model, "messages": messages, "temperature": 0, "max_tokens": args.max_tokens}
    if args.endpoint == "chat":
        if cfg:
            body["harness"] = cfg
        url = f"{args.url}/v1/chat/completions"
    elif args.endpoint == "base":
        url = f"{args.url}/base/v1/chat/completions"
    else:
        url = f"{args.url}/chat/completions"
    r = client.post(url, json=body)
    r.raise_for_status()
    d = r.json()
    content = d["choices"][0]["message"].get("content") or ""
    return content, {"usage": d.get("usage"), "harness": d.get("harness")}


def git_sha() -> str:
    if os.environ.get("GIT_SHA"):
        return os.environ["GIT_SHA"]
    try:
        return subprocess.check_output(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL,
                                       text=True).strip()
    except Exception:
        return "nogit"


def parse_cfg(pairs: list[str]) -> dict:
    out = {}
    for p in pairs or []:
        k, _, v = p.partition("=")
        out[k.strip()] = v.strip()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endpoint", choices=["answer", "chat", "base", "openai"], default="answer")
    ap.add_argument("--url", default=os.environ.get("HARNESS_URL", "http://127.0.0.1:18000"))
    ap.add_argument("--files", nargs="*", default=None, help="jsonl files (default: devset/*.jsonl)")
    ap.add_argument("--label", default="")
    ap.add_argument("--cfg", action="append", default=[], help="harness override key=value (answer/chat endpoints)")
    ap.add_argument("--pass-type", action="store_true", help="send gold type to /answer (skip type detection)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--types", default="", help="comma list of types to keep")
    ap.add_argument("--model", default=os.environ.get("EVAL_MODEL", "wmt-matura-rag"))
    ap.add_argument("--system", "--base-system", dest="system", default="", help="system prompt for chat/base/openai")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--no-csv", action="store_true")
    ap.add_argument("--show", type=int, default=0, help="print N wrong answers")
    args = ap.parse_args()
    args.url = args.url.rstrip("/")

    files = args.files or sorted(glob.glob(os.path.join(ROOT, "devset", "*.jsonl")))
    items = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    it = json.loads(line)
                    it["_file"] = os.path.basename(f)
                    items.append(it)
    if args.types:
        keep = set(args.types.split(","))
        items = [i for i in items if i["type"] in keep]
    if args.limit:
        items = items[: args.limit]
    cfg = parse_cfg(args.cfg)

    client = httpx.Client(timeout=args.timeout)
    server_cfg = {}
    if args.endpoint in ("answer", "chat"):
        try:
            h = client.get(f"{args.url}/health").json()
            c = h.get("config", {})
            server_cfg = {k: c.get(k) for k in ("llm_model", "use_kb", "ctx_tokens", "top_k", "n_votes", "think",
                                                "pf_mode", "chrono_mode", "use_grammar", "temperature")}
            server_cfg["kb_index"] = (h.get("kb") or {}).get("index_dir")
        except Exception as e:
            print(f"[warn] /health failed: {e}")
    server_cfg.update({f"override.{k}": v for k, v in cfg.items()})
    if args.system:
        server_cfg["system"] = args.system[:80]

    results = []
    t_start = time.time()

    def work(it):
        t0 = time.time()
        try:
            pred, meta = call(client, args, it, cfg)
            err = None
        except Exception as e:
            pred, meta, err = "", {}, f"{type(e).__name__}: {e}"
        lat = time.time() - t0
        g = grade(it, pred)
        return {"id": it["id"], "type": it["type"], "era": it.get("era", ""), "points": it.get("points", 1),
                "question": it["question"], "gold": it["answer"], "pred": pred, "latency_s": round(lat, 3),
                "error": err, **g, "meta": meta}

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(work, it) for it in items]
        for i, fu in enumerate(cf.as_completed(futs), 1):
            r = fu.result()
            results.append(r)
            mark = "OK " if r["extract"] else "-- "
            print(f"[{i:3d}/{len(items)}] {mark}{r['id']:<18} {r['latency_s']:6.2f}s  gold={r['gold']!r:<22} "
                  f"pred={r['pred'][:60]!r}" + (f"  ERR {r['error']}" if r["error"] else ""), flush=True)
    wall = time.time() - t_start

    # ----------------------------------------------------------------------- report
    def agg(rs):
        n = len(rs)
        if not n:
            return {}
        return {"n": n,
                "strict": round(sum(r["strict"] for r in rs) / n, 4),
                "extract": round(sum(r["extract"] for r in rs) / n, 4),
                "lenient": round(sum(r["lenient"] for r in rs) / n, 4)}

    results.sort(key=lambda r: r["id"])
    overall = agg(results)
    by_type = {t: agg([r for r in results if r["type"] == t]) for t in sorted({r["type"] for r in results})}
    by_era = {e: agg([r for r in results if r["era"] == e]) for e in sorted({r["era"] for r in results})}
    pts_max = sum(r["points"] for r in results)
    pts_strict = sum(r["points"] for r in results if r["strict"])
    pts_extract = sum(r["points"] for r in results if r["extract"])
    lats = [r["latency_s"] for r in results if not r["error"]]
    avg_lat = statistics.mean(lats) if lats else 0
    p50 = statistics.median(lats) if lats else 0
    p90 = sorted(lats)[int(0.9 * (len(lats) - 1))] if lats else 0
    errors = sum(1 for r in results if r["error"])
    pf_partial = [r["partial"] for r in results if r["type"] == "pf" and r["partial"] is not None]

    print("\n=== {} | endpoint={} | n={} | errors={}".format(args.label or "-", args.endpoint, len(results), errors))
    print(f"overall  strict={overall.get('strict', 0):.3f}  extract={overall.get('extract', 0):.3f}  "
          f"lenient={overall.get('lenient', 0):.3f}")
    print(f"points   strict={pts_strict}/{pts_max}  extract={pts_extract}/{pts_max}")
    for t, a in by_type.items():
        print(f"  type {t:<8} n={a['n']:<3} strict={a['strict']:.2f} extract={a['extract']:.2f} lenient={a['lenient']:.2f}")
    for e, a in by_era.items():
        print(f"  era  {e:<12} n={a['n']:<3} extract={a['extract']:.2f}")
    if pf_partial:
        print(f"  pf per-statement accuracy: {statistics.mean(pf_partial):.3f}")
    print(f"latency  avg={avg_lat:.2f}s p50={p50:.2f}s p90={p90:.2f}s  wall={wall:.1f}s  "
          f"throughput={len(results) / wall * 60:.1f} q/min (workers={args.workers})")
    if args.show:
        wrong = [r for r in results if not r["extract"]][: args.show]
        for r in wrong:
            print(f"\n--- {r['id']} gold={r['gold']!r} pred={r['pred']!r}\n{r['question'][:300]}")

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    runs_dir = os.path.join(ROOT, "devset", "runs")
    os.makedirs(runs_dir, exist_ok=True)
    run_path = os.path.join(runs_dir, f"{ts}_{re.sub(r'[^A-Za-z0-9_.-]+', '_', args.label or args.endpoint)}.jsonl")
    with open(run_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"per-question results -> {run_path}")

    if not args.no_csv:
        csv_path = os.path.join(ROOT, "devset", "experiments.csv")
        header = ["timestamp", "git_sha", "label", "endpoint", "url", "config", "files", "n", "errors",
                  "acc_strict", "acc_extract", "acc_lenient", "points_strict", "points_extract", "points_max",
                  "per_type", "per_era", "pf_partial", "avg_latency_s", "p50_s", "p90_s", "wall_s", "q_per_min",
                  "workers", "run_file"]
        row = [dt.datetime.now().isoformat(timespec="seconds"), git_sha(), args.label, args.endpoint, args.url,
               json.dumps(server_cfg, ensure_ascii=False), ";".join(os.path.basename(f) for f in files), len(results),
               errors, overall.get("strict"), overall.get("extract"), overall.get("lenient"), pts_strict, pts_extract,
               pts_max, json.dumps({t: a["extract"] for t, a in by_type.items()}),
               json.dumps({e: a["extract"] for e, a in by_era.items()}),
               round(statistics.mean(pf_partial), 4) if pf_partial else "", round(avg_lat, 3), round(p50, 3),
               round(p90, 3), round(wall, 1), round(len(results) / wall * 60, 2), args.workers,
               os.path.relpath(run_path, ROOT)]
        new = not os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(header)
            w.writerow(row)
        print(f"appended -> {csv_path}")


if __name__ == "__main__":
    main()
