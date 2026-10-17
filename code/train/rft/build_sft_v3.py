#!/usr/bin/env python3
"""SFT v3 for Bielik-4.5B-v3 (harness v3, CKE_MODE=1) = RFT v3 rows + CKE human sample answers.

  1. RFT rows (/workspace/data/rft_v3.jsonl, train/rft/rft_select.py): the untouched base model's own correct
     reasoning -> kept as they are (minus rows whose task text overlaps a 2023-2026 CKE paper).
  2. CKE items (train/datagen/cke_full_items/*.jsonl; split=train, verified, type in explain / decide_justify /
     compare / open_short, non-empty 'answer'):
       * provenance: the 'answer' must be found in the official answer key of its paper
         (data_cke/arkusze/<slug>/*odpowiedzi*.txt; verbatim, or >= 80 % of its word 3-grams, or a short answer
         whose words all occur in the key) - so every target is CKE human text, never a paraphrase;
       * decontamination: build_sft.contaminated (devset/**) + 10-word shingles vs every 2022-12..2026 CKE text
         (data_cke/*.txt, data_cke/arkusze/<2023+ slug>/*.txt);
       * prompt: the REAL harness (Pipeline.answer, CKE_MODE=1 QTYPE_V2=1 RERANK=1) runs with an LLM wrapper that
         raises at the first answer-producing call and records its messages. The per-source 'Kto:' analyses of
         the decision flow (CKE_DECIDE_MODE=summaries) go to the real base model, as at exam time.
       * target: explain flow -> the CKE answer (a single sheet label is prefixed when the command has one);
         decision flow (prefill 'Rozstrzygnięcie:') -> 'Rozstrzygnięcie: <variant>\\nUzasadnienie: <CKE answer>'
         when the answer starts with the verdict; open / names flows (prefill 'Rozumowanie:') are skipped: a human
         sample answer has no reasoning to put there and nothing may be written for it.

  cd /scratch/sftv3/repo && CKE_MODE=1 QTYPE_V2=1 RERANK=1 RERANK_URL=http://127.0.0.1:18094 \\
    KB_INDEX_DIR=/scratch/kb_index LLM_BASE_URL=http://127.0.0.1:18093/v1 LLM_MODEL=bielik-4.5b-v3 \\
    /scratch/ovl/venvs/wmt/bin/python train/rft/build_sft_v3.py --rft /scratch/rft/out/rft_v3.jsonl \\
      --out /scratch/sftv3/sft_v3.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "train"))

import build_sft  # noqa: E402
from harness import cke  # noqa: E402
from harness.qtype import KW_DECIDE, detect  # noqa: E402

TYPES = {"explain", "decide_justify", "compare", "open_short"}
_W = re.compile(r"[0-9a-ząćęłńóśźż]+")


def words(s: str) -> list[str]:
    s = (s or "").lower().replace("-\n", "").replace("­", "")
    return _W.findall(s)


def ngrams(ws: list[str], n: int) -> set:
    return {" ".join(ws[i:i + n]) for i in range(len(ws) - n + 1)}


# ----------------------------------------------------------------------------- provenance vs the official key
class Keys:
    def __init__(self, arkusze: str):
        self.dir, self.cache = arkusze, {}

    def get(self, slug: str):
        if slug not in self.cache:
            txt = ""
            for f in sorted(glob.glob(os.path.join(self.dir, slug, "*.txt"))):
                if re.search(r"odpow|klucz|model|kryter|zasad", os.path.basename(f), re.I) and not f.endswith(".raw.txt"):
                    txt += "\n" + open(f, encoding="utf-8", errors="replace").read()
            ws = words(txt)
            self.cache[slug] = (" " + " ".join(ws) + " ", set(ws), ngrams(ws, 3)) if ws else None
        return self.cache[slug]


def provenance(answer: str, key) -> str | None:
    if not key:
        return None
    flat, vocab, tri = key
    aw = words(answer)
    if not aw:
        return None
    if " " + " ".join(aw) + " " in flat:
        return "verbatim"
    at = ngrams(aw, 3)
    if at and sum(t in tri for t in at) / len(at) >= 0.8:
        return "near_verbatim"
    if len(aw) <= 6 and all(w in vocab for w in aw):
        return "short_in_key"
    return None


# ----------------------------------------------------------------------------- 2023-2026 CKE shingles
def recent_texts(data_cke: str) -> list[str]:
    fs = [f for f in glob.glob(os.path.join(data_cke, "*.txt")) if not f.endswith(".raw.txt")]
    for d in glob.glob(os.path.join(data_cke, "arkusze", "*")):
        m = re.search(r"(20\d\d)-(\w+?)-", os.path.basename(d) + "-")
        if m and (int(m.group(1)) >= 2023 or (m.group(1) == "2022" and m.group(2) == "grudzien")):
            fs += [f for f in glob.glob(os.path.join(d, "*.txt")) if not f.endswith(".raw.txt")]
    return sorted(set(fs))


class Recent:
    N = 10

    def __init__(self, files: list[str]):
        self.sh = set()
        for f in files:
            self.sh |= ngrams(words(open(f, encoding="utf-8", errors="replace").read()), self.N)
        self.files = len(files)

    def hits(self, text: str, common: set) -> int:
        return len((ngrams(words(text), self.N) - common) & self.sh)


def task_text(user: str) -> str:
    """User turn of a harness prompt -> the task text (between 'Zadanie:' and the instruction paragraph)."""
    t = user.split("Zadanie:\n", 1)[-1]
    return t.rsplit("\n\n", 1)[0] if "\n\n" in t else t


# ----------------------------------------------------------------------------- harness prompt capture
class Captured(Exception):
    def __init__(self, messages, kw):
        super().__init__("captured")
        self.messages, self.kw = messages, kw


class RecLLM:
    """Stands in for pipe.llm: per-source 'Kto:' analyses (decision flow) go to the real base model; the first
    other call is the answer-producing one -> its messages are captured and the flow is aborted."""

    def __init__(self, real):
        self.real = real
        self.n_real = 0

    async def lora_zero(self) -> dict:
        return await self.real.lora_zero()

    async def chat(self, messages, **kw):
        last = messages[-1]
        if last.get("role") == "assistant" and last.get("content", "").strip().startswith("Kto:"):
            self.n_real += 1
            return await self.real.chat(messages, **kw)
        raise Captured(messages, kw)


def route_of(pq) -> tuple[str, list]:
    """Mirror of harness.cke_flow.run routing (after cke.fix_command). -> (route, sheet labels)."""
    from harness import cke_flow
    src, cmd = cke.fix_command(pq)
    pq.sources, pq.command = src, cmd
    labels = cke.sheet_labels(pq.command or pq.text)
    if pq.qtype == "essay":
        return "essay", labels
    names = cke.names_task(pq, labels) if pq.qtype in ("match", "open", "generic", "explain") else []
    if not names and pq.qtype in ("open", "generic") and labels:
        names = labels
    if names:
        return "names", labels
    if pq.qtype in cke_flow.CLOSED:
        return "closed", labels
    if pq.qtype == "chrono":
        return "chrono", labels
    wants = bool(re.search(r"uzasadni", pq.command or "", re.I))
    if pq.qtype == "explain" and ((labels[:1] and labels[0][0].lower().startswith("rozstrzygni")) or
                                  (KW_DECIDE.search(pq.command or "") and wants)):
        return "decision", labels
    if pq.qtype == "explain":
        return "explain", labels
    return "open", labels


_VERDICT = re.compile(r"^\W*(tak|nie)\b\s*[,.;:–—-]?\s*", re.I)


def decision_target(answer: str, pq, labels) -> tuple[str | None, str]:
    cmd = pq.command or pq.text
    dv = cke.decision_variants(cmd)
    extra = [l for l, _ in labels if not l.lower().startswith(("rozstrzygni", "uzasadni"))]
    if extra:
        return None, "decision_extra_labels"
    a = re.sub(r"^\s*(odpowiedź|rozstrzygnięcie)\s*:\s*", "", answer.strip(), flags=re.I)
    if dv["kind"] == "yesno":
        m = _VERDICT.match(a)
        if not m:
            return None, "decision_verdict_not_first"
        choice = "Tak" if m.group(1).lower() == "tak" else "Nie"
        just = a[m.end():].strip()
        if len(just.split()) < 4:
            return None, "decision_no_justification"
        just = just[:1].upper() + just[1:]
    else:
        head = re.split(r"[,.;:–—]|\s+(?:ponieważ|bo|gdyż|albowiem|dlatego)\b", a, maxsplit=1)[0]
        idx = cke.match_variant(head, dv)
        if idx is None:
            return None, "decision_verdict_not_first"
        choice = dv["variants"][idx][1]
        just = a
    return f"Rozstrzygnięcie: {choice}\nUzasadnienie: {just}", "ok"


def explain_target(answer: str, labels) -> tuple[str | None, str]:
    a = re.sub(r"^\s*odpowiedź\s*:\s*", "", answer.strip(), flags=re.I)
    if not labels:
        return a, "ok"
    trip = cke.parse_labeled(a, labels)
    if all(v for _, _, v in trip):
        return a, "ok"
    if len(labels) == 1:
        l, sep = labels[0]
        return f"{l}{': ' if sep.strip() == ':' else ' – '}{a}", "ok"
    return None, "labels_unmatched"


async def capture_all(items, conc: int):
    from harness.config import Settings
    from harness.llm import LLM
    from harness.pipeline import Pipeline
    from harness.retrieval import Retriever
    s = Settings()
    assert s.cke_mode and s.qtype_v2 and s.rerank, "run with CKE_MODE=1 QTYPE_V2=1 RERANK=1"
    retr = Retriever(s)
    if not retr.available:
        sys.exit(f"KB not available: {retr.error}")
    real = LLM(s)
    rec = RecLLM(real)
    pipe = Pipeline(s, rec, retr)
    sem = asyncio.Semaphore(conc)
    out = {}

    async def one(it):
        async with sem:
            try:
                res = await pipe.answer(it["_question"])
                out[it["id"]] = (None, f"no_llm_call:{res.qtype}")
            except Captured as c:
                out[it["id"]] = (c.messages, "ok")
            except Exception as e:  # noqa: BLE001
                out[it["id"]] = (None, f"error:{type(e).__name__}:{str(e)[:120]}")

    await asyncio.gather(*(one(it) for it in items))
    info = {"settings": {k: getattr(s, k) for k in ("cke_mode", "qtype_v2", "rerank", "rerank_url", "top_k",
                                                     "ctx_tokens", "cke_decide_mode", "llm_model", "llm_base_url",
                                                     "kb_index_dir")},
            "real_kto_calls": rec.n_real}
    await real.close()
    return out, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rft", required=True)
    ap.add_argument("--cke-full", default=os.path.join(ROOT, "train/datagen/cke_full_items"))
    ap.add_argument("--data-cke", default=os.path.join(ROOT, "data_cke"))
    ap.add_argument("--dev-dir", default=os.path.join(ROOT, "devset"))
    ap.add_argument("--overlap", type=float, default=0.8)
    ap.add_argument("--recent-min-hits", type=int, default=1)
    ap.add_argument("--conc", type=int, default=4)
    ap.add_argument("--dry", action="store_true", help="filters + routing only, no retrieval / LLM")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    stats = collections.Counter()
    recent = Recent(recent_texts(a.data_cke))
    dev_titles, dev_q, n_dev = build_sft.load_dev(a.dev_dir)
    inv = collections.defaultdict(list)
    for i, q in enumerate(dev_q):
        for t in q:
            inv[t].append(i)

    # ---------------- CKE human sample answers
    keys = Keys(os.path.join(a.data_cke, "arkusze"))
    cand = []
    for f in sorted(glob.glob(os.path.join(a.cke_full, "*.jsonl"))):
        slug = os.path.basename(f)[:-6]
        for it in build_sft.read_jsonl(f):
            if it.get("type") not in TYPES:
                continue
            t = it["type"]
            if it.get("split") != "train" or it.get("verified") is not True:
                stats[f"cke/{t}/drop:not_train_or_unverified"] += 1
                continue
            ans = it.get("answer") if isinstance(it.get("answer"), str) else ""
            if not ans.strip():
                stats[f"cke/{t}/drop:no_answer"] += 1
                continue
            q = it["question"]
            if not it.get("text_only", True) or it.get("need_image"):
                desc = (it.get("image_desc") or "").strip()
                if not desc:
                    stats[f"cke/{t}/drop:image_without_description"] += 1
                    continue
                parts = q.rsplit("\n\n", 1)  # description before the command, like '[Opis obrazu: ...]' at exam time
                q = (parts[0] + f"\n[Opis obrazu: {desc}]\n\n" + parts[1]) if len(parts) == 2 else \
                    f"[Opis obrazu: {desc}]\n\n{q}"
            prov = provenance(ans, keys.get(slug))
            if not prov:
                stats[f"cke/{t}/drop:answer_not_in_official_key"] += 1
                continue
            it = dict(it, _question=q, _prov=prov, _slug=slug)
            cand.append(it)
    # boilerplate shingles (instruction phrases shared by >= 3 items) never count as contamination
    df = collections.Counter()
    for it in cand:
        df.update(ngrams(words(it["_question"]), Recent.N))
    common = {g for g, n in df.items() if n >= 3}
    keep = []
    for it in cand:
        t = it["type"]
        why = build_sft.contaminated(it, dev_titles, dev_q, inv, a.overlap)
        if why:
            stats[f"cke/{t}/drop:{why}"] += 1
            continue
        if recent.hits(it["_question"], common) >= a.recent_min_hits:
            stats[f"cke/{t}/drop:overlap_cke_2023_2026"] += 1
            continue
        pq = detect(it["_question"], None, v2=True)
        route, labels = route_of(pq)
        it["_route"] = route
        if route in ("open", "names"):
            stats[f"cke/{t}/drop:route_{route}_needs_reasoning"] += 1
            continue
        if route not in ("explain", "decision"):
            stats[f"cke/{t}/drop:route_{route}"] += 1
            continue
        tgt, why = (decision_target if route == "decision" else lambda x, p, l: explain_target(x, l))(
            it["answer"], pq, labels)
        if not tgt:
            stats[f"cke/{t}/drop:{why}"] += 1
            continue
        it["_target"] = tgt
        keep.append(it)
    print(f"[cke] candidates={len(cand)} after filters={len(keep)}", flush=True)

    cke_rows = []
    if not a.dry and keep:
        caps, cinfo = asyncio.run(capture_all(keep, a.conc))
        stats["cke_real_kto_calls"] = cinfo["real_kto_calls"]
        print(f"[capture] {json.dumps(cinfo, ensure_ascii=False)}", flush=True)
        for it in keep:
            msgs, why = caps.get(it["id"], (None, "missing"))
            t = it["type"]
            if not msgs:
                stats[f"cke/{t}/drop:capture_{why.split(':')[0]}"] += 1
                continue
            prefill = ""
            if msgs[-1]["role"] == "assistant":
                prefill = msgs[-1]["content"]
                msgs = msgs[:-1]
            want = {"decision": "Rozstrzygnięcie:", "explain": ""}[it["_route"]]
            if prefill.strip() != want:
                stats[f"cke/{t}/drop:unexpected_prefill:{prefill.strip()[:20]}"] += 1
                continue
            cke_rows.append({"messages": list(msgs) + [{"role": "assistant", "content": it["_target"]}],
                             "meta": {"id": it["id"], "type": "explain" if it["_route"] == "explain" else "decision",
                                      "item_type": t, "route": it["_route"], "source": "cke_human",
                                      "provenance": it["_prov"], "paper": it["_slug"], "chars": len(it["_target"])}})
            stats[f"cke/{t}/kept"] += 1

    # ---------------- RFT rows
    rft = list(build_sft.read_jsonl(a.rft))
    df_r = collections.Counter()
    tasks = [task_text(r["messages"][1]["content"]) for r in rft]
    for tt in set(tasks):
        df_r.update(ngrams(words(tt), Recent.N))
    common_r = {g for g, n in df_r.items() if n >= 3}
    rft_rows = []
    for r, tt in zip(rft, tasks):
        t = r["meta"].get("type")
        if recent.hits(tt, common_r) >= a.recent_min_hits:
            stats[f"rft/{t}/drop:overlap_cke_2023_2026"] += 1
            continue
        r["meta"]["source_set"] = "rft_v3"
        rft_rows.append(r)
        stats[f"rft/{t}/kept"] += 1

    rows = rft_rows + cke_rows
    if not a.dry:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    by = collections.Counter(f"{r['meta'].get('source_set', r['meta'].get('source'))}/"
                             f"{r['meta'].get('source') if 'source_set' in r['meta'] else r['meta']['item_type']}/"
                             f"{r['meta'].get('type')}" for r in rows)
    out = {"rows": len(rows), "rft": len(rft_rows), "cke_human": len(cke_rows), "recent_files": recent.files,
           "dev_files": n_dev, "by_set_source_type": dict(sorted(by.items())), "stats": dict(sorted(stats.items())),
           "cke_prov": dict(collections.Counter(r["meta"]["provenance"] for r in cke_rows)),
           "cke_route": dict(collections.Counter(it["_route"] for it in keep))}
    if not a.dry:
        with open(a.out + ".stats.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
