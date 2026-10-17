"""Generate essays for devset/cke-essays.jsonl with one system and save them for grading (evaluation only).

  raw     : POST <url>/v1/chat/completions, the question as the only user message (no system prompt) = B
  harness : POST <url>/answer (QTYPE_V2=1 essay mode), the question only

    python devset/run_essays.py --mode raw --url http://127.0.0.1:18085 --system bielik-4.5b-base
    python devset/run_essays.py --mode harness --url http://127.0.0.1:18005 --system bielik-4.5b-harness

Output devset/runs/essays_<system>.jsonl: one record per essay (id, answer, words, chosen topic, latency, tokens,
retrieval titles); the CKE question text itself is not copied (it stays in the git-ignored devset file).
The question is sent the way the mentor benchmark does: 'Zadanie N (P pkt)' + blank line + the task text.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import time

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORD = re.compile(r"\w+(?:[-–]\w+)*")
# 'WYPRACOWANIE na temat nr 2', 'Temat 3:', 'Wybór tematu: 2.', 'skupiając się na temacie 1', 'wybór tematu 4'
_TOPIC = re.compile(r"(?:WYPRACOWANIE\s+na\s+temat\s+nr|\btema\w*)\s*(?:nr\.?)?\s*[:.]?\s*\**\s*(\d)\b", re.I)


def words(text: str) -> int:
    return len(_WORD.findall(text or ""))


def strip_think(text: str) -> str:
    return text.split("</think>")[-1].strip() if "</think>" in (text or "") else (text or "").strip()


async def one(client: httpx.AsyncClient, args, d: dict, sem: asyncio.Semaphore) -> dict:
    q = f"Zadanie {d['task_no']} ({d['points']} pkt)\n\n{d['question']}" if args.header else d["question"]
    rec = {"id": d["id"], "split": d.get("split"), "formula": d.get("formula"), "points": d.get("points"),
           "system": args.system, "mode": args.mode}
    async with sem:
        t0 = time.time()
        try:
            if args.mode == "raw":
                body = {"model": args.model, "messages": [{"role": "user", "content": q}],
                        "max_tokens": args.max_tokens, "temperature": args.temperature, "seed": 42}
                r = await client.post(args.url.rstrip("/") + "/v1/chat/completions", json=body)
                r.raise_for_status()
                j = r.json()
                ch = j["choices"][0]
                ans = strip_think(ch["message"].get("content") or "")
                u = j.get("usage") or {}
                rec.update(finish=ch.get("finish_reason"), prompt_tokens=u.get("prompt_tokens"),
                           completion_tokens=u.get("completion_tokens"))
            else:
                body = {"question": q, "id": d["id"], "config": json.loads(args.config) if args.config else None}
                r = await client.post(args.url.rstrip("/") + "/answer", json=body)
                r.raise_for_status()
                j = r.json()
                ans = j["answer"]
                e = (j.get("parsed") or {}).get("essay") or {}
                rec.update(qtype=j.get("qtype"), essay=e, finish=e.get("finish"), llm_calls=j.get("llm_calls"),
                           prompt_tokens=j.get("prompt_tokens"), completion_tokens=j.get("completion_tokens"),
                           ctx_titles=[c.get("title") for c in j.get("contexts") or []],
                           harness_latency_ms=j.get("latency_ms"))
            rec["answer"] = ans
            m = _TOPIC.search(ans[:400])
            rec["topic"] = (rec.get("essay") or {}).get("topic") or (m.group(1) if m else None)
            rec["words"] = words(ans)
        except Exception as ex:
            rec.update(answer="", words=0, error=f"{type(ex).__name__}: {ex}"[:300])
        rec["latency_s"] = round(time.time() - t0, 2)
    print(f"  {rec['id']:32s} topic={rec.get('topic')} words={rec['words']:4d} {rec['latency_s']:6.1f}s "
          f"{rec.get('finish') or ''} {rec.get('error') or ''}", flush=True)
    return rec


async def amain(args) -> None:
    with open(args.devset, encoding="utf-8") as f:
        items = [json.loads(ln) for ln in f if ln.strip()]
    if args.ids:
        keep = set(args.ids.split(","))
        items = [d for d in items if d["id"] in keep]
    out = args.out or os.path.join(ROOT, "devset", "runs", f"essays_{args.system}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sem = asyncio.Semaphore(args.workers)
    t0 = time.time()
    async with httpx.AsyncClient(timeout=httpx.Timeout(args.timeout, connect=10.0)) as client:
        recs = await asyncio.gather(*(one(client, args, d, sem) for d in items))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ok = [r for r in recs if not r.get("error")]
    w = [r["words"] for r in ok]
    lat = [r["latency_s"] for r in ok]
    print(f"{args.system}: {len(ok)}/{len(recs)} ok, words mean {statistics.mean(w) if w else 0:.0f} "
          f"median {statistics.median(w) if w else 0:.0f} min {min(w) if w else 0} max {max(w) if w else 0}, "
          f"<300 words: {sum(1 for x in w if x < 300)}, latency mean {statistics.mean(lat) if lat else 0:.1f}s "
          f"max {max(lat) if lat else 0:.1f}s, wall {time.time() - t0:.0f}s -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--devset", default=os.path.join(ROOT, "devset", "cke-essays.jsonl"))
    ap.add_argument("--mode", choices=("raw", "harness"), required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--system", required=True, help="label used in the output file name")
    ap.add_argument("--model", default="x")
    ap.add_argument("--out", default="")
    ap.add_argument("--ids", default="")
    ap.add_argument("--config", default="", help="harness per-request overrides (JSON)")
    ap.add_argument("--max-tokens", type=int, default=1400)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--no-header", dest="header", action="store_false")
    asyncio.run(amain(ap.parse_args()))


if __name__ == "__main__":
    main()
