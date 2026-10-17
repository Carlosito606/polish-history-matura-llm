"""Harness v4 LLM flows. Entered from harness/cke_flow.py (closed items, abcd_parts) and pipeline._chrono_years
ONLY when a v4 flag is on (harness/v4.py); with every flag off the v3 code runs unchanged.

  abcd_parts_flow  'Dokończ zdania 1. i 2.' -> each sentence as its own abcd item (own retrieval + reasoning call)
  closed_flow      v3 closed flow + source-first retrieval, neutral format examples, self-consistency (SC_K),
                   P/F evidence pass (F only with a quoted contradicting sentence; value-first re-check of P)
  chrono_years     v2 year-grammar chronology + ' p.n.e.' years / BC fallback + tie resolution (month/day, pairwise)
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import re

from . import cke, formats, prompts, v4
from .postprocess import parse_letters, parse_sequence, parse_years
from .qtype import ParsedQuestion, detect, entities
from .retrieval import build_queries, retrieve

log = logging.getLogger("harness.v4")


def _cf():
    from . import cke_flow
    return cke_flow


def _info(res) -> dict:
    return res.parsed.setdefault("cke", {}).setdefault("v4", {})


# ------------------------------------------------------------------ fix 2: source-first retrieval
def _ident_values(ident: str) -> dict:
    out = {}
    for part in (ident or "").split(";"):
        k, _, v = part.partition(":")
        v = v.strip()
        if v and not re.match(r"^\W*(nie\s+wiadomo|brak|nieznan\w*|-+)\W*$", v, re.I):
            out[k.strip().lower()] = v
    return out


def ident_query(ident: str) -> str:
    vals = _ident_values(ident)
    return " ".join(vals[k] for k in ("co", "kto", "kiedy", "gdzie") if k in vals)[:300]


def _cmd_stem(pq: ParsedQuestion) -> str:
    """The command without its list entries (P/F statements, options)."""
    lines = []
    for ln in (pq.command or "").split("\n"):
        if re.match(r"^\s*(?:\(?[A-H1-9]\)|[A-H1-9][.)]|[-•*])\s+", ln):
            continue
        lines.append(ln.strip())
    return " ".join(" ".join(lines).split())[:400]


def source_first_queries(pq: ParsedQuestion, ident: str) -> tuple[list[tuple[str, str, float]], str, str]:
    """-> (BM25 queries, reranker query, title reference). The identification + command drive retrieval; the P/F
    statements and ABCD options (distractors) do not. Match items keep their per-item queries (the fragments)."""
    iq = ident_query(ident)
    cmd = _cmd_stem(pq)
    qs: list[tuple[str, str, float]] = []
    if iq:
        qs.append(("ident", iq, 1.0))
        qs.append(("ident+cmd", f"{iq} {cmd}", 0.8))
    stem = pq.stem or cmd
    qs.append(("stem", stem, 0.7 if iq else 1.0))
    if pq.qtype == "match":
        qs += [x for x in build_queries(pq, v2=True) if x[0].startswith(("item:", "right:"))]
    ents = entities(f"{iq} {pq.sources}")
    if ents:
        qs.append(("ents", " ".join(ents[:12]), 0.6))
    seen, out = set(), []
    for name, q, w in qs:
        k = q.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append((name, q, w))
    rq = " ".join(f"{iq}\n{cmd}\n{pq.sources}".split())[:900]
    ref = f"{pq.sources}\n{cmd}\n{iq}"
    return out, rq, ref


async def identify_source(pipe, res, pq: ParsedQuestion, s, sysmsg: str, kw: dict, use_kb: bool) -> str:
    """Short who/what/when/where call on the source text alone (+ passages retrieved for the source text)."""
    body = (pq.sources or "").strip()[:1600]
    ctx = []
    q = cke.source_query(body, 60)
    if use_kb and q:
        ss = dataclasses.replace(s, ctx_tokens=s.cke_source_ctx_tokens, top_k=s.cke_source_top_k,
                                 rerank_keep=s.cke_source_top_k, v4_title_rescore=0)
        spq = ParsedQuestion(text=body, qtype="explain", stem=q)
        ctx, _ = await asyncio.to_thread(retrieve, pipe.retriever, spq, ss, [("stem", q, 1.0)])
    user = prompts.build_user(body, ctx, cke.analysis_instruction("źródło"))
    txt, _ = await _cf()._chat(pipe, res, [{"role": "system", "content": sysmsg}, {"role": "user", "content": user}],
                               max_tokens=120, kw=kw, tag="v4-ident", prefill="Kto:")
    return cke.parse_analysis(txt)


async def source_first_retrieve(pipe, res, pq, s, sysmsg, kw, use_kb):
    info = _info(res)
    ident = await identify_source(pipe, res, pq, s, sysmsg, kw, use_kb)
    info["ident"] = ident[:300]
    qs, rq, ref = source_first_queries(pq, ident)
    if not use_kb:
        return [], []
    return await asyncio.to_thread(retrieve, pipe.retriever, pq, s, qs, None, rq, ref)


# ------------------------------------------------------------------ closed items
def closed_instruction(pq: ParsedQuestion, s) -> str:
    instr = cke.closed_instruction(pq)
    if v4.on(s, "v4_neutral_examples") and pq.qtype == "match" and pq.left:
        ex = ", ".join(f"{l}-{pq.right[0][0] if pq.right else 'X'}" for l, _ in pq.left[:3])
        ex_x = ", ".join(f"{l}-X" for l, _ in pq.left[:3])
        instr = instr.replace(f"Odpowiedź: {ex}, …", f"Odpowiedź: {ex_x}, … (X = oznaczenie właściwego elementu;")
        instr = instr.replace("(X = oznaczenie właściwego elementu; (pary", "(X = oznaczenie właściwego elementu; pary")
    return instr


async def closed_flow(pipe, res, pq, s, sysmsg, use_kb, kw):
    cf = _cf()
    res.mode = "cke-closed-v4"
    info = _info(res)
    qtext = v4.neutralize_examples(pq.text) if v4.on(s, "v4_neutral_examples") else pq.text
    if qtext != pq.text:
        info["neutral"] = True
    if v4.on(s, "v4_source_first") and (pq.sources or "").strip():
        res.contexts, res.queries = await source_first_retrieve(pipe, res, pq, s, sysmsg, kw, use_kb)
    else:
        res.contexts, res.queries = await cf._retrieve(pipe, pq, s, use_kb)
    messages = cf._msgs(sysmsg, qtext, res.contexts, closed_instruction(pq, s))
    k = v4.sc_k(s)
    jobs = [cf._chat(pipe, res, messages, max_tokens=s.cke_reason_max_tokens, kw=kw, tag="reason",
                     prefill="Rozumowanie:")]
    for i in range(1, k):
        jobs.append(cf._chat(pipe, res, messages, max_tokens=s.cke_reason_max_tokens, kw=kw, tag=f"sc{i}",
                             prefill="Rozumowanie:", temperature=s.sc_temperature))
    outs = [o for o, _ in await asyncio.gather(*jobs)]
    out = outs[0]
    regions = []
    for o in outs:
        rg = cke.final_region(o) if cf.has_answer(o) else ""
        if cf.complete(pq, rg):
            regions.append(rg)
    ans = pipe._combine(pq, regions, res) if regions else None
    first = cke.final_region(out) if cf.has_answer(out) else ""
    res.parsed["cke"].update(final=first[:200], fallback=ans is None)
    if k > 1:
        info["sc"] = {"k": k, "valid": len(regions), "votes": list(res.votes)}
    if ans is None and v4.on(s, "v4_continue") and out.strip():
        # reasoning cut by max_tokens before its 'Odpowiedź:' line -> let the model finish its OWN conclusion
        # (continue the assistant turn) instead of a fresh grammar call, which fell back to 'A' after long reasoning
        pre = re.sub(r"[\s*#]+$", "", out)
        cont, _ = await cf._chat(pipe, res, messages, max_tokens=cf.pipe_max_tokens(pq, s) + 12, kw=kw,
                                 tag="continue", prefill=pre + "\n\nOdpowiedź:")
        rg = cke.final_region(cont)
        if cf.complete(pq, rg):
            ans = pipe._combine(pq, [rg], res)
            info["continued"] = True
    if ans is None:  # no parsable final line -> grammar-constrained answer, reasoning kept as context
        instr = prompts.instruction(pq)
        m2 = messages + [{"role": "assistant", "content": cke.reasoning_part(out)[:1500]},
                         {"role": "user", "content": instr}]
        out2, _ = await cf._chat(pipe, res, m2, max_tokens=cf.pipe_max_tokens(pq, s), kw=kw, tag="grammar",
                                 grammar=prompts.grammar_for(pq))
        ans = pipe._combine(pq, [out2], res)
    if ans is not None and pq.qtype == "pf" and pq.statements and (
            v4.on(s, "v4_pf_evidence") or v4.on(s, "v4_pf_value")):
        ans = await pf_evidence_pass(pipe, res, pq, s, sysmsg, kw, qtext, ans)
    res.answer = formats.wrap(ans if ans is not None else formats.render_generic(first))


# ------------------------------------------------------------------ fix 3: P/F evidence pass
async def pf_evidence_pass(pipe, res, pq, s, sysmsg, kw, qtext: str, ans: str) -> str:
    from .postprocess import parse_pf
    cf = _cf()
    n = len(pq.statements)
    vals = parse_pf(ans, n)
    if len(vals) != n:
        return ans
    ev_on, val_on = v4.on(s, "v4_pf_evidence"), v4.on(s, "v4_pf_value")
    evidence = "\n".join(f"{c.get('title', '')}. {c.get('text', '')}" for c in res.contexts) + "\n" + \
               (pq.sources or "") + "\n" + (pq.stem if not pq.sources else "")
    todo = []
    for i, (lab, stmt) in enumerate(pq.statements):
        hv = v4.has_value(stmt)
        if (not vals[i] and ev_on) or (vals[i] and val_on and hv):
            todo.append((i, lab, stmt, hv))
    if not todo:
        return ans

    async def check(i, lab, stmt, hv):
        instr = v4.pf_check_instruction(lab, stmt, vals[i], hv)
        txt, _ = await cf._chat(pipe, res, cf._msgs(sysmsg, qtext, res.contexts, instr), max_tokens=200, kw=kw,
                                tag=f"pf-check:{lab}", prefill="Wartość w kontekście:" if hv else "Cytat:")
        quote, verdict = v4.parse_pf_check(txt)
        new, why = v4.pf_decide(vals[i], quote, verdict, evidence)
        return i, new, why, quote[:160]

    got = await asyncio.gather(*(check(*t) for t in todo))
    log_ = []
    for i, new, why, quote in got:
        log_.append({"stmt": pq.statements[i][0], "why": why, "quote": quote})
        vals[i] = new
    _info(res)["pf_check"] = log_
    return formats.render_pf(vals, [l for l, _ in pq.statements])


# ------------------------------------------------------------------ fix 1: abcd_parts as separate abcd items
async def abcd_parts_flow(pipe, res, pq, s, sysmsg, use_kb, kw):
    from .pipeline import Result
    cf = _cf()
    res.mode = "cke-parts-v4"
    subs = []
    for i, (pl, sent, opts) in enumerate(pq.parts):
        t = v4.part_question(pq, i)
        spq = detect(t, "abcd", v2=True)
        if [l for l, _ in spq.options] != [l for l, _ in opts]:
            spq.options = list(opts)
        spq.n_select = 1
        subs.append((pl, t, spq))

    async def one(spq):
        r = Result(answer="", qtype="abcd", parsed=spq.to_dict())
        r.parsed["cke"] = {"labels": [], "lora_off": bool(kw.get("lora"))}
        if v4.any_closed(s):
            await closed_flow(pipe, r, spq, s, sysmsg, use_kb, kw)
        else:
            await cf.closed_flow(pipe, r, spq, s, sysmsg, use_kb, kw)
        return r

    rs = await asyncio.gather(*(one(spq) for _, _, spq in subs))
    pairs, detail = [], []
    seen = set()
    for (pl, t, spq), r in zip(subs, rs):
        got = parse_letters(r.answer, [l for l, _ in spq.options], 1)
        pairs.append((pl, got[0] if got else spq.options[0][0]))
        res.raw += [f"[part {pl}] {x}" for x in r.raw]
        res.llm_calls += r.llm_calls
        res.prompt_tokens += r.prompt_tokens
        res.completion_tokens += r.completion_tokens
        res.queries += [(f"p{pl}:{q[0]}", q[1], q[2]) for q in r.queries]
        for c in r.contexts:
            key = (c.get("title"), c.get("text", "")[:80])
            if key not in seen:
                seen.add(key)
                res.contexts.append(c)
        detail.append({"part": pl, "answer": r.answer, "mode": r.mode, "v4": r.parsed.get("cke", {}).get("v4")})
    res.votes = ["".join(f"{a}{b}" for a, b in pairs)]
    _info(res)["parts"] = detail
    res.answer = formats.wrap(formats.render_match(pairs))


# ------------------------------------------------------------------ fix 5: chronology
async def chrono_years(pipe, res, pq, s, extra_system):
    """pipeline._chrono_years with V4_CHRONO_BC / V4_CHRONO_TIES / V4_NEUTRAL_EXAMPLES."""
    from .pipeline import _max_tokens, build_messages
    bc, ties, neutral = v4.chrono_bc_mode(s), v4.chrono_ties_mode(s), v4.on(s, "v4_neutral_examples")
    hybrid = s.chrono_mode == "hybrid"
    res.mode = "chrono-" + s.chrono_mode + "-v4"
    labels = [l for l, _ in pq.items]
    sysmsg = pipe._system(extra_system, s)
    qtext = v4.neutralize_examples(pq.text) if neutral else pq.text
    instr_y = v4.instruction_chrono_years_bc(pq.items) if bc >= 2 else prompts.instruction_chrono_years(pq)
    gram_y = v4.grammar_years_bc(pq.items) if bc else prompts.grammar_years(pq)
    messages = build_messages(sysmsg, qtext, res.contexts, instr_y)
    tasks = [pipe._gen(res, messages, max_tokens=(15 if bc else 8) * len(labels) + 4, grammar=gram_y, s=s, votes=True)]
    if hybrid:
        instr_d = prompts.instruction(pq)
        if neutral:
            instr_d = (f"Uporządkuj elementy ({', '.join(labels)}) chronologicznie, od najwcześniejszego do "
                       f"najpóźniejszego. Odpowiedz wyłącznie oznaczeniami oddzielonymi przecinkami, bez wyjaśnień.")
        tasks.append(pipe._gen(res, build_messages(sysmsg, qtext, res.contexts, instr_d),
                               max_tokens=_max_tokens(pq, s), grammar=prompts.grammar_for(pq), s=s, votes=False))
    got = await asyncio.gather(*tasks)
    outs = got[0]
    direct = parse_sequence(got[1][0], labels) if hybrid and got[1] else labels
    for l in labels:  # parse_sequence may miss a label
        if l not in direct:
            direct = direct + [l]
    res.raw = outs + (got[1] if hybrid else [])
    yrs = [parse_years(o, labels) for o in outs]
    final_years = {}
    for l in labels:
        vals = sorted(y[l] for y in yrs if l in y)
        final_years[l] = vals[len(vals) // 2] if vals else None
    meta: dict = {}
    if bc:
        ctx_text = "\n".join(c.get("text", "") for c in res.contexts)
        final_years, meta["bc"] = v4.bc_fix(final_years, v4.signed_labels(outs[0] if outs else "", labels),
                                            pq.items, pq.stem, ctx_text)
    known = [final_years[l] for l in labels if final_years[l] is not None]
    unknown = [l for l in labels if final_years[l] is None]
    for l in unknown:
        final_years[l] = 99999 if not known else max(known) + 1
    res.votes = [str(y) for y in yrs]
    rank = {l: direct.index(l) for l in labels}
    if ties:
        groups = [g for g in v4.tie_groups(final_years, [l for l in labels if l not in unknown])]
        meta["ties"] = []
        texts = dict(pq.items)
        for g in groups[:3]:
            g = sorted(g, key=lambda l: rank[l])
            md = None
            if ties == 1:
                instr = v4.instruction_monthday([(l, texts[l]) for l in g], int(final_years[g[0]]))
                o = await pipe._gen(res, build_messages(sysmsg, qtext, res.contexts, instr), max_tokens=8 * len(g) + 4,
                                    grammar=v4.grammar_monthday(g), s=s, votes=False)
                res.raw += o
                md = v4.parse_monthday(o[0] if o else "", g)
            order_g, how = v4.order_group(g, md, None, direct)
            if how == "direct" and len(g) <= 4:  # month/day did not separate them -> pairwise with context
                wins = {l: 0 for l in g}
                pairs = [(a, b) for i, a in enumerate(g) for b in g[i + 1:]]

                async def cmp(a, b):
                    o = await pipe._gen(res, build_messages(sysmsg, qtext, res.contexts,
                                                            v4.instruction_pair((a, texts[a]), (b, texts[b]))),
                                        max_tokens=3, grammar=f'root ::= "{a}" | "{b}"\n', s=s, votes=False)
                    return a, b, (o[0].strip()[:1] if o else "")
                for a, b, w in await asyncio.gather(*(cmp(a, b) for a, b in pairs)):
                    res.raw.append(f"[pair {a}{b}] {w}")
                    if w in (a, b):
                        wins[w] += 1
                order_g, how = v4.order_group(g, None, wins, direct)
            base = min(rank[x] for x in g)
            for j, l in enumerate(order_g):
                rank[l] = base + j * 1e-3
            meta["ties"].append({"group": g, "order": order_g, "how": how, "md": md})
    order = sorted(labels, key=lambda l: (final_years[l], rank[l]))
    res.parsed["years"] = final_years
    if meta:
        res.parsed["v4_chrono"] = meta
    res.answer = formats.wrap(formats.render_chrono(order))
