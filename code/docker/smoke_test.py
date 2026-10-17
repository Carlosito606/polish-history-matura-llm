#!/usr/bin/env python3
"""End-to-end smoke test of the deployed stack (stdlib only; runs on the host or in a container).

  python3 docker/smoke_test.py                                   # harness on 127.0.0.1:18000
  python3 docker/smoke_test.py --url http://127.0.0.1:18050 --raw-url http://127.0.0.1:18051
  python3 docker/smoke_test.py --require-kb --require-llm        # strict (prod)

Checks: harness /health, /v1/models, one matura-style question through the RAG model,
the harness 'base' passthrough, and optionally the raw llama-server port (untouched base).
Exit code 0 = every HTTP call succeeded and answers are non-empty (a wrong answer from a tiny
smoke model is reported but is not a failure).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

QUESTION = (
    "Zadanie. W którym roku książę Mieszko I przyjął chrzest?\n"
    "A. 966\nB. 1000\nC. 1025\nD. 1138\n"
    "Odpowiedz tylko literą."
)
EXPECTED = "A"

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method: str, url: str, body: dict | None = None, timeout: float = 600.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer none"})
    t = time.time()
    with _opener.open(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8")), (time.time() - t) * 1000


def chat(url: str, model: str, max_tokens: int = 16) -> tuple[str, float, dict]:
    resp, ms = call("POST", url.rstrip("/") + "/v1/chat/completions", {
        "model": model, "temperature": 0, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": QUESTION}],
    })
    msg = resp["choices"][0].get("message") or {}
    return (msg.get("content") or resp["choices"][0].get("text") or "").strip(), ms, resp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18000", help="harness base URL")
    ap.add_argument("--raw-url", default="", help="raw llama-server URL (gateway raw port), optional")
    ap.add_argument("--require-kb", action="store_true", help="fail if the KB index is not loaded")
    ap.add_argument("--require-llm", action="store_true", help="fail if harness reports llm_ok=false")
    ap.add_argument("--wait", type=float, default=0, help="seconds to wait for /health to answer")
    a = ap.parse_args()
    fails: list[str] = []

    deadline = time.time() + a.wait
    while True:
        try:
            health, ms = call("GET", a.url.rstrip("/") + "/health", timeout=10)
            break
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            if time.time() > deadline:
                print(f"FAIL /health unreachable: {e}")
                return 2
            time.sleep(3)
    kb = health.get("kb", {})
    print(f"[health] status={health.get('status')} llm_ok={health.get('llm_ok')} kb.available={kb.get('available')} "
          f"index={kb.get('index_dir')} err={kb.get('error')} ({ms:.0f} ms)")
    if a.require_kb and not kb.get("available"):
        fails.append("kb not available")
    if a.require_llm and not health.get("llm_ok"):
        fails.append("llm not ok")

    models, _ = call("GET", a.url.rstrip("/") + "/v1/models", timeout=10)
    ids = [m["id"] for m in models.get("data", [])]
    print(f"[models] {ids}")
    rag_model = ids[0] if ids else "wmt-matura-rag"

    try:
        ans, ms, resp = chat(a.url, rag_model)
        h = resp.get("harness", {})
        ok = ans.strip().upper().startswith(EXPECTED)
        print(f"[rag]  model={rag_model} answer={ans!r} expected={EXPECTED} correct={ok} "
              f"qtype={h.get('qtype')} n_ctx={h.get('n_ctx')} kb={h.get('kb')} ({ms:.0f} ms)")
        if not ans:
            fails.append("empty RAG answer")
    except Exception as e:  # noqa: BLE001
        fails.append(f"rag call failed: {e}")
        print(f"FAIL rag: {e}")

    if len(ids) > 1:
        try:
            ans, ms, _ = chat(a.url, ids[1])
            print(f"[base passthrough] model={ids[1]} answer={ans!r} ({ms:.0f} ms)")
            if not ans:
                fails.append("empty base-passthrough answer")
        except Exception as e:  # noqa: BLE001
            fails.append(f"base passthrough failed: {e}")
            print(f"FAIL base passthrough: {e}")

    if a.raw_url:
        try:
            rm, _ = call("GET", a.raw_url.rstrip("/") + "/v1/models", timeout=10)
            rid = rm["data"][0]["id"]
            ans, ms, _ = chat(a.raw_url, rid)
            print(f"[raw llama-server] model={rid} answer={ans!r} ({ms:.0f} ms)")
            if not ans:
                fails.append("empty raw answer")
        except Exception as e:  # noqa: BLE001
            fails.append(f"raw call failed: {e}")
            print(f"FAIL raw: {e}")

    if fails:
        print("SMOKE FAIL: " + "; ".join(fails))
        return 1
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
