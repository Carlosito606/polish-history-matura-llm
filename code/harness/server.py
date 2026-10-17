"""FastAPI app: OpenAI-compatible RAG endpoint + raw passthrough + debug /answer."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from . import __version__
from .config import SETTINGS
from .llm import LLM
from .pipeline import Pipeline
from .retrieval import Retriever

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("harness.server")

STATE: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    llm = LLM(SETTINGS)
    retriever = Retriever(SETTINGS)
    STATE.update(llm=llm, retriever=retriever, pipeline=Pipeline(SETTINGS, llm, retriever))
    log.info("harness %s up; LLM=%s model=%s KB=%s", __version__, SETTINGS.llm_base_url, SETTINGS.llm_model,
             retriever.status())
    yield
    await llm.close()


app = FastAPI(title="wmt-matura harness", version=__version__, lifespan=lifespan)


def _log_request(rec: dict) -> None:
    path = SETTINGS.request_log
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:  # pragma: no cover
        log.warning("request log failed: %s", e)


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") in (None, "text", "input_text"))
    return str(content or "")


def _extract(messages: list[dict]) -> tuple[str, str | None]:
    """Question = last user message; caller system/developer messages = extra instruction."""
    question, systems = "", []
    for m in messages or []:
        role = m.get("role")
        if role in ("system", "developer"):
            systems.append(_content_text(m.get("content")))
    for m in reversed(messages or []):
        if m.get("role") == "user":
            question = _content_text(m.get("content"))
            break
    return question, ("\n".join(s for s in systems if s.strip()) or None)


def _format_for_response_format(answer: str, rf) -> str:
    """If caller asks for JSON output, wrap the answer into the requested schema's first string field."""
    if not isinstance(rf, dict) or rf.get("type") not in ("json_object", "json_schema"):
        return answer
    key = "answer"
    try:
        schema = (rf.get("json_schema") or {}).get("schema") or rf.get("schema") or {}
        props = schema.get("properties") or {}
        if props:
            key = next(iter(props))
    except Exception:
        pass
    return json.dumps({key: answer}, ensure_ascii=False)


def _completion_payload(model: str, content: str, meta: dict, usage: dict, kind: str = "chat") -> dict:
    cid = ("chatcmpl-" if kind == "chat" else "cmpl-") + uuid.uuid4().hex[:24]
    if kind == "chat":
        choice = {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        obj = "chat.completion"
    else:
        choice = {"index": 0, "text": content, "finish_reason": "stop", "logprobs": None}
        obj = "text_completion"
    return {"id": cid, "object": obj, "created": int(time.time()), "model": model, "choices": [choice],
            "usage": usage, "harness": meta}


def _sse(model: str, content: str):
    cid = "chatcmpl-" + uuid.uuid4().hex[:24]
    now = int(time.time())
    first = {"id": cid, "object": "chat.completion.chunk", "created": now, "model": model,
             "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}]}
    last = {"id": cid, "object": "chat.completion.chunk", "created": now, "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
    yield f"data: {json.dumps(first, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps(last)}\n\n"
    yield "data: [DONE]\n\n"


async def _run(question: str, qtype=None, extra_system=None, overrides=None):
    pipe: Pipeline = STATE["pipeline"]
    return await pipe.answer(question, qtype=qtype, extra_system=extra_system, overrides=overrides)


# ----------------------------------------------------------------------------- endpoints
@app.get("/health")
async def health():
    llm: LLM = STATE["llm"]
    ok = await llm.health()
    return {"status": "ok" if ok else "degraded", "llm_ok": ok, "version": __version__,
            "kb": STATE["retriever"].status(), "config": SETTINGS.public()}


@app.get("/v1/models")
async def models():
    now = int(time.time())
    return {"object": "list", "data": [
        {"id": SETTINGS.public_model_name, "object": "model", "created": now, "owned_by": "wmt-matura"},
        {"id": SETTINGS.base_model_name, "object": "model", "created": now, "owned_by": "wmt-matura"},
    ]}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model") or SETTINGS.public_model_name
    if model == SETTINGS.base_model_name:
        return await _passthrough(body)
    question, extra_system = _extract(body.get("messages") or [])
    overrides = body.get("harness") if isinstance(body.get("harness"), dict) else None
    t0 = time.time()
    try:
        res = await _run(question, qtype=(overrides or {}).get("qtype"), extra_system=extra_system, overrides=overrides)
    except Exception as e:
        log.exception("pipeline failed")
        return JSONResponse(status_code=500, content={"error": {"message": str(e), "type": "harness_error"}})
    content = _format_for_response_format(res.answer, body.get("response_format"))
    meta = {"qtype": res.qtype, "latency_ms": res.latency_ms, "kb": res.kb, "n_ctx": len(res.contexts), "mode": res.mode}
    usage = {"prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
             "total_tokens": res.prompt_tokens + res.completion_tokens}
    _log_request({"ts": time.time(), "endpoint": "chat", "question": question, "extra_system": extra_system,
                  "answer": res.answer, "qtype": res.qtype, "raw": res.raw, "votes": res.votes,
                  "ctx_titles": [c["title"] for c in res.contexts], "latency_ms": int((time.time() - t0) * 1000)})
    if body.get("stream"):
        return StreamingResponse(_sse(model, content), media_type="text/event-stream")
    return _completion_payload(model, content, meta, usage)


@app.post("/v1/completions")
async def completions(request: Request):
    body = await request.json()
    prompt = body.get("prompt") or ""
    if isinstance(prompt, list):
        prompt = prompt[0] if prompt else ""
    res = await _run(prompt, overrides=body.get("harness") if isinstance(body.get("harness"), dict) else None)
    usage = {"prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
             "total_tokens": res.prompt_tokens + res.completion_tokens}
    return _completion_payload(body.get("model") or SETTINGS.public_model_name, res.answer,
                               {"qtype": res.qtype, "latency_ms": res.latency_ms}, usage, kind="text")


async def _passthrough(body: dict):
    llm: LLM = STATE["llm"]
    if body.get("stream"):
        async def gen():
            async with llm.stream(body) as r:
                async for chunk in r.aiter_bytes():
                    yield chunk
        return StreamingResponse(gen(), media_type="text/event-stream")
    r = await llm.passthrough(body)
    return Response(content=r.content, status_code=r.status_code, media_type="application/json")


@app.post("/base/v1/chat/completions")
async def base_chat(request: Request):
    return await _passthrough(await request.json())


@app.get("/base/v1/models")
async def base_models():
    r = await STATE["llm"].get("/models")
    return Response(content=r.content, status_code=r.status_code, media_type="application/json")


@app.post("/answer")
async def answer(request: Request):
    body = await request.json()
    question = body.get("question") or ""
    overrides = body.get("config") if isinstance(body.get("config"), dict) else None
    res = await _run(question, qtype=body.get("type") or None,
                     extra_system=body.get("system"), overrides=overrides)
    out = {"answer": res.answer, "raw": res.raw, "qtype": res.qtype, "votes": res.votes, "mode": res.mode,
           "kb": res.kb, "contexts": res.contexts, "queries": res.queries, "parsed": res.parsed,
           "latency_ms": res.latency_ms, "llm_calls": res.llm_calls,
           "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens}
    _log_request({"ts": time.time(), "endpoint": "answer", "id": body.get("id"), "question": question,
                  "answer": res.answer, "qtype": res.qtype, "raw": res.raw, "votes": res.votes,
                  "ctx_titles": [c["title"] for c in res.contexts], "latency_ms": res.latency_ms,
                  "config": overrides})
    return out
