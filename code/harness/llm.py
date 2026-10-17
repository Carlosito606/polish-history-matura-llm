"""Async client for the llama.cpp OpenAI-compatible server."""
from __future__ import annotations

import asyncio
import json
import logging

import httpx

from .config import Settings

log = logging.getLogger("harness.llm")


class LLM:
    def __init__(self, settings: Settings):
        self.s = settings
        self.client = httpx.AsyncClient(
            base_url=settings.llm_base_url,
            timeout=httpx.Timeout(settings.llm_timeout, connect=10.0),
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            limits=httpx.Limits(max_connections=64, max_keepalive_connections=16),
        )
        self.sem = asyncio.Semaphore(max(1, settings.llm_concurrency))
        if settings.base_llm_base_url != settings.llm_base_url:
            self.base_client = httpx.AsyncClient(base_url=settings.base_llm_base_url,
                                                 timeout=httpx.Timeout(settings.llm_timeout, connect=10.0),
                                                 headers={"Authorization": f"Bearer {settings.llm_api_key}"})
        else:
            self.base_client = self.client
        try:
            self.extra = json.loads(settings.llm_extra_body) if settings.llm_extra_body else {}
        except Exception:
            log.warning("bad LLM_EXTRA_BODY, ignoring")
            self.extra = {}
        self._lora_ids: list[int] | None = None

    async def lora_zero(self) -> dict:
        """Request fields that switch every loaded LoRA adapter off for one request ({} when none is loaded).
        llama-server lists its adapters at GET /lora-adapters; the per-request 'lora' field overrides scales."""
        if self._lora_ids is None:
            ids: list[int] = []
            try:
                base = self.s.llm_base_url.rsplit("/v1", 1)[0]
                r = await self.client.get(base + "/lora-adapters", timeout=5.0)
                if r.status_code == 200 and isinstance(r.json(), list):
                    ids = [int(a["id"]) for a in r.json() if "id" in a]
            except Exception as e:  # no endpoint / not llama-server -> nothing to switch off
                log.info("lora-adapters query failed: %s", e)
            self._lora_ids = ids
        return {"lora": [{"id": i, "scale": 0.0} for i in self._lora_ids]} if self._lora_ids else {}

    async def close(self):
        await self.client.aclose()
        if self.base_client is not self.client:
            await self.base_client.aclose()

    async def chat(self, messages: list[dict], *, max_tokens: int = 32, temperature: float = 0.0,
                   grammar: str | None = None, n: int = 1, stop: list[str] | None = None,
                   seed: int | None = None, **kw) -> dict:
        body: dict = {"model": self.s.llm_model, "messages": messages, "max_tokens": max_tokens,
                      "temperature": temperature, "cache_prompt": True}
        if n > 1:
            body["n"] = n
        if grammar and self.s.use_grammar:
            body["grammar"] = grammar
        if stop:
            body["stop"] = stop
        if seed is not None:
            body["seed"] = seed
        if temperature > 0:
            body.setdefault("top_p", 0.95)
        body.update(self.extra)
        body.update(kw)
        if self.s.no_think_tag and messages and messages[-1].get("role") == "user":
            body["messages"] = messages[:-1] + [{"role": "user", "content": "/no_think\n" + messages[-1]["content"]}]
        async with self.sem:
            r = await self.client.post("/chat/completions", json=body)
        if r.status_code != 200:
            raise RuntimeError(f"LLM HTTP {r.status_code}: {r.text[:500]}")
        return r.json()

    @staticmethod
    def texts(resp: dict) -> list[str]:
        out = []
        for c in resp.get("choices", []):
            m = c.get("message") or {}
            out.append((m.get("content") or c.get("text") or "").strip())
        return out

    # ---- raw passthrough (base model benchmark; BASE_LLM_BASE_URL) ----
    async def passthrough(self, body: dict) -> httpx.Response:
        return await self.base_client.post("/chat/completions", json=body)

    def stream(self, body: dict):
        return self.base_client.stream("POST", "/chat/completions", json=body)

    async def get(self, path: str) -> httpx.Response:
        return await self.base_client.get(path)

    async def health(self) -> bool:
        try:
            base = self.s.llm_base_url.rsplit("/v1", 1)[0]
            r = await self.client.get(base + "/health", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False
