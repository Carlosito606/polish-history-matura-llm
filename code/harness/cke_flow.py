"""CKE_MODE=1 answer flows (harness v3). Entry point: run(pipe, res, pq, s, extra_system, use_kb).

  closed (abcd, abj, pf, match, abcd_parts) -> reasoning + 'Odpowiedź: ...' (last explicit answer parsed;
                                               grammar-constrained retry only when it cannot be parsed)
  names  ('Fragment A –', 'przyporządkuj władcę', colon-labelled short answers) -> names on ONE line
  decision ('Rozstrzygnij ... uzasadnij') -> per-source who/what/when (separate retrieval per source) ->
            comparison -> variant from the command (yes/no: 'Tak' only if P(Tak) >= CKE_YES_THRESHOLD) ->
            justification naming concrete elements of each cited source
  explain -> concrete content of each indicated source + 1-2 context facts, sheet labels kept
  open / generic -> short reasoning + 'Odpowiedź: ...' (granularity rules)
  essay -> plan, intro with stance, one paragraph per element from its own retrieval, comparison for
           'najbardziej' theses, conclusion, verification against the retrieved passages; ESSAY_SAFE=1: stricter
           date checks (cke_essay.verify_paragraph_safe), plain-year prompts, best of two topics
Every generation sends LoRA scale 0 (per request) unless its qtype is listed in CKE_LORA_TYPES.
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import math
import re
import time

from . import cke, cke_essay, essay, formats, prompts, v4
from .formats import clean_short
from .llm import LLM
from .qtype import KW_DECIDE, ParsedQuestion
from .retrieval import build_queries, retrieve

log = logging.getLogger("harness.cke")

CLOSED = {"abcd", "abj", "pf", "match", "abcd_parts"}


# ------------------------------------------------------------------ plumbing
async def _lora_kw(pipe, s, qtype: str) -> dict:
    keep = {t.strip() for t in (s.cke_lora_types or "").split(",") if t.strip()}
    return {} if qtype in keep else await pipe.llm.lora_zero()


async def _chat(pipe, res, messages, *, max_tokens: int, kw: dict, tag: str = "", temperature: float = 0.0,
                grammar: str | None = None, prefill: str = "", **extra) -> tuple[str, dict]:
    """One LLM call. `prefill` starts the assistant turn (llama-server continues it): 'Rozumowanie:' makes
    Bielik reason BEFORE the answer (without it, it writes 'Odpowiedź: X' first and justifies afterwards)."""
    if prefill:
        messages = list(messages) + [{"role": "assistant", "content": prefill}]
    r = await pipe.llm.chat(messages, max_tokens=max_tokens, temperature=temperature, grammar=grammar,
                            **kw, **extra)
    res.llm_calls += 1
    pipe._usage(res, r)
    txt = (LLM.texts(r) or [""])[0]
    if prefill and not txt.lstrip("*# ").lower().startswith(prefill.strip().lower()):
        body = txt.strip()
        txt = prefill + ("" if body[:1] in ",.;:)" else " ") + body
    res.raw.append(f"[{tag}] {txt}" if tag else txt)
    return txt, r


def _system(pipe, extra_system, s) -> str:
    sysmsg = cke.SYSTEM
    if extra_system and s.keep_caller_system:
        sysmsg += "\n\nDodatkowe instrukcje:\n" + extra_system.strip()
    return sysmsg


def _msgs(system: str, question: str, contexts: list[dict], instr: str) -> list[dict]:
    return [{"role": "system", "content": system},
            {"role": "user", "content": prompts.build_user(question, contexts, instr)}]


async def _retrieve(pipe, pq, s, use_kb, queries=None):
    if not use_kb:
        return [], []
    return await asyncio.to_thread(retrieve, pipe.retriever, pq, s, queries)


def _with_source_queries(pq, s, units) -> list[tuple[str, str, float]]:
    qs = build_queries(pq, v2=s.qtype_v2)
    seen = {q.strip().lower() for _, q, _ in qs}
    for i, (lab, body) in enumerate(units[:4]):
        q = cke.source_query(body)
        if q and q.lower() not in seen:
            qs.append((f"item:src{i + 1}", q, 0.9))
            seen.add(q.lower())
    return qs


# ------------------------------------------------------------------ entry
async def run(pipe, res, pq: ParsedQuestion, s, extra_system, use_kb: bool) -> None:
    src, cmd = cke.fix_command(pq)
    if (src, cmd) != (pq.sources, pq.command):
        pq.sources, pq.command = src, cmd
        res.parsed["cke_command_fixed"] = True
    labels = cke.sheet_labels(pq.command or pq.text)
    kw = await _lora_kw(pipe, s, pq.qtype)
    sysmsg = _system(pipe, extra_system, s)
    res.parsed["cke"] = {"labels": [l for l, _ in labels], "lora_off": bool(kw.get("lora"))}
    if pq.qtype == "essay":
        return await essay_flow(pipe, res, pq, s, extra_system, use_kb, kw)
    names = cke.names_task(pq, labels) if pq.qtype in ("match", "open", "generic", "explain") else []
    if not names and pq.qtype in ("open", "generic") and labels:
        names = labels
    if names:
        return await names_flow(pipe, res, pq, s, sysmsg, use_kb, kw, names)
    if pq.qtype == "abcd_parts" and v4.on(s, "v4_abcd_parts"):  # harness v4 (flag off -> v3 below)
        from . import v4_flow
        return await v4_flow.abcd_parts_flow(pipe, res, pq, s, sysmsg, use_kb, kw)
    if pq.qtype in CLOSED:
        if v4.any_closed(s):
            from . import v4_flow
            return await v4_flow.closed_flow(pipe, res, pq, s, sysmsg, use_kb, kw)
        return await closed_flow(pipe, res, pq, s, sysmsg, use_kb, kw)
    if pq.qtype == "chrono":  # year-grammar path (short, no reasoning) stays as in v2
        res.contexts, res.queries = await _retrieve(pipe, pq, s, use_kb)
        return await pipe._chrono_years(res, pq, s, extra_system)
    wants_just = bool(re.search(r"uzasadni", pq.command or "", re.I))
    if pq.qtype == "explain" and ((labels[:1] and labels[0][0].lower().startswith("rozstrzygni")) or
                                  (KW_DECIDE.search(pq.command or "") and wants_just)):
        return await decision_flow(pipe, res, pq, s, sysmsg, use_kb, kw, labels)
    if pq.qtype == "explain":
        return await explain_flow(pipe, res, pq, s, sysmsg, use_kb, kw, labels)
    return await open_flow(pipe, res, pq, s, sysmsg, use_kb, kw)


# ------------------------------------------------------------------ closed items
_PF_TOK = re.compile(r"(?<![A-Za-ząćęłńóśźż])(P|F|prawda|fałsz)(?![A-Za-ząćęłńóśźż])", re.I)


def complete(pq: ParsedQuestion, region: str) -> bool:
    """Does the final answer line carry an answer for every part?"""
    t = pq.qtype
    if not region.strip():
        return False
    if t == "pf":
        return len(_PF_TOK.findall(region)) >= max(1, len(pq.statements))
    if t == "match":
        return all(re.search(rf"(?<![A-Za-z0-9]){re.escape(l)}\s*[\-–:→>.)]?\s*[A-Z0-9]", region) for l, _ in pq.left)
    if t == "abcd_parts":
        return all(re.search(rf"(?<!\d){re.escape(p[0])}\s*[\-–:.)]?\s*[A-H]", region) for p in pq.parts)
    if t in ("abcd", "abj"):
        return bool(re.search(r"(?<![A-Za-ząćęłńóśźż])[A-H](?![A-Za-ząćęłńóśźż])", region))
    return True


async def closed_flow(pipe, res, pq, s, sysmsg, use_kb, kw):
    res.mode = "cke-closed"
    res.contexts, res.queries = await _retrieve(pipe, pq, s, use_kb)
    messages = _msgs(sysmsg, pq.text, res.contexts, cke.closed_instruction(pq))
    out, _ = await _chat(pipe, res, messages, max_tokens=s.cke_reason_max_tokens, kw=kw, tag="reason",
                         prefill="Rozumowanie:")
    region = cke.final_region(out) if has_answer(out) else ""
    ans = pipe._combine(pq, [region], res) if complete(pq, region) else None
    res.parsed["cke"].update(final=region[:200], fallback=ans is None)
    if ans is None:  # no parsable final line -> grammar-constrained answer, reasoning kept as context
        instr = prompts.instruction(pq)
        m2 = messages + [{"role": "assistant", "content": cke.reasoning_part(out)[:1500]},
                         {"role": "user", "content": instr}]
        out2, _ = await _chat(pipe, res, m2, max_tokens=pipe_max_tokens(pq, s), kw=kw, tag="grammar",
                              grammar=prompts.grammar_for(pq))
        ans = pipe._combine(pq, [out2], res)
    res.answer = formats.wrap(ans if ans is not None else formats.render_generic(region))


def has_answer(text: str) -> bool:
    return bool(cke._ANS.search((text or "").replace("**", "")))


async def _ensure_answer(pipe, res, messages, out: str, kw: dict, fmt: str) -> str:
    """Reasoning without a final 'Odpowiedź:' line (cut by max_tokens) -> one short call for the answer only."""
    if has_answer(out):
        return out
    m2 = list(messages) + [{"role": "assistant", "content": cke.reasoning_part(out)[:1500]},
                           {"role": "user", "content": f"Napisz teraz tylko ostateczną odpowiedź w formacie:\n{fmt}"}]
    ans, _ = await _chat(pipe, res, m2, max_tokens=90, kw=kw, tag="final", prefill="Odpowiedź:")
    return out + "\n" + ans


def pipe_max_tokens(pq, s) -> int:
    from .pipeline import _max_tokens
    return _max_tokens(pq, s)


# ------------------------------------------------------------------ names / labelled short answers
async def names_flow(pipe, res, pq, s, sysmsg, use_kb, kw, labels):
    res.mode = "cke-names"
    units = cke.split_sources(pq.sources)
    res.contexts, res.queries = await _retrieve(pipe, pq, s, use_kb, _with_source_queries(pq, s, units))
    messages = _msgs(sysmsg, pq.text, res.contexts, cke.names_instruction(pq, labels))
    out, _ = await _chat(pipe, res, messages, max_tokens=s.cke_reason_max_tokens, kw=kw, tag="names",
                         prefill="Rozumowanie:")
    out = await _ensure_answer(pipe, res, messages, out, kw,
                               "Odpowiedź: " + "; ".join(f"{l}{sep}…" for l, sep in labels))
    region = cke.final_region(out)
    triples = cke.parse_labeled(region, labels)
    if sum(1 for t in triples if t[2]) < len(labels):  # labels spread over several lines / before 'Odpowiedź'
        alt = cke.parse_labeled(out[out.lower().rfind(labels[0][0].lower()):] if labels[0][0].lower() in out.lower()
                                else out, labels)
        if sum(1 for t in alt if t[2]) > sum(1 for t in triples if t[2]):
            triples = alt
    def bad(v: str) -> bool:  # empty, a reasoning sentence, or cut mid-sentence
        v = v.strip()
        return not v or len(v.split()) > 10 or bool(re.search(r"[,:]$|\b(bo|ponieważ|że|gdyż)$", v))

    if any(bad(t[2]) for t in triples):  # verbose per-item reasoning cut by max_tokens -> answer-only call
        fmt = "; ".join(f"{l}{sep}…" for l, sep in labels)
        m2 = list(messages) + [{"role": "assistant", "content": cke.reasoning_part(out)[:1500]},
                               {"role": "user", "content": "Napisz teraz tylko ostateczną odpowiedź: wszystkie "
                                                           f"elementy w jednej linii, same nazwy, w formacie:\n{fmt}"}]
        ans, _ = await _chat(pipe, res, m2, max_tokens=120, kw=kw, tag="final",
                             prefill=f"Odpowiedź: {labels[0][0]}{labels[0][1]}".rstrip())
        t2 = cke.parse_labeled(cke.final_region(ans), labels)
        if sum(1 for t in t2 if not bad(t[2])) >= sum(1 for t in triples if not bad(t[2])):
            triples, region = t2, cke.final_region(ans)
    if not any(t[2] for t in triples):  # one bare value for one label ('Odpowiedź: Kazimierz Wielki')
        vals = [v.strip() for v in re.split(r"[;,]", region) if v.strip()]
        triples = [(l, sep, vals[i] if i < len(vals) else "") for i, (l, sep) in enumerate(labels)]
    triples = [(l, sep, clean_short(v).lstrip("-–•* ")[:160].rstrip(" .")) for l, sep, v in triples]
    res.parsed["cke"].update(names=[l for l, _ in labels], final=region[:200])
    res.answer = formats.wrap(cke.render_labeled(triples, one_line=True))


# ------------------------------------------------------------------ open / generic
async def open_flow(pipe, res, pq, s, sysmsg, use_kb, kw):
    res.mode = "cke-open"
    res.contexts, res.queries = await _retrieve(pipe, pq, s, use_kb)
    messages = _msgs(sysmsg, pq.text, res.contexts, cke.open_instruction(pq))
    out, _ = await _chat(pipe, res, messages, max_tokens=s.cke_reason_max_tokens, kw=kw, tag="open",
                         prefill="Rozumowanie:")
    out = await _ensure_answer(pipe, res, messages, out, kw, "Odpowiedź: …")
    region = cke.final_region(out)
    first = region.split("\n")[0].strip()
    if pq.qtype == "open":
        ans = formats.render_open(first, pq.open_kind)
    else:
        ans = cke.flatten_prose(region)[:600]
    res.parsed["cke"].update(final=region[:200])
    res.answer = formats.wrap(ans or cke.flatten_prose(out)[:400])


# ------------------------------------------------------------------ explanations
async def explain_flow(pipe, res, pq, s, sysmsg, use_kb, kw, labels):
    res.mode = "cke-explain"
    cmd = pq.command or pq.text
    units = cke.split_sources(pq.sources)
    cited = [c for c, _ in cke.cited_sources(cmd, units)] if cke.mentions_sources(cmd) and units else []
    res.contexts, res.queries = await _retrieve(pipe, pq, s, use_kb, _with_source_queries(pq, s, units))
    messages = _msgs(sysmsg, pq.text, res.contexts, cke.explain_instruction(pq, labels, cited))
    out, _ = await _chat(pipe, res, messages, max_tokens=s.cke_explain_max_tokens, kw=kw, tag="explain")
    res.parsed["cke"].update(cited=cited)
    res.answer = formats.wrap(cke.render_explain_cke(out, labels)[: formats.FORMATS["explain"]["max_chars"]])


# ------------------------------------------------------------------ decisions
def _top_prob(resp: dict, keys: tuple[str, ...]) -> dict:
    """Probabilities of the first generated token for each key ('tak', 'nie') from top_logprobs."""
    out = {k: 0.0 for k in keys}
    try:
        lp = resp["choices"][0]["logprobs"]["content"][0]
        cands = lp.get("top_logprobs") or [lp]
        for c in cands:
            tok = norm_tok(c.get("token", ""))
            for k in keys:
                if tok and (k.startswith(tok) or tok.startswith(k)):
                    out[k] += math.exp(float(c.get("logprob", -99)))
    except Exception:
        return {}
    return out


def norm_tok(t: str) -> str:
    return cke.norm(t).strip(" ▁Ġ\"'„")


async def decision_flow(pipe, res, pq, s, sysmsg, use_kb, kw, labels):
    res.mode = "cke-decision"
    cmd = pq.command or pq.text
    dv = cke.decision_variants(cmd)
    units = cke.split_sources(pq.sources)
    cited = cke.cited_sources(cmd, units)
    info: dict = {"kind": dv["kind"], "variants": [d for _, d in dv["variants"]], "cited": [c for c, _ in cited]}
    res.parsed["cke"].update(decision=info)
    ss = dataclasses.replace(s, ctx_tokens=s.cke_source_ctx_tokens, top_k=s.cke_source_top_k,
                             rerank_keep=s.cke_source_top_k)

    async def analyse(lab: str, body: str) -> str:
        spq = ParsedQuestion(text=body, qtype="explain", stem=cke.source_query(body, 60))
        q = cke.source_query(body)
        ctx, _ = await _retrieve(pipe, spq, ss, use_kb, [("stem", q, 1.0)] if q else None)
        user = prompts.build_user(body[:1600], ctx, cke.analysis_instruction(lab))
        txt, _ = await _chat(pipe, res, [{"role": "system", "content": sysmsg}, {"role": "user", "content": user}],
                             max_tokens=120, kw=kw, tag=f"who:{lab}", prefill="Kto:")
        return f"{lab}: " + cke.parse_analysis(txt)

    main = asyncio.create_task(_retrieve(pipe, pq, s, use_kb, _with_source_queries(pq, s, units)))
    mode = s.cke_decide_mode
    info["mode"] = mode
    summaries = (await asyncio.gather(*(analyse(l, b) for l, b in cited))) if cited and mode != "direct" else []
    res.contexts, res.queries = await main
    facts = ("Ustalenia dla poszczególnych źródeł:\n" + "\n".join(summaries) + "\n\n") if summaries else ""
    info["summaries"] = summaries
    if mode in ("summaries", "direct"):
        return await _decide_one_call(pipe, res, pq, s, sysmsg, kw, labels, dv, cited, facts, info, cmd)
    user2 = prompts.build_user(pq.text, res.contexts, facts + cke.compare_instruction(dv, cmd))
    m2 = [{"role": "system", "content": sysmsg}, {"role": "user", "content": user2}]
    out2, _ = await _chat(pipe, res, m2, max_tokens=320, kw=kw, tag="compare", prefill="Porównanie:")
    idx = cke.match_variant(cke.final_region(out2), dv)
    info["free_choice"] = None if idx is None else dv["variants"][idx][1]
    if dv["kind"] == "yesno" or idx is None:
        m3 = m2 + [{"role": "assistant", "content": cke.reasoning_part(out2)[:1500]},
                   {"role": "user", "content": "Na podstawie powyższego porównania podaj rozstrzygnięcie jednym "
                                               "wariantem: " + " albo ".join(d for _, d in dv["variants"]) + "."}]
        g = "root ::= " + " | ".join('"' + d.replace('"', "") + '"' for _, d in dv["variants"]) + "\n"
        extra = {"logprobs": True, "top_logprobs": 10} if dv["kind"] == "yesno" else {}
        try:
            out3, r3 = await _chat(pipe, res, m3, max_tokens=12, kw=kw, tag="decide", grammar=g, **extra)
        except RuntimeError as e:  # logprobs unsupported -> plain constrained choice
            log.warning("decide call failed (%s), retrying without logprobs", str(e)[:100])
            out3, r3 = await _chat(pipe, res, m3, max_tokens=12, kw=kw, tag="decide", grammar=g)
        j = cke.match_variant(out3, dv)
        if dv["kind"] == "yesno":
            pr = _top_prob(r3, ("tak", "nie"))
            tot = sum(pr.values()) if pr else 0.0
            if tot > 0 and s.cke_yes_threshold > 0:
                p_yes = pr["tak"] / tot
                info["p_tak"] = round(p_yes, 3)
                j = 0 if p_yes >= s.cke_yes_threshold else 1
            elif j is None:
                j = idx
        idx = j if j is not None else (idx if idx is not None else (1 if dv["kind"] == "yesno" else 0))
    choice = dv["variants"][idx][1]
    info["choice"] = choice
    just_instr = cke.justify_instruction(dv, choice, labels, [c for c, _ in cited], cmd)
    user4 = prompts.build_user(pq.text, res.contexts, facts + just_instr)
    out4, _ = await _chat(pipe, res, [{"role": "system", "content": sysmsg}, {"role": "user", "content": user4}],
                          max_tokens=s.cke_explain_max_tokens, kw=kw, tag="justify")
    res.answer = formats.wrap(render_decision(labels, choice, out4))


def _yes_prob(resp: dict) -> float | None:
    """P(Tak) / (P(Tak) + P(Nie)) at the first of the first 4 generated tokens where 'Tak'/'Nie' carry the mass."""
    try:
        content = resp["choices"][0]["logprobs"]["content"][:4]
    except Exception:
        return None
    for ent in content:
        pr = {"tak": 0.0, "nie": 0.0}
        for c in ent.get("top_logprobs") or [ent]:
            tok = norm_tok(c.get("token", ""))
            for k in pr:
                if tok and len(tok) >= 2 and (k.startswith(tok) or tok.startswith(k)):
                    pr[k] += math.exp(float(c.get("logprob", -99)))
        if pr["tak"] + pr["nie"] >= 0.3:
            return pr["tak"] / (pr["tak"] + pr["nie"])
    return None


async def _decide_one_call(pipe, res, pq, s, sysmsg, kw, labels, dv, cited, facts, info, cmd):
    """CKE_DECIDE_MODE=summaries|direct: verdict + justification in one call (verdict line prefilled so its first
    token's probability is read; yes/no -> 'Tak' only if P(Tak) >= CKE_YES_THRESHOLD, otherwise the
    justification is rewritten for the flipped verdict)."""
    instr = cke.decide_instruction(dv, labels, [c for c, _ in cited], cmd)
    m = [{"role": "system", "content": sysmsg},
         {"role": "user", "content": prompts.build_user(pq.text, res.contexts, facts + instr)}]
    extra = {"logprobs": True, "top_logprobs": 10} if dv["kind"] == "yesno" else {}
    try:
        out, r = await _chat(pipe, res, m, max_tokens=s.cke_explain_max_tokens, kw=kw, tag="decide1",
                             prefill="Rozstrzygnięcie:", **extra)
    except RuntimeError as e:
        log.warning("decide1 failed (%s), retrying without logprobs", str(e)[:100])
        out, r = await _chat(pipe, res, m, max_tokens=s.cke_explain_max_tokens, kw=kw, tag="decide1",
                             prefill="Rozstrzygnięcie:")
    body = out.replace("**", "").split("Rozstrzygnięcie:", 1)[-1]
    verdict = re.split(r"(?i)uzasadnienie\s*:|\n", body.strip(), maxsplit=1)[0]
    idx = cke.match_variant(verdict, dv)
    info["free_choice"] = None if idx is None else dv["variants"][idx][1]
    rewrite = False
    if dv["kind"] == "yesno":
        p = _yes_prob(r)
        if p is not None and s.cke_yes_threshold > 0:
            info["p_tak"] = round(p, 3)
            j = 0 if p >= s.cke_yes_threshold else 1
            rewrite = idx != j
            idx = j
    if idx is None:  # a bare 'Tak' for a choice command, or nothing recognisable -> constrained choice
        m3 = m + [{"role": "assistant", "content": out[:1500]},
                  {"role": "user", "content": "Podaj rozstrzygnięcie jednym wariantem: " +
                                              " albo ".join(d for _, d in dv["variants"]) + "."}]
        g = "root ::= " + " | ".join('"' + d.replace('"', "") + '"' for _, d in dv["variants"]) + "\n"
        out3, _ = await _chat(pipe, res, m3, max_tokens=12, kw=kw, tag="decide", grammar=g)
        idx = cke.match_variant(out3, dv)
        idx = 0 if idx is None else idx
        rewrite = True
    choice = dv["variants"][idx][1]
    info["choice"] = choice
    just = body.split("\n", 1)[1] if "\n" in body.strip() else ""
    m_u = re.search(r"(?i)uzasadnienie\s*:", body)
    if m_u:
        just = body[m_u.end():]
    if rewrite or not just.strip():
        out4, _ = await _chat(pipe, res, m, max_tokens=s.cke_explain_max_tokens, kw=kw, tag="justify",
                              prefill=f"Rozstrzygnięcie: {choice}\nUzasadnienie:")
        just = out4.split("Uzasadnienie:", 1)[-1]
    res.answer = formats.wrap(render_decision(labels, choice, just))


def render_decision(labels, choice: str, text: str) -> str:
    """'Rozstrzygnięcie: <variant>\\nUzasadnienie: <prose>' (+ extra sheet labels) from the justification text."""
    just = re.sub(r"(?im)^\s*(rozstrzygnięcie|odpowiedź)\s*:.*$", "", (text or "").replace("**", ""))
    just = re.sub(r"^\s*uzasadnienie\s*:\s*", "", just.strip(), flags=re.I)
    extra_labels = [(l, sep) for l, sep in labels if not l.lower().startswith(("rozstrzygni", "uzasadni"))]
    tail = ""
    if extra_labels:
        trip = cke.parse_labeled(just, extra_labels)
        first = min((just.lower().find(l.lower()) for l, _ in extra_labels if l.lower() in just.lower()),
                    default=-1)
        if first > 0:
            just = just[:first]
        tail = "\n" + "\n".join(f"{l}: {cke.flatten_prose(v)}" for l, _, v in trip)
    lab_r = next((l for l, _ in labels if l.lower().startswith("rozstrzygni")), "Rozstrzygnięcie")
    lab_u = next((l for l, _ in labels if l.lower().startswith("uzasadni")), "Uzasadnienie")
    return (f"{lab_r}: {choice}\n{lab_u}: {cke.clean_justification(just)}{tail}".strip()
            [: formats.FORMATS["explain"]["max_chars"]])


# ------------------------------------------------------------------ essay
async def essay_flow(pipe, res, pq, s, extra_system, use_kb, kw):
    res.mode = "cke-essay"
    topics = pq.topics or [("1", pq.text)]
    plans = [essay.plan(n, t, pq.text) for n, t in topics]
    es = dataclasses.replace(s, ctx_tokens=s.essay_ctx_tokens, top_k=s.essay_top_k, rerank_keep=s.essay_top_k,
                             rerank_topn=max(s.rerank_topn, s.essay_rerank_topn), rerank_item_slots=True)
    if not use_kb:  # nothing to ground a verification on -> v2 essay path
        return await pipe._essay(res, pq, s, extra_system, use_kb)
    got = await asyncio.gather(*(asyncio.to_thread(retrieve, pipe.retriever, p.pq, es, p.queries) for p in plans))
    for p, (ctx, _) in zip(plans, got):
        p.contexts = ctx
        p.score, p.coverage = essay.coverage(p, ctx)
        fr = cke_essay.time_frame(p.topic)
        if fr and ctx:  # topics whose frame the passages do not cover lose a little
            yrs = [int(y) for c in ctx for y in re.findall(r"(?<!\d)(\d{4})(?!\d)", c.get("text", ""))]
            inside = sum(1 for y in yrs if fr[0] - 3 <= y <= fr[1] + 3)
            p.coverage["frame_hits"] = inside
            if inside < 3:
                p.score = round(p.score * 0.9, 4)
    ch = essay.choose(plans, s.essay_topic)
    if s.essay_safe:
        return await _essay_best_of_two(pipe, res, pq, s, extra_system, use_kb, kw, plans, ch)
    return await _write_essay(pipe, res, pq, s, extra_system, use_kb, kw, plans, ch)


async def _essay_best_of_two(pipe, res, pq, s, extra_system, use_kb, kw, plans, ch):
    """ESSAY_SAFE=1: write the essay for the two most promising topics (the topic choice first, then the next one by
    retrieval coverage; one topic when ESSAY_TOPIC forces it or the time budget is half gone) and hand in the one
    with the fewest unsupported claims per 100 words among those with >= ESSAY_SAFE_MIN_WORDS words (else the
    longer one). Both candidates' stats go to parsed['essay']['safe']."""
    from .pipeline import Result
    order = [ch] + [p for p in sorted(plans, key=lambda p: -p.score) if p is not ch]
    cands = order[:1] if s.essay_topic else order[:2]
    t0 = time.monotonic()
    runs, skipped = [], ""
    for i, p in enumerate(cands):
        if i and time.monotonic() - t0 > s.essay_safe_budget / 2:
            skipped = f"budget: first candidate took {time.monotonic() - t0:.0f}s"
            break
        r = Result(answer="", qtype=res.qtype)
        r.mode = res.mode
        t1 = time.monotonic()
        try:
            await _write_essay(pipe, r, pq, s, extra_system, use_kb, kw, plans, p)
        except Exception as e:  # the second candidate is optional
            if not runs:
                raise
            log.warning("essay safe: candidate topic %s failed: %s", p.n, e)
            skipped = f"error: {type(e).__name__}"
            break
        runs.append((p, r, round(time.monotonic() - t1, 1)))
    stats = []
    for p, r, dt in runs:
        m = r.parsed.get("essay") or {}
        words = essay.body_words(r.answer)
        n = m.get("unsupported")
        if n is None or m.get("fallback_v2"):  # v2 essay path (not verified): audit it with the same checker
            n = cke_essay.count_unsupported(r.answer, [p.topic] + [f"{c.get('title', '')} {c.get('text', '')}"
                                                                   for c in r.contexts],
                                            cke_essay.time_frame(p.topic))["unsupported"]
        stats.append({"topic": p.n, "score": p.score, "words": words, "unsupported": n,
                      "per100": round(100.0 * n / words, 2) if words else None, "latency_s": dt,
                      "llm_calls": r.llm_calls, "fallback_v2": bool(m.get("fallback_v2")) or r.mode == "essay"})
    best = cke_essay.pick_candidate(stats, s.essay_safe_min_words)
    p, r, _ = runs[best]
    res.answer, res.mode, res.contexts, res.queries = r.answer, r.mode, r.contexts, r.queries
    for j, (pj, rj, _) in enumerate(runs):
        res.raw += [f"[essay-safe] candidate {j + 1}: topic {pj.n}" + (" (chosen)" if j == best else "")] + rj.raw
        res.llm_calls += rj.llm_calls
        res.prompt_tokens += rj.prompt_tokens
        res.completion_tokens += rj.completion_tokens
    meta = dict(r.parsed.get("essay") or {})
    meta["safe"] = {"candidates": stats, "chosen": best, "chosen_topic": p.n, "skipped": skipped,
                    "elapsed_s": round(time.monotonic() - t0, 1)}
    res.parsed["essay"] = meta


async def _write_essay(pipe, res, pq, s, extra_system, use_kb, kw, plans, ch):
    """The v3 essay for the chosen topic `ch` (plan, per-element retrieval, parts, verification, clean-up)."""
    safe = s.essay_safe
    res.queries = ch.queries
    sysmsg = essay.SYSTEM + (("\n\nDodatkowe instrukcje:\n" + extra_system.strip())
                             if extra_system and s.keep_caller_system else "")
    gkw = dict(kw)
    gkw.update(repeat_penalty=s.essay_repeat_penalty, repeat_last_n=256, seed=42)
    if s.essay_dry_multiplier > 0:
        gkw.update(dry_multiplier=s.essay_dry_multiplier, dry_allowed_length=s.essay_dry_allowed)
    fr = cke_essay.time_frame(ch.topic)
    sup = cke_essay.superlative(ch.thesis)
    kind_sg, kind_pl, n_el = cke_essay.element_kind(ch.topic)
    topic_block = f"Temat nr {ch.n}:\n{ch.topic.strip()}"
    frame_rule = (f" Wszystkie przykłady muszą pochodzić z lat {cke_essay.frame_text(fr)} (rama czasowa tematu)."
                  if fr else "")
    meta: dict = {"topic": ch.n, "frame": fr, "superlative": sup, "aspects": ch.aspects,
                  "topics": [{"n": p.n, "score": p.score, **p.coverage} for p in plans]}
    res.parsed["essay"] = meta

    async def gen(user: str, max_tokens: int, tag: str, temperature: float | None = None, prefill: str = "") -> str:
        txt, _ = await _chat(pipe, res, [{"role": "system", "content": sysmsg}, {"role": "user", "content": user}],
                             max_tokens=max_tokens, kw=gkw, tag=tag, prefill=prefill,
                             temperature=s.essay_temperature if temperature is None else temperature)
        return txt

    def frags(ctx: list[dict]) -> str:
        return prompts.build_user("", ctx, "").rsplit("Zadanie:", 1)[0].strip()

    # 1. plan: concrete elements (when the topic lists no aspects; list format forced by a '1.' prefill) and an
    #    alternative for 'najbardziej' theses (its own one-line call, prefilled 'Alternatywa:')
    elements: list[str] = list(ch.aspects)
    alt = ""
    if not ch.aspects:
        ptxt = await gen(f"{frags(ch.contexts[:8])}\n\n{topic_block}\n\n" +
                         cke_essay.plan_instruction(ch.n, kind_pl, n_el, fr, False, []), 200, "plan", 0.0,
                         prefill="1.")
        els, _ = cke_essay.parse_plan(ptxt, n_el, fr)
        elements = [e for e, _ in els]
        if len(elements) < n_el:  # out-of-frame picks were dropped -> titles of in-frame passages
            extra = cke_essay.elements_from_contexts(ch.contexts, fr, n_el, ch.thesis, elements)
            meta["plan_fill"] = extra
            elements += extra
    if sup:
        atxt = await gen(f"{frags(ch.contexts[:6])}\n\n{topic_block}\n\n" + cke_essay.alt_instruction(ch.thesis),
                         30, "alt", 0.0, prefill="Alternatywa:")
        alt = cke_essay.parse_alt(atxt, ch.thesis)
    meta.update(elements=elements, alternative=alt)
    if len(elements) < 2:  # planning failed -> v2 essay path (its raw outputs are appended to ours)
        keep_raw = list(res.raw) + ["[cke-essay] plan failed -> v2 essay"]
        res.parsed.pop("essay", None)
        await pipe._essay(res, pq, s, extra_system, use_kb)
        res.raw = keep_raw + list(res.raw)
        return

    # 2. per-element retrieval (own passages for every paragraph)
    ps = dataclasses.replace(s, ctx_tokens=s.cke_essay_part_ctx_tokens, top_k=s.cke_essay_part_top_k,
                             rerank_keep=s.cke_essay_part_top_k, rerank_item_slots=False)
    short = " ".join(ch.thesis.split()[:14])

    def eq(e: str) -> tuple[ParsedQuestion, list]:
        if ch.aspects:
            q1, q2 = f"{ch.thesis} {e}", f"{short} {e} {cke_essay.frame_text(fr)}".strip()
        else:
            q1, q2 = e, f"{e} {short}"
        return ParsedQuestion(text=q1, qtype="essay", stem=q1), [("stem", q1, 1.0), ("item:e", q2, 0.8)]

    targets = elements + ([alt] if sup and alt else [])
    rs = await asyncio.gather(*(asyncio.to_thread(retrieve, pipe.retriever, eq(e)[0], ps, eq(e)[1])
                                for e in targets))
    used, ectx = set(), []
    for ctx, _ in rs:
        mine = [c for c in ctx if (c.get("title"), c.get("text", "")[:80]) not in used]
        mine = mine if len(mine) >= 3 else ctx
        used |= {(c.get("title"), c.get("text", "")[:80]) for c in mine}
        ectx.append(mine)
    all_ctx = list(ch.contexts) + [c for x in ectx for c in x]
    res.contexts = all_ctx
    blob = (ch.topic + (f" {fr[0]} {fr[1]}" if fr else "") + "\n" +  # the frame we put in the prompts is known
            "\n".join(f"{c.get('title', '')} {c.get('text', '')}" for c in all_ctx))
    unsup: dict = {}
    if safe:  # ESSAY_SAFE: passage-level checks (the topic + frame is passage 0)
        sidx = cke_essay.safe_index([ch.topic + (f" {fr[0]} {fr[1]}" if fr else "")] +
                                    [f"{c.get('title', '')} {c.get('text', '')}" for c in all_ctx])
        slog: list = []

    # 3. intro with an explicit stance (a stance sentence is added when the model hedges)
    listing = ", ".join(elements)
    stance = ("jednoznacznie zajmij stanowisko wobec tezy (np. „Zgadzam się z tezą, że…”, „Nie zgadzam się "
              "z tezą, że…” albo „Teza jest słuszna tylko częściowo, ponieważ…”)")
    intro_i = (f"Napisz wstęp wypracowania (3–4 zdania): wprowadź w temat (epoka, kontekst" +
               (f", lata {cke_essay.frame_text(fr)}" if fr else "") + f"), {stance} i zapowiedz, że uzasadnisz je, "
               f"omawiając: {listing}." + (f" Zapowiedz też porównanie z: {alt}." if sup and alt else "") +
               " Nie przepisuj polecenia ani tezy słowo w słowo, nie pisz nagłówka. Napisz tylko wstęp." +
               (" Nie podawaj miesięcy ani dni; rok tylko taki, który występuje w temacie albo w powyższych "
                "fragmentach." if safe else ""))
    intro = essay.clean_part(await gen(f"{frags(ch.contexts[:4])}\n\n{topic_block}\n\n{intro_i}", 320, "intro"),
                             "intro")
    intro = cke_essay.strip_prompt_copy(intro, ch.topic) or intro
    intro, added = cke_essay.ensure_stance(intro, ch.thesis)
    meta["stance_added"] = added
    if safe and s.cke_essay_verify:
        intro, lg, unsup["intro"] = cke_essay.verify_paragraph_safe(intro, sidx, fr, allow_drop=False)
        slog += lg
    stance_txt = cke_essay.stance_sentence(intro) or intro

    # 4. one paragraph per element (parallel; aspect paragraphs prefilled 'W aspekcie militarnym'), comparison
    #    for superlative theses. Only the stance goes into these prompts (the whole intro got copied back).
    def body_i(e: str) -> str:
        what = f"aspektu: {e}" if ch.aspects else f"{kind_sg if kind_sg != 'element' else 'elementu'}: {e}"
        if safe:  # fewer risky claims: plain years only, at most 2, only from the fragments; causes/effects instead
            return (f"Napisz akapit rozwinięcia (6–8 zdań) dotyczący {what}. Pierwsze zdanie ma wiązać ten element "
                    f"z tezą. Podaj 2–3 konkretne fakty z powyższych fragmentów (kto, co zrobił, z jakim skutkiem) "
                    f"i wyjaśnij, jak potwierdzają albo osłabiają stanowisko. Daty: podawaj tylko same lata, nigdy "
                    f"miesięcy ani dni, najwyżej 2 lata w całym akapicie i wyłącznie takie, które w powyższych "
                    f"fragmentach stoją przy tym samym wydarzeniu; gdy nie masz pewności, podaj fakt bez daty. "
                    f"Zamiast kolejnych dat wyjaśniaj przyczyny, skutki i znaczenie wydarzeń. Ostatnie zdanie akapitu "
                    f"ma wyraźnie wiązać go z tezą.{frame_rule} Pisz ciągłym tekstem, bez nagłówka; nie powtarzaj "
                    f"wstępu i nie pisz zakończenia. Napisz tylko ten akapit.")
        return (f"Napisz akapit rozwinięcia (6–8 zdań) dotyczący {what}. Pierwsze zdanie ma wiązać ten element "
                f"z tezą. Podaj 2–3 konkretne fakty z datami (rok) z powyższych fragmentów — wyłącznie takie, które "
                f"w nich występują — i wyjaśnij, jak potwierdzają albo osłabiają stanowisko. Ostatnie zdanie akapitu "
                f"ma wyraźnie wiązać go z tezą.{frame_rule} Pisz ciągłym tekstem, bez nagłówka; nie powtarzaj wstępu "
                f"i nie pisz zakończenia. Napisz tylko ten akapit.")

    jobs = [gen(f"{frags(ectx[i])}\n\n{topic_block}\n\nStanowisko autora wypracowania: {stance_txt}\n\n{body_i(e)}",
                520, f"body{i + 1}", prefill=cke_essay.aspect_prefill(e) if ch.aspects else "")
            for i, e in enumerate(elements)]
    if sup and alt:
        cmp_i = (f"Napisz akapit (4–6 zdań), w którym porównasz to, czego dotyczy teza, z alternatywą: {alt}. Podaj "
                 f"1–2 fakty z datami o {alt} z powyższych fragmentów i wyjaśnij, dlaczego mimo to stanowisko jest "
                 f"uzasadnione (albo dlaczego teza jest dyskusyjna). Bez nagłówka. Napisz tylko ten akapit.")
        if safe:
            cmp_i = (f"Napisz akapit (4–6 zdań), w którym porównasz to, czego dotyczy teza, z alternatywą: {alt}. "
                     f"Podaj 1–2 fakty o {alt} z powyższych fragmentów (najwyżej jeden rok, bez miesięcy i dni) "
                     f"i wyjaśnij, dlaczego mimo to stanowisko jest uzasadnione (albo dlaczego teza jest dyskusyjna). "
                     f"Bez nagłówka. Napisz tylko ten akapit.")
        jobs.append(gen(f"{frags(ectx[-1])}\n\n{topic_block}\n\nStanowisko autora wypracowania: {stance_txt}\n\n{cmp_i}",
                        400, "compare"))
    outs = await asyncio.gather(*jobs)
    bodies = [cke_essay.strip_prompt_copy(essay.clean_part(o, f"body{i + 1}"), ch.topic) for i, o in enumerate(outs)]

    # 5. verification against the retrieved passages (keeps >= 3 sentences per paragraph)
    vlog = []
    if s.cke_essay_verify:
        vb = []
        for b in bodies:
            if safe:
                nb, lg, nu = cke_essay.verify_paragraph_safe(b, sidx, fr)
                unsup["body"] = unsup.get("body", 0) + nu
            else:
                nb, lg = cke_essay.verify_paragraph(b, blob, fr)
            vb.append(nb)
            vlog += lg
        bodies = vb
    bodies = [b for b in bodies if b]

    # 6. conclusion (no new facts)
    so_far = "\n\n".join([intro] + bodies)
    end_i = ("Napisz zakończenie (3–4 zdania): podsumuj argumenty z rozwinięcia i powtórz stanowisko ze wstępu. "
             "Nie dodawaj nowych faktów ani dat. Napisz tylko zakończenie.")
    end = essay.clean_part(await gen(f"{topic_block}\n\nDotychczas napisany tekst wypracowania:\n{so_far}\n\n{end_i}",
                                     360, "end"), "end")
    end = cke_essay.strip_prompt_copy(end, ch.topic) or end
    if safe and s.cke_essay_verify:
        end, lg, unsup["end"] = cke_essay.verify_paragraph_safe(end, sidx, fr, allow_drop=False)
        slog += lg
    # a paragraph cut by max_tokens ends mid-sentence ("... Zimna wojna w latach 50."); graders take points off B
    pars = [_drop_trailing_fragment(p, last=(i == len(bodies) + 1))
            for i, p in enumerate([intro] + bodies + [end]) if p]
    pars = [p for p in pars if p]
    if sum(essay.word_count(p) for p in pars) > s.cke_essay_max_words + 80:
        pars = cke_essay.trim_to_words(pars, s.cke_essay_max_words, {0, len(pars) - 1})
    text = cke_essay.assemble(ch.n, [cke_essay.clean_header_lines(p) for p in pars])
    text = essay.clean(text, ch.n)  # cross-paragraph verbatim repeats, one header line
    words = cke_essay.body_words(text)
    meta.update(words=words, verify=vlog[:20], n_removed=sum(1 for v in vlog if "removed" in v),
                n_ctx=len(all_ctx), lora_off=bool(kw.get("lora")))
    if safe and s.cke_essay_verify:
        meta.update(unsupported=sum(unsup.values()), unsupported_parts=unsup, verify_intro_end=slog[:10])
    if words < 300:  # never hand in an essay below the coherence threshold
        res.raw.append(f"[cke-essay] {words} words -> v2 essay")
        v2 = await _v2_essay(pipe, pq, s, extra_system, use_kb)
        if v2 and essay.body_words(v2.answer) > words:
            res.answer, meta["fallback_v2"] = v2.answer, True
            return
    res.answer = formats.wrap(formats.render_essay(text))


_SENT_END = re.compile(r"(?<=[.!?…])[\"”»)]*\s+(?=[\"„«(]?[A-ZĄĆĘŁŃÓŚŹŻ])")
_ABBR_END = re.compile(r"(?:(?<!\w)(?:gen|św|ks|tzw|np|m\.in|ok|prof|płk|kpt|mjr|ppłk|abp|bp|dr|hr|kard|marsz|pw|im|ul)\.|(?<!\w)[IVXLC]+\.)$", re.I)


def _drop_trailing_fragment(p: str, last: bool = False) -> str:
    """Cut a paragraph back to its last complete sentence. The final paragraph also loses a trailing
    sentence under 6 words, which is what a max_tokens cut that happens to end in '50.' looks like."""
    p = p.rstrip()
    sents = []
    for x in _SENT_END.split(p):
        if sents and _ABBR_END.search(sents[-1]):
            sents[-1] += " " + x          # 'gen. Anders', 'św. Wojciech', 'Bolesław III. Krzywousty'
        elif x.strip():
            sents.append(x)
    if len(sents) < 2:
        return p
    if not re.search(r"[.!?…][\"”»)]*$", sents[-1]) or (last and len(sents[-1].split()) < 6):
        sents = sents[:-1]
    return " ".join(sents)


async def _v2_essay(pipe, pq, s, extra_system, use_kb):
    from .pipeline import Result
    r = Result(answer="", qtype="essay")
    try:
        await pipe._essay(r, pq, s, extra_system, use_kb)
        return r
    except Exception as e:  # pragma: no cover
        log.warning("v2 essay fallback failed: %s", e)
        return None
