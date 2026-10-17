"""Golden record of every prompt the harness sends (LLM messages + sampling args, retrieval and reranker
queries) for a fixed set of synthetic items, with a fake LLM / KB / reranker. Used by tests/test_v4.py to
prove that with every V4 flag off the v1/v2/v3 prompts are byte-identical to the pre-v4 code.

All item texts are our own wording in the CKE / dev-set layout (no CKE text).
Regenerate the fixture ONLY from the pre-v4 code (it is the reference):
    python tests/v3_golden.py --write tests/fixtures/v3_prompts.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ITEMS = {
    "abcd_plain": ("Który władca zwołał sejm do Piotrkowa w roku 1496?\nA. Jan Olbracht\nB. Aleksander Jagiellończyk\n"
                   "C. Zygmunt Stary\nD. Kazimierz Jagiellończyk"),
    "abcd_src": ("Źródło. Fragment kroniki\nW tym roku król zwołał posłów ziemskich do Piotrkowa i wydał przywileje "
                 "dla szlachty, ograniczające prawa mieszczan do nabywania ziemi.\nNa podstawie: Kronika, s. 3.\n"
                 "Dokończ zdanie. Zaznacz właściwą odpowiedź spośród podanych.\nPrzywileje opisane w źródle wydał\n"
                 "A. Jan Olbracht.\nB. Aleksander Jagiellończyk.\nC. Zygmunt Stary.\nD. Stefan Batory."),
    "pf_src": ("Źródło. Napis na medalu\n„Odzyskana twierdza nad Dniestrem wraca do Rzeczypospolitej po latach niewoli”.\n"
               "Oceń prawdziwość poniższych stwierdzeń. Napisz P, jeśli stwierdzenie jest prawdziwe, albo F – jeśli "
               "jest fałszywe.\n1. Traktat upamiętniony na medalu podpisano za panowania Jana III Sobieskiego.\n"
               "2. Traktat upamiętniony na medalu kończył wojny z Portą Osmańską.\nOdpowiedz w formacie: P/F, P/F."),
    "pf_wiki": ("Oceń prawdziwość zdań dotyczących konstytucji marcowej.\n1. Konstytucję uchwalono w 1921 roku.\n"
                "2. Wprowadzała ostatecznie ustrój prezydencki.\n3. Parlament składał się z sejmu i senatu.\n"
                "Odpowiedz w formacie: P, F, P."),
    "match_example": ("Dopasuj państwo zaborcze do ziem, które zajęło w trzecim rozbiorze.\n1. Austria\n2. Prusy\n"
                      "3. Rosja\nA. ziemie na wschód od Niemna\nB. reszta Małopolski z Krakowem\n"
                      "C. część Mazowsza z Warszawą\nOdpowiedz w formacie: 1-B, 2-A, 3-C."),
    "abcd_parts": ("Źródło. Fragment rozkazu\nZnoszę nazwę dotychczasowej organizacji. Wszyscy żołnierze w kraju "
                   "tworzą odtąd armię podległą Panu Generałowi jako jej dowódcy.\nNACZELNY WÓDZ\n"
                   "Dokończ zdania 1. i 2. Zaznacz właściwą odpowiedź spośród podanych.\n"
                   "1. Rozkaz był skierowany do generała\nA. Michała Tokarzewskiego.\nB. Stefana Roweckiego.\n"
                   "C. Tadeusza Komorowskiego.\nD. Leopolda Okulickiego.\n2. Rozkaz podpisał generał\n"
                   "A. Władysław Anders.\nB. Kazimierz Sosnkowski.\nC. Władysław Sikorski.\nD. Emil Fieldorf."),
    "chrono_bc": ("Poniżej wymieniono wydarzenia z okresu drugiej wojny Rzymu z Kartaginą.\nA. bitwa pod Kannami\n"
                  "B. zdobycie Syrakuz\nC. bitwa nad Metaurusem\nD. kapitulacja Saguntu\n"
                  "Uporządkuj wydarzenia chronologicznie (od najwcześniejszego). Odpowiedz ciągiem liter "
                  "oddzielonych przecinkami, np. B, A, D, C."),
    "names": ("Źródło 1. Lista władców\nMieszko II, Kazimierz Odnowiciel, Bolesław Śmiały.\n"
              "Źródło 2. Fragmenty opracowań\nFragment A:\nWładca odbudował państwo po najeździe i przeniósł główny "
              "ośrodek władzy do Krakowa, co umocniło kraj.\nFragment B:\nWładca koronował się w Gnieźnie, a potem "
              "popadł w konflikt z biskupem krakowskim i musiał uchodzić z kraju.\nKażdemu wydarzeniu opisanemu we "
              "fragmentach A–B (źródło 2.) przyporządkuj\nwładcę ze źródła 1., który był związany z tym wydarzeniem. "
              "Odpowiedzi zapisz poniżej.\nFragment A –\nFragment B –"),
    "decision": ("Źródło 1. Tekst\nOpis wydarzeń w zaborze pruskim, w tym strajk dzieci we Wrześni w roku 1901.\n"
                 "Źródło 2. Tekst\nOpis wydarzeń w zaborze rosyjskim, w tym rewolucja w Łodzi w roku 1905.\n"
                 "Rozstrzygnij, czy źródła 1. i 2. dotyczą tego samego zaboru. Odpowiedź uzasadnij, odwołując się "
                 "do obu źródeł.\nRozstrzygnięcie:\nUzasadnienie:"),
    "explain": ("Źródło. Fragment odezwy\nWzywamy wszystkich do walki o wolność i całość ojczyzny przeciw zaborcom.\n"
                "Wyjaśnij, do jakiego wydarzenia odnosi się odezwa. W odpowiedzi odwołaj się do treści źródła."),
    "open": "W którym roku odbyła się bitwa pod Grunwaldem?",
}


def _crc(s: str) -> int:
    return zlib.crc32(s.encode("utf-8"))


class FakeLLM:
    def __init__(self):
        self.calls: list[dict] = []

    async def lora_zero(self):
        return {"lora": [{"id": 0, "scale": 0.0}]}

    async def chat(self, messages, **kw):
        self.calls.append({"messages": messages, **kw})
        g = kw.get("grammar") or ""
        pre = messages[-1]["content"] if messages and messages[-1]["role"] == "assistant" else ""
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if "Y ::=" in g:
            labs = [ln.split(":")[0].strip().strip('"') for ln in g.split("root ::= ", 1)[1].split('"\\n"')]
            txt = "\n".join(f"{l}: {1400 + 10 * (i % 2)}" for i, l in enumerate(labs))
        elif 'V ::= "P" | "F"' in g:
            n = g.count('" V')
            txt = "\n".join(f"{i}: {'P' if i % 2 else 'F'}" for i in range(1, n + 1))
        elif g:
            txt = g.split('"')[1] if '"' in g else "A"
        elif pre.startswith("Kto:"):
            txt = " książę\nCo: wiec\nKiedy: 1901\nGdzie: Gniezno"
        elif pre.startswith("Rozstrzygnięcie:"):
            txt = " Tak\nUzasadnienie: Źródło 1 opisuje Wrześnię, a źródło 2 Łódź."
            if kw.get("logprobs"):
                return {"choices": [{"message": {"content": txt}, "finish_reason": "stop",
                                     "logprobs": {"content": [{"token": " Tak", "logprob": -0.4,
                                                               "top_logprobs": [{"token": " Tak", "logprob": -0.4},
                                                                                {"token": " Nie", "logprob": -1.1}]}]}}]}
        elif pre.startswith("Rozumowanie:"):
            txt = f" Rozumowanie próbne {_crc(user) % 97}.\nOdpowiedź: A"
        else:
            txt = f"Odpowiedź próbna {_crc(user) % 89}."
        return {"choices": [{"message": {"content": txt}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


class FakeReranker:
    def __init__(self, log):
        self.log = log

    def score(self, query, docs):
        self.log.append({"rerank_query": query, "n_docs": len(docs)})
        return [float((_crc(query + d) % 1000) / 100.0) for d in docs]

    def status(self):
        return {}


class FakeRetriever:
    available = True

    def __init__(self):
        self.log: list = []
        self.reranker = FakeReranker(self.log)

    def search(self, query, k):
        self.log.append({"search": query, "k": k})
        h = _crc(query)
        out = []
        for i in range(k):
            t = ["Wojna trzydziestoletnia", "II wojna trzydziestoletnia", "I wojna punicka", "II wojna punicka",
                 "III rozbiór Polski", "Rozbiory Polski", "Konstytucja marcowa", "Konstytucja kwietniowa",
                 "Bitwa pod Grunwaldem", "Pokój w Karłowicach"][(h + i) % 10]
            out.append({"title": t, "section": f"s{(h >> 3) % 5}",
                        "text": f"{t}: fragment {i} o numerze {(h + i) % 1000}; w roku 216 p.n.e. Hannibal.",
                        "url": "", "score": float(k - i)})
        return out

    def dense_search(self, q, s):
        return []


CONFIGS = {
    "v1_default": {},
    "v2_rerank": {"qtype_v2": True, "rerank": True},
    "v3_cke": {"cke_mode": True, "qtype_v2": True, "rerank": True},
    "v3_cke_nokb": {"cke_mode": True, "qtype_v2": True, "use_kb": False},
}


def record(extra: dict | None = None) -> dict:
    """{config: {item: {'answer', 'calls' (sorted JSON strings), 'retrieval' (sorted JSON strings)}}}"""
    from harness.config import Settings
    from harness.pipeline import Pipeline
    out: dict = {}
    for cname, cfg in CONFIGS.items():
        out[cname] = {}
        for iname, text in ITEMS.items():
            s = Settings()
            for k, v in {**cfg, **(extra or {})}.items():
                setattr(s, k, v)
            llm, kb = FakeLLM(), FakeRetriever()
            if not s.use_kb:
                kb.available = False
            pipe = Pipeline(s, llm, kb)
            res = asyncio.run(pipe.answer(text))
            out[cname][iname] = {
                "answer": res.answer,
                "calls": sorted(json.dumps(c, ensure_ascii=False, sort_keys=True) for c in llm.calls),
                "retrieval": sorted(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in kb.log),
            }
    return out


def _clean_env():
    for k in list(os.environ):
        if k.startswith(("V4", "SC_", "CKE_", "QTYPE_V2", "RERANK", "CHRONO_", "PF_MODE", "DENSE", "N_VOTES",
                         "THINK", "TOP_K", "CTX_TOKENS", "USE_KB", "USE_GRAMMAR", "TEMPERATURE")):
            os.environ.pop(k)


if __name__ == "__main__":
    _clean_env()
    if len(sys.argv) == 3 and sys.argv[1] == "--write":
        data = record()
        os.makedirs(os.path.dirname(os.path.abspath(sys.argv[2])), exist_ok=True)
        with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        n = sum(len(v["calls"]) for c in data.values() for v in c.values())
        print(f"wrote {sys.argv[2]}: {n} LLM calls")
    else:
        print(__doc__)
