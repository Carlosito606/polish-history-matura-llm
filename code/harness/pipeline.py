"""RAG answer pipeline: detect type -> retrieve -> prompt (grammar-constrained) -> vote -> normalise."""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import re
import time
from dataclasses import dataclass, field

from . import essay, formats, prompts
from .config import Settings
from .llm import LLM
from .postprocess import (clean_open, majority, parse_letters, parse_match, parse_pairs, parse_pf, parse_sequence,
                          parse_years)
from .qtype import ParsedQuestion, detect, entities, is_essay
from .retrieval import Retriever, retrieve

log = logging.getLogger("harness.pipeline")

CLOSED = {"abcd", "abj", "pf", "chrono", "match", "abcd_parts"}
ALL_TYPES = CLOSED | {"open", "generic", "explain", "essay"}


# ---------------------------------------------------------------- QUERY_REWRITE (v2)
def needs_rewrite(pq: ParsedQuestion, mode: int) -> bool:
    if mode >= 2:
        return True
    if mode == 1:
        return not entities(pq.command or pq.stem or pq.text)
    return False


def rewrite_prompt(pq: ParsedQuestion) -> list[dict]:
    body = (pq.sources[-900:] + "\n\n" + pq.command) if pq.sources else pq.text
    user = ("Zadanie z historii:\n" + body.strip()[:2000] + "\n\n"
            "Napisz 1–2 krótkie zapytania do wyszukiwarki polskiej Wikipedii, które pomogą znaleźć odpowiedź: "
            "słowa kluczowe lub prawdopodobne tytuły artykułów (nazwy wydarzeń, postaci, pojęć). "
            "Każde zapytanie w osobnej linii, bez numeracji i bez komentarzy.")
    return [{"role": "system", "content": "Jesteś asystentem wyszukiwania w polskiej Wikipedii."},
            {"role": "user", "content": user}]


def parse_rewrite(text: str) -> list[tuple[str, str, float]]:
    out = []
    for ln in (text or "").splitlines():
        q = re.sub(r"^\s*(?:[-*•]+|\d{1,2}[.)])\s*", "", ln).strip().strip("\"'„”`").strip()
        if q.lower().startswith(("zapytanie", "query")) and ":" in q:
            q = q.split(":", 1)[1].strip()
        if 3 <= len(q) <= 120 and q.lower() not in {x[1].lower() for x in out}:
            out.append((f"rw{len(out) + 1}", q, 1.0))
        if len(out) >= 2:
            break
    return out


def build_messages(system: str, question: str, contexts: list[dict], instr: str, think: bool = False) -> list[dict]:
    """The exact chat messages sent to the answering LLM (one place; train/build_sft.py reuses it for SFT data)."""
    return [{"role": "system", "content": system},
            {"role": "user", "content": prompts.build_user(question, contexts, instr, think=think)}]


@dataclass
class Result:
    answer: str
    qtype: str
    raw: list[str] = field(default_factory=list)
    contexts: list[dict] = field(default_factory=list)
    queries: list = field(default_factory=list)
    parsed: dict = field(default_factory=dict)
    votes: list = field(default_factory=list)
    latency_ms: int = 0
    llm_calls: int = 0
    kb: bool = False
    mode: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


def apply_overrides(s: Settings, overrides: dict | None) -> Settings:
    if not overrides:
        return s
    fields = {f.name: f.type for f in dataclasses.fields(s)}
    clean = {}
    for k, v in overrides.items():
        if k not in fields:
            continue
        cur = getattr(s, k)
        if isinstance(cur, bool):
            v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
        elif isinstance(cur, int):
            v = int(v)
        elif isinstance(cur, float):
            v = float(v)
        clean[k] = v
    return dataclasses.replace(s, **clean)


def _max_tokens(pq: ParsedQuestion, s: Settings) -> int:
    t = pq.qtype
    if t == "abcd":
        return 3 * max(1, pq.n_select) + 2
    if t == "abj":
        return 4
    if t == "abcd_parts":
        return 6 * max(1, len(pq.parts)) + 4
    if t == "explain":
        return s.explain_max_tokens
    if t == "pf":
        return 5 * max(1, len(pq.statements)) + 8 if pq.statements else 60
    if t == "chrono":
        return 4 * max(1, len(pq.items)) + 4
    if t == "match":
        return 6 * max(1, len(pq.left)) + 4
    if t == "open":
        return s.open_max_tokens
    return s.generic_max_tokens


class Pipeline:
    def __init__(self, settings: Settings, llm: LLM, retriever: Retriever):
        self.s = settings
        self.llm = llm
        self.retriever = retriever

    # ------------------------------------------------------------------ helpers
    def _system(self, extra_system: str | None, s: Settings) -> str:
        sysmsg = prompts.SYSTEM
        if extra_system and s.keep_caller_system:
            sysmsg += "\n\nDodatkowe instrukcje:\n" + extra_system.strip()
        return sysmsg

    async def _gen(self, res: Result, messages, *, max_tokens, grammar, s: Settings, votes: bool,
                   stop=None) -> list[str]:
        """Greedy answer (+ optional sampled votes). Returns raw texts, greedy first."""
        r = await self.llm.chat(messages, max_tokens=max_tokens, temperature=s.temperature, grammar=grammar, stop=stop)
        res.llm_calls += 1
        self._usage(res, r)
        outs = LLM.texts(r)[:1]
        if votes and s.n_votes > 0:
            r2 = await self.llm.chat(messages, max_tokens=max_tokens, temperature=s.vote_temperature,
                                     grammar=grammar, n=s.n_votes, stop=stop)
            res.llm_calls += 1
            self._usage(res, r2)
            outs += LLM.texts(r2)
        return outs

    @staticmethod
    def _usage(res: Result, r: dict):
        u = r.get("usage") or {}
        res.prompt_tokens += int(u.get("prompt_tokens") or 0)
        res.completion_tokens += int(u.get("completion_tokens") or 0)

    # ------------------------------------------------------------------ main
    async def answer(self, question: str, qtype: str | None = None, extra_system: str | None = None,
                     overrides: dict | None = None) -> Result:
        t0 = time.time()
        s = apply_overrides(self.s, overrides)
        v2 = s.qtype_v2 or s.cke_mode  # CKE_MODE builds on the v2 detector (labels, explain, essay)
        forced = qtype if qtype in ALL_TYPES and (v2 or qtype != "essay") else None  # essay = v2 only
        if v2 and forced not in (None, "essay") and is_essay(question):
            forced = "essay"  # a sheet-level type hint ('open') must not squeeze an essay into a short answer
        pq = detect(question, forced, v2=v2)
        res = Result(answer="", qtype=pq.qtype, parsed=pq.to_dict())
        use_kb = s.use_kb and self.retriever.available
        res.kb = use_kb
        if s.cke_mode:  # harness v3 (harness/cke_flow.py); every other path below is unchanged
            from . import cke_flow
            await cke_flow.run(self, res, pq, s, extra_system, use_kb)
        elif pq.qtype == "essay":
            await self._essay(res, pq, s, extra_system, use_kb)
        elif pq.qtype == "pf" and s.pf_mode == "split" and pq.statements:
            await self._pf_split(res, pq, s, extra_system, use_kb)
        else:
            contexts, queries = ([], [])
            if use_kb:
                extra = await self._rewrite(res, pq, s) if s.query_rewrite else None
                contexts, queries = await asyncio.to_thread(retrieve, self.retriever, pq, s, None, extra)
            res.contexts, res.queries = contexts, queries
            if pq.qtype == "chrono" and s.chrono_mode in ("years", "hybrid") and pq.items:
                await self._chrono_years(res, pq, s, extra_system)
            else:
                await self._direct(res, pq, s, extra_system)
        res.latency_ms = int((time.time() - t0) * 1000)
        return res

    async def _rewrite(self, res: Result, pq: ParsedQuestion, s: Settings):
        """QUERY_REWRITE: 1-2 search queries written by the same LLM (no extra model)."""
        if not needs_rewrite(pq, s.query_rewrite):
            return None
        try:
            r = await self.llm.chat(rewrite_prompt(pq), max_tokens=s.rewrite_max_tokens, temperature=0.0)
            res.llm_calls += 1
            self._usage(res, r)
            qs = parse_rewrite((LLM.texts(r) or [""])[0])
        except Exception as e:  # never fail the answer because of the rewrite
            log.warning("query rewrite failed: %s", e)
            return None
        res.parsed["rewrite"] = [q for _, q, _ in qs]
        return qs

    async def _direct(self, res: Result, pq: ParsedQuestion, s: Settings, extra_system):
        think = s.think
        instr = prompts.instruction(pq)
        messages = build_messages(self._system(extra_system, s), pq.text, res.contexts, instr, think=think)
        grammar = None if think else prompts.grammar_for(pq)
        mt = _max_tokens(pq, s) + (s.think_max_tokens if think else 0)
        stop = ["\n"] if (pq.qtype == "open" and not think) else None
        res.mode = "think" if think else ("grammar" if grammar else "free")
        outs = await self._gen(res, messages, max_tokens=mt, grammar=grammar, s=s,
                               votes=(pq.qtype in CLOSED or pq.qtype == "open"), stop=stop)
        res.raw = outs
        ans = self._combine(pq, outs, res)
        if think and ans is None:
            # parsing failed after reasoning -> grammar-constrained retry without reasoning
            user = prompts.build_user(pq.text, res.contexts, instr, think=False)
            messages[-1]["content"] = user
            g = prompts.grammar_for(pq)
            outs2 = await self._gen(res, messages, max_tokens=_max_tokens(pq, s), grammar=g, s=s, votes=False)
            res.raw += outs2
            ans = self._combine(pq, outs2, res)
        res.answer = formats.wrap(ans if ans is not None else formats.render_generic(outs[0] if outs else ""))

    def _combine(self, pq: ParsedQuestion, outs: list[str], res: Result) -> str | None:
        """Parse every output, vote, render canonical string. None if unparsable (think mode)."""
        t = pq.qtype
        if not outs:
            return None
        if t == "abcd":
            labels = [l for l, _ in pq.options]
            parsed = [tuple(sorted(parse_letters(o, labels, pq.n_select, pq.options))) for o in outs]
            valid = [p for p in parsed if p]
            res.votes = ["".join(p) for p in parsed]
            if not valid:
                return None
            win = majority(valid)
            return formats.render_abcd(list(win))
        if t == "abj":
            parsed = []
            for o in outs:
                a = parse_letters(o, [l for l, _ in pq.options], 1)
                j = parse_sequence(o, [l for l, _ in pq.justifications])[:1] if pq.justifications else []
                if a and j and any(ch.isdigit() for ch in o):
                    parsed.append((a[0], j[0]))
            res.votes = ["".join(p) for p in parsed]
            if not parsed:
                return None
            c, j = majority(parsed)
            return formats.render_abj(c, j)
        if t == "pf":
            n = len(pq.statements)
            parsed = [parse_pf(o, n) for o in outs]
            parsed = [p for p in parsed if p]
            res.votes = ["".join("P" if v else "F" for v in p) for p in parsed]
            if not parsed:
                return None
            if n:
                final = [majority([p[i] for p in parsed if len(p) > i]) for i in range(n)]
            else:
                final = parsed[0]
            return formats.render_pf(final, [l for l, _ in pq.statements] or None)
        if t == "chrono":
            labels = [l for l, _ in pq.items]
            seqs = [parse_sequence(o, labels) for o in outs]
            res.votes = [",".join(q) for q in seqs]
            if len(seqs) == 1:
                return formats.render_chrono(seqs[0])
            # Borda: average position, ties -> greedy order
            pos = {l: sum(q.index(l) for q in seqs) / len(seqs) for l in labels}
            greedy = seqs[0]
            order = sorted(labels, key=lambda l: (pos[l], greedy.index(l)))
            return formats.render_chrono(order)
        if t == "abcd_parts":
            left = [p[0] for p in pq.parts]
            right = [l for l, _ in pq.right]
            parsed = [dict(parse_pairs(o, left, right)) for o in outs]
            res.votes = [",".join(f"{k}{v}" for k, v in p.items()) for p in parsed]
            return formats.render_match([(l, majority([p[l] for p in parsed if l in p])) for l in left])
        if t == "explain":
            return formats.render_explain(outs[0], pq.labels)
        if t == "match":
            left = [l for l, _ in pq.left]
            right = [l for l, _ in pq.right]
            pp = parse_pairs if (left and left[0].isalpha()) else parse_match  # v2 letter -> number
            parsed = [dict(pp(o, left, right)) for o in outs]
            res.votes = [",".join(f"{k}{v}" for k, v in p.items()) for p in parsed]
            final = [(l, majority([p[l] for p in parsed if l in p])) for l in left]
            return formats.render_match(final)
        if t == "open":
            cleaned = [clean_open(o) for o in outs]
            cleaned = [c for c in cleaned if c]
            if not cleaned:
                return None
            norm = [_norm(c) for c in cleaned]
            res.votes = cleaned
            winner = majority(norm)
            chosen = cleaned[norm.index(winner)]
            return formats.render_open(chosen, pq.open_kind)
        return formats.render_generic(outs[0])

    async def _pf_split(self, res: Result, pq: ParsedQuestion, s: Settings, extra_system, use_kb):
        sub = dataclasses.replace(s, ctx_tokens=max(600, s.ctx_tokens // 2), top_k=max(2, s.top_k // 2))
        stem = pq.stem
        res.mode = "pf-split"

        async def one(label: str, stmt: str):
            ctx = []
            if use_kb:
                qs = [("item:" + label, stmt, 1.0), ("stem", f"{stem} {stmt}", 0.7)]
                ents = entities(stmt)
                if ents:
                    qs.append(("ents", " ".join(ents[:8]), 0.5))
                ctx, _ = await asyncio.to_thread(retrieve, self.retriever, pq, sub, qs)
            q = f"{stem}\n\nZdanie: {stmt}"
            messages = build_messages(self._system(extra_system, s), q, ctx, prompts.instruction_pf_single())
            outs = await self._gen(res, messages, max_tokens=2, grammar=prompts.grammar_pf_single(), s=s, votes=True)
            vals = [parse_pf(o, 1)[0] for o in outs if o]
            return majority(vals) if vals else True, outs, ctx

        results = await asyncio.gather(*(one(l, st) for l, st in pq.statements))
        vals = [r[0] for r in results]
        res.raw = [" | ".join(r[1]) for r in results]
        seen = set()
        for r in results:
            for c in r[2]:
                k = (c["title"], c["text"][:80])
                if k not in seen:
                    seen.add(k)
                    res.contexts.append(c)
        res.votes = ["".join("P" if v else "F" for v in vals)]
        res.answer = formats.wrap(formats.render_pf(vals, [l for l, _ in pq.statements]))

    async def _essay(self, res: Result, pq: ParsedQuestion, s: Settings, extra_system, use_kb):
        """Essay mode (harness/essay.py): retrieve for every topic, write ONE essay on the best-covered topic."""
        res.mode = "essay"
        topics = pq.topics or [("1", pq.text)]
        plans = [essay.plan(n, t, pq.text) for n, t in topics]
        es = dataclasses.replace(s, ctx_tokens=s.essay_ctx_tokens, top_k=s.essay_top_k, rerank_keep=s.essay_top_k,
                                 rerank_topn=max(s.rerank_topn, s.essay_rerank_topn), rerank_item_slots=True)
        if use_kb:
            got = await asyncio.gather(*(asyncio.to_thread(retrieve, self.retriever, p.pq, es, p.queries)
                                         for p in plans))
            for p, (ctx, _) in zip(plans, got):
                p.contexts = ctx
                p.score, p.coverage = essay.coverage(p, ctx)
            chosen = essay.choose(plans, s.essay_topic)
        else:
            chosen = essay.choose_no_kb(plans, s.essay_topic)
        res.contexts, res.queries = chosen.contexts, chosen.queries
        sysmsg = essay.SYSTEM
        if extra_system and s.keep_caller_system:
            sysmsg += "\n\nDodatkowe instrukcje:\n" + extra_system.strip()
        kw: dict = {"repeat_penalty": s.essay_repeat_penalty, "repeat_last_n": 256, "seed": 42}
        if s.essay_dry_multiplier > 0:
            kw.update(dry_multiplier=s.essay_dry_multiplier, dry_allowed_length=s.essay_dry_allowed)
        if s.essay_lora_off:
            kw.update(await self.llm.lora_zero())

        async def gen(messages, max_tokens: int = 0) -> tuple[str, str]:
            r = await self.llm.chat(messages, max_tokens=max_tokens or s.essay_max_tokens,
                                    temperature=s.essay_temperature, **kw)
            res.llm_calls += 1
            self._usage(res, r)
            ch = (r.get("choices") or [{}])[0]
            return (LLM.texts(r) or [""])[0], ch.get("finish_reason") or ""

        ctx = list(chosen.contexts)
        while True:  # context overflow on a small slot -> halve the chunks and retry
            messages = [{"role": "system", "content": sysmsg},
                        {"role": "user", "content": essay.build_user(chosen, ctx)}]
            try:
                raw, fin = await gen(messages)
                break
            except RuntimeError as e:
                if ctx and ("context" in str(e).lower() or "HTTP 400" in str(e)):
                    log.warning("essay prompt too long (%d chunks): %s", len(ctx), str(e)[:120])
                    ctx = ctx[: len(ctx) // 2]
                    continue
                raise
        res.contexts = ctx
        text = essay.clean(raw, chosen.n, truncated=(fin == "length"))
        res.raw = [raw]
        words = first_words = essay.body_words(text)
        expanded = False
        if words < s.essay_min_words and s.essay_fallback in ("sections", "rewrite"):
            try:
                if s.essay_fallback == "sections":  # part by part, each call sees the text written so far
                    parts: list[str] = []
                    for kind, instr, mt in essay.section_steps(chosen):
                        m2 = [{"role": "system", "content": sysmsg},
                              {"role": "user", "content": essay.build_section_user(chosen, ctx, parts, instr)}]
                        raw_k, _ = await gen(m2, max_tokens=mt)
                        res.raw.append(f"[{kind}] {raw_k}")
                        part = essay.clean_part(raw_k, kind)
                        if part:
                            parts.append(part)
                    text2 = essay.clean("\n\n".join(parts), chosen.n)  # cross-paragraph repeats
                else:
                    messages2 = messages + [{"role": "assistant", "content": raw},
                                            {"role": "user", "content": essay.expand_message(chosen, words)}]
                    raw2, fin2 = await gen(messages2)
                    res.raw.append(raw2)
                    text2 = essay.clean(raw2, chosen.n, truncated=(fin2 == "length"))
                if essay.body_words(text2) > words:
                    text, words, expanded = text2, essay.body_words(text2), s.essay_fallback
            except Exception as e:  # keep the first essay
                log.warning("essay fallback failed: %s", e)
        res.parsed["essay"] = {
            "topic": chosen.n, "aspects": chosen.aspects, "thesis": chosen.thesis, "words": words,
            "words_first": first_words, "expanded": expanded, "finish": fin, "n_ctx": len(ctx), "lora_off": bool(kw.get("lora")),
            "topics": [{"n": p.n, "score": p.score, **p.coverage} for p in plans],
        }
        res.answer = formats.wrap(formats.render_essay(text))

    async def _chrono_years(self, res: Result, pq: ParsedQuestion, s: Settings, extra_system):
        """Ask for the year of each item (grammar), sort by year. 'hybrid' also asks for the direct order
        and uses it to break ties / fill unknown years."""
        from . import v4
        if v4.chrono_bc_mode(s) or v4.chrono_ties_mode(s) or v4.on(s, "v4_neutral_examples"):
            from . import v4_flow  # harness v4 (every flag off -> the code below, unchanged)
            return await v4_flow.chrono_years(self, res, pq, s, extra_system)
        hybrid = s.chrono_mode == "hybrid"
        res.mode = "chrono-" + s.chrono_mode
        labels = [l for l, _ in pq.items]
        sysmsg = self._system(extra_system, s)
        messages = build_messages(sysmsg, pq.text, res.contexts, prompts.instruction_chrono_years(pq))
        tasks = [self._gen(res, messages, max_tokens=8 * len(labels) + 4, grammar=prompts.grammar_years(pq),
                           s=s, votes=True)]
        if hybrid:
            tasks.append(self._gen(res, build_messages(sysmsg, pq.text, res.contexts, prompts.instruction(pq)),
                                   max_tokens=_max_tokens(pq, s), grammar=prompts.grammar_for(pq), s=s, votes=False))
        got = await asyncio.gather(*tasks)
        outs = got[0]
        direct = parse_sequence(got[1][0], labels) if hybrid and got[1] else labels
        res.raw = outs + (got[1] if hybrid else [])
        yrs = [parse_years(o, labels) for o in outs]
        # median year per label across votes
        final_years = {}
        for l in labels:
            vals = sorted(y[l] for y in yrs if l in y)
            final_years[l] = vals[len(vals) // 2] if vals else None
        known = [final_years[l] for l in labels if final_years[l] is not None]
        for l in labels:  # unknown year -> place by direct order position (hybrid) or at the end
            if final_years[l] is None:
                final_years[l] = 99999 if not known else max(known) + 1
        res.votes = [str(y) for y in yrs]
        order = sorted(labels, key=lambda l: (final_years[l], direct.index(l)))
        res.parsed["years"] = final_years
        res.answer = formats.wrap(formats.render_chrono(order))


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).replace("ł", "l")
    return " ".join("".join(ch if ch.isalnum() else " " for ch in s).split())
