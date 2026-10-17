"""Fake LLM / KB / reranker for the CKE_MODE essay flow (harness/cke_flow.py essay_flow) and the golden record of
every prompt it sends. Used by tests/test_essay_safe.py to prove that with ESSAY_SAFE off the essay output and all
prompts are byte-identical to the code before the safe mode was added.

All texts below are our own wording (synthetic topics and passages; no CKE text).
Regenerate the fixture ONLY from the pre-ESSAY_SAFE code (it is the reference):
    python tests/essay_fakes.py --write tests/fixtures/essay_off_golden.json
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

QUESTION = """Zadanie 26. (0–15)
Zadanie zawiera trzy tematy. Wybierz jeden z nich do opracowania. Twoja wypowiedź
powinna liczyć minimum 300 wyrazów.

1. Hołd pruski był największym sukcesem dyplomacji ostatnich Jagiellonów. Zajmij stanowisko
wobec powyższej tezy i je uzasadnij, uwzględniając w swojej argumentacji aspekty: polityczny
i militarny.

2. Kongres wiedeński zapewnił Europie trwały pokój. Zajmij stanowisko wobec powyższej tezy
i je uzasadnij, uwzględniając w swojej argumentacji aspekt ustrojowy, międzynarodowy i społeczny.

3. Odwilż 1956 roku zmieniła PRL tylko pozornie. Zajmij stanowisko wobec powyższej tezy i je
uzasadnij, charakteryzując trzy wybrane wydarzenia z lat 1956–1970.

WYPRACOWANIE
na temat nr ……
"""

PASSAGES = [
    ("Poznański Czerwiec", "Poznański Czerwiec – strajk i demonstracje robotników Poznania 28 czerwca 1956 roku, "
                           "stłumione przez wojsko i milicję. Zginęło kilkadziesiąt osób."),
    ("Polski Październik", "W październiku 1956 roku Władysław Gomułka został wybrany na I sekretarza KC PZPR. "
                           "Ograniczono kolektywizację wsi i złagodzono cenzurę."),
    ("Marzec 1968", "W marcu 1968 roku studenci Warszawy protestowali po zdjęciu z afisza Dziadów w Teatrze "
                    "Narodowym. Władze rozpętały kampanię antysemicką."),
    ("Grudzień 1970", "W grudniu 1970 roku po podwyżce cen robotnicy stoczni Wybrzeża rozpoczęli strajk. Gomułkę "
                      "zastąpił Edward Gierek."),
    ("Powstanie węgierskie", "Powstanie węgierskie wybuchło 23 października 1956 roku w Budapeszcie i zostało "
                             "stłumione przez armię radziecką."),
    ("Józef Stalin", "Józef Stalin zmarł w marcu 1953 roku w Moskwie."),
    ("Kongres wiedeński", "Kongres wiedeński obradował od września 1814 do czerwca 1815 roku. Utworzono Królestwo "
                          "Polskie związane unią z Rosją."),
    ("Hołd pruski", "Hołd pruski złożył Albrecht Hohenzollern królowi Zygmuntowi Staremu w Krakowie 10 kwietnia "
                    "1525 roku. Prusy Książęce stały się lennem Polski."),
    ("Święte Przymierze", "W 1815 roku monarchowie Rosji, Austrii i Prus zawarli Święte Przymierze."),
    ("Wojna pruska", "Wojna pruska toczyła się w latach 1519–1521 i zakończyła się rozejmem w Toruniu."),
]

BODIES = [
    ("{e} pokazuje, że teza jest trafna. W czerwcu 1956 roku robotnicy Poznania rozpoczęli strajk, który stłumiło "
     "wojsko. W listopadzie 1956 roku Władysław Gomułka został I sekretarzem KC PZPR. W 1957 roku władze powołały "
     "nową instytucję. W marcu 1968 roku studenci Warszawy protestowali po zdjęciu Dziadów. W 1953 roku wybuchło "
     "powstanie węgierskie. Władze odpowiedziały represjami, a wielu uczestników protestów straciło pracę i musiało "
     "wyjechać z kraju. Społeczeństwo coraz wyraźniej dostrzegało, że obietnice z okresu przemian nie zostały "
     "spełnione. Cenzura znów się zaostrzyła, a swobody obiecane robotnikom i studentom stopniowo odbierano. "
     "Zaufanie do rządzących malało z każdym rokiem. To wydarzenie potwierdza, że zmiany po przełomie były "
     "w dużej mierze pozorne."),
    ("{e} wyraźnie wiąże się z tezą. W grudniu 1970 roku robotnicy stoczni Wybrzeża rozpoczęli strajk po podwyżce "
     "cen. W styczniu 1970 roku Edward Gierek zastąpił Gomułkę. W 1971 roku rząd cofnął podwyżki, co uspokoiło "
     "nastroje na krótko. W 1965 roku stocznie otrzymały nowe zamówienia. Przemoc wobec robotników podważyła "
     "zaufanie do partii i pokazała granice liberalizacji. Nowa ekipa zapowiadała modernizację, lecz nie zmieniła "
     "podstaw systemu. Decyzje nadal zapadały w wąskim gronie kierownictwa, bez udziału obywateli. Robotnicy "
     "zapamiętali, że władza strzelała do protestujących. Ten przykład dowodzi, że przemiany miały charakter "
     "powierzchowny."),
    ("{e} również przemawia za przyjętym stanowiskiem. 23 października 1956 roku w Budapeszcie wybuchło powstanie "
     "węgierskie. 25 października 1956 roku armia radziecka stłumiła powstanie. W marcu 1953 roku zmarł Józef "
     "Stalin, co zapoczątkowało odwilż w całym bloku. W 1954 roku Polacy obserwowali wydarzenia na Węgrzech "
     "z niepokojem. Doświadczenie sąsiadów przekonało wielu, że otwarty bunt nie ma szans. Kierownictwo partii "
     "wykorzystało te obawy, by ograniczyć żądania reform. Nadzieje na demokratyzację szybko osłabły, a aparat "
     "bezpieczeństwa odzyskał dawną pozycję. Ten przykład także pokazuje, że swoboda po przełomie była "
     "ograniczona."),
]
INTRO = ("Okres po przełomie przyniósł wiele zmian w państwie i społeczeństwie. Rządzący zapowiadali odnowę, "
         "a obywatele liczyli na większą swobodę i lepsze warunki życia. Zgadzam się z tezą, ponieważ wiele "
         "reform okazało się nietrwałych, a władza szybko wróciła do dawnych metod. Uzasadnię to stanowisko, omawiając "
         "trzy wybrane wydarzenia i ich skutki dla obywateli.")
END = ("Podsumowując, omówione wydarzenia pokazują, że zmiany były w dużej mierze pozorne. Władza zachowała kontrolę "
       "nad państwem, a społeczeństwo wielokrotnie protestowało przeciw jej decyzjom. Dlatego podtrzymuję stanowisko "
       "przedstawione we wstępie.")
COMPARE = ("W porównaniu z wojną pruską hołd pruski przyniósł trwalsze skutki. Wojna pruska toczyła się w latach "
           "1519–1521. Rozejm w Toruniu nie rozwiązał sporu. Dlatego stanowisko pozostaje uzasadnione.")


def _crc(s: str) -> int:
    return zlib.crc32(s.encode("utf-8"))


class FakeEssayLLM:
    def __init__(self, bodies: list[str] | None = None):
        self.calls: list[dict] = []
        self.bodies = bodies or BODIES
        self.nb = 0

    async def lora_zero(self):
        return {"lora": [{"id": 0, "scale": 0.0}]}

    async def chat(self, messages, **kw):
        self.calls.append({"messages": messages, **kw})
        pre = messages[-1]["content"] if messages and messages[-1]["role"] == "assistant" else ""
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if pre == "1.":
            txt = " Poznański Czerwiec (1956)\n2. Marzec 1968 (1968)\n3. Grudzień 1970 (1970)\n4. Wybory 1947 (1947)"
        elif pre.startswith("Alternatywa"):
            txt = " Wojna pruska"
        elif "Napisz wstęp" in user:
            txt = INTRO
        elif "Napisz akapit rozwinięcia" in user:
            m = re.search(r"dotyczący (?:aspektu|\w+): ([^.]+)\.", user)
            txt = self.bodies[self.nb % len(self.bodies)].format(e=(m.group(1) if m else "Ten element").strip())
            self.nb += 1
        elif "porównasz" in user:
            txt = COMPARE
        elif "Napisz zakończenie" in user:
            txt = END
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


class FakeEssayKB:
    available = True

    def __init__(self):
        self.log: list = []
        self.reranker = FakeReranker(self.log)

    def search(self, query, k):
        self.log.append({"search": query, "k": k})
        h = _crc(query)
        out = []
        for i in range(min(k, len(PASSAGES))):
            t, txt = PASSAGES[(h + i) % len(PASSAGES)]
            out.append({"title": t, "section": "", "text": txt, "url": "", "score": float(k - i)})
        return out

    def dense_search(self, q, s):
        return []


CONFIGS = {"auto": {}, "topic1": {"essay_topic": 1}, "topic3": {"essay_topic": 3}}


def run_essay(extra: dict | None = None, bodies: list[str] | None = None):
    """-> (Result, FakeEssayLLM, FakeEssayKB) for QUESTION under CKE_MODE=1 QTYPE_V2=1 RERANK=1 + `extra`."""
    from harness.config import Settings
    from harness.pipeline import Pipeline
    s = Settings()
    for k, v in {"cke_mode": True, "qtype_v2": True, "rerank": True, **(extra or {})}.items():
        setattr(s, k, v)
    llm, kb = FakeEssayLLM(bodies), FakeEssayKB()
    res = asyncio.run(Pipeline(s, llm, kb).answer(QUESTION))
    return res, llm, kb


def record(extra: dict | None = None) -> dict:
    out = {}
    for name, cfg in CONFIGS.items():
        res, llm, kb = run_essay({**cfg, **(extra or {})})
        out[name] = {
            "answer": res.answer,
            "essay_meta": json.loads(json.dumps(res.parsed.get("essay"), ensure_ascii=False, default=str)),
            "calls": sorted(json.dumps(c, ensure_ascii=False, sort_keys=True) for c in llm.calls),
            "retrieval": sorted(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in kb.log),
        }
    return out


def clean_env():
    for k in list(os.environ):
        if k.startswith(("V4", "SC_", "CKE_", "ESSAY", "QTYPE_V2", "RERANK", "CHRONO_", "PF_MODE", "DENSE",
                         "N_VOTES", "THINK", "TOP_K", "CTX_TOKENS", "USE_KB", "USE_GRAMMAR", "TEMPERATURE")):
            os.environ.pop(k)


if __name__ == "__main__":
    clean_env()
    if len(sys.argv) == 3 and sys.argv[1] == "--write":
        data = record()
        os.makedirs(os.path.dirname(os.path.abspath(sys.argv[2])), exist_ok=True)
        with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        print(f"wrote {sys.argv[2]}: " + ", ".join(f"{k}: {len(v['calls'])} calls, meta topic "
                                                    f"{(v['essay_meta'] or {}).get('topic')}" for k, v in data.items()))
    else:
        print(__doc__)
