"""Build + validate dev-b.jsonl (era: nowożytność) from questions.py.

Usage: python build_devb.py WIKI_CACHE_DIR [OUT_JSONL]
  WIKI_CACHE_DIR = output dir of fetch_wiki.py (article extracts, used for URLs and answer checks)
  OUT_JSONL      = default ../dev-b.jsonl
"""
import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from questions import Q  # noqa: E402

WIKI = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "cache")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(HERE), "dev-b.jsonl")
ERA = "nowożytność (ok. 1490–1815)"


def auto_accept(q):
    """Add harmless answer variants (like dev-a): option text for abcd, compact forms for sequences."""
    acc = list(q["accept"])
    if q["type"] == "abcd":
        m = re.search(rf"^{q['answer']}\. (.+)$", q["question"], re.M)
        if m:
            acc += [f"{q['answer']}. {m.group(1)}", m.group(1)]
    elif q["type"] in ("pf", "chrono", "match"):
        acc += [q["answer"].replace(" ", ""), re.sub(r"[ ,]", "", q["answer"])]
    out = []
    for a in acc:
        if a and a != q["answer"] and a not in out:
            out.append(a)
    return out


# article texts / urls
ART = {}
for f in glob.glob(os.path.join(WIKI, "*.json")):
    d = json.load(open(f, encoding="utf-8"))
    if d.get("missing") or len(d.get("extract", "")) < 1000:
        continue
    ART[d["title"]] = d

ORDER = [
    "Wielkie odkrycia geograficzne", "Krzysztof Kolumb", "Traktat z Tordesillas", "Vasco da Gama",
    "Ferdynand Magellan", "Mikołaj Kopernik", "Reformacja", "Marcin Luter", "Jan Kalwin",
    "Hołd pruski 1525", "Sobór trydencki", "Unia lubelska", "Konfederacja warszawska (1573)",
    "Wolna elekcja", "Artykuły henrykowskie", "Henryk III Walezy", "Stefan Batory", "Zygmunt III Waza",
    "Unia brzeska", "Rokosz Zebrzydowskiego", "Bitwa pod Kłuszynem", "Wojna trzydziestoletnia",
    "Bitwa pod Chocimiem (1621)", "Pokój westfalski", "Powstanie Chmielnickiego",
    "Bitwa pod Beresteczkiem", "Potop szwedzki", "Traktaty welawsko-bydgoskie", "Pokój oliwski",
    "Rozejm andruszowski", "Liberum veto", "Ludwik XIV", "Jan III Sobieski", "Bitwa pod Wiedniem",
    "III wojna północna", "Wojna o sukcesję hiszpańską", "Sejm niemy", "Stanisław August Poniatowski",
    "Konfederacja barska", "I rozbiór Polski", "Komisja Edukacji Narodowej",
    "Deklaracja niepodległości Stanów Zjednoczonych", "Sejm Czteroletni", "Rewolucja francuska",
    "Konstytucja 3 maja", "Konfederacja targowicka", "Wojna polsko-rosyjska (1792)", "II rozbiór Polski",
    "Insurekcja kościuszkowska", "Bitwa pod Racławicami", "III rozbiór Polski",
    "Legiony Polskie we Włoszech", "Kodeks Napoleona", "Księstwo Warszawskie", "Pokój w Tylży",
    "Inwazja na Rosję (1812)",
]

errors = []
rank = {t: i for i, t in enumerate(ORDER)}
for q in Q:
    if q["source_title"] not in rank:
        errors.append(f"not in ORDER: {q['source_title']}")
Qs = sorted(enumerate(Q), key=lambda iq: (rank.get(iq[1]["source_title"], 999), iq[0]))

rows = []
for n, (_, q) in enumerate(Qs, 1):
    t = q["source_title"]
    if t not in ART:
        errors.append(f"missing article text: {t}")
        url = ""
    else:
        url = ART[t]["fullurl"]
    rows.append({
        "id": f"dev-b-{n:03d}",
        "era": ERA,
        "type": q["type"],
        "question": q["question"],
        "answer": q["answer"],
        "accept": auto_accept(q),
        "points": q["points"],
        "source_title": t,
        "source_url": url,
    })

# ---- validation
TYPES = {"abcd", "pf", "chrono", "match", "open"}
for r in rows:
    rid, typ, qs, ans = r["id"], r["type"], r["question"], r["answer"]
    if typ not in TYPES:
        errors.append(f"{rid}: bad type {typ}")
    if typ == "abcd":
        if ans not in "ABCD" or len(ans) != 1:
            errors.append(f"{rid}: abcd answer {ans}")
        for L in "ABCD":
            if not re.search(rf"^{L}\. ", qs, re.M):
                errors.append(f"{rid}: missing option {L}")
        if r["points"] != 1:
            errors.append(f"{rid}: abcd points")
    elif typ == "pf":
        items = re.findall(r"^(\d)\. ", qs, re.M)
        if not re.fullmatch(r"[PF](, [PF])+", ans):
            errors.append(f"{rid}: pf answer format {ans}")
        elif len(ans.split(", ")) != len(items):
            errors.append(f"{rid}: pf count {len(items)} vs {ans}")
        if not (2 <= len(items) <= 4):
            errors.append(f"{rid}: pf items {len(items)}")
        exp = 2 if len(items) >= 3 else 1
        if r["points"] != exp:
            errors.append(f"{rid}: pf points")
    elif typ == "chrono":
        labels = re.findall(r"^([A-D])\. ", qs, re.M)
        parts = ans.split(", ")
        if sorted(parts) != sorted(labels) or len(labels) != 4:
            errors.append(f"{rid}: chrono {labels} vs {ans}")
        if ans == "B, A, D, C":
            errors.append(f"{rid}: chrono answer equals instruction example")
        if r["points"] != 2:
            errors.append(f"{rid}: chrono points")
    elif typ == "match":
        nums = re.findall(r"^(\d)\. ", qs, re.M)
        letters = re.findall(r"^([A-D])\. ", qs, re.M)
        m = re.fullmatch(r"(\d-[A-D])(, \d-[A-D])+", ans)
        pairs = [p.split("-") for p in ans.split(", ")]
        if not m or [p[0] for p in pairs] != nums:
            errors.append(f"{rid}: match nums {nums} vs {ans}")
        used = [p[1] for p in pairs]
        if len(set(used)) != len(used) or not set(used) <= set(letters):
            errors.append(f"{rid}: match letters {letters} vs {ans}")
        example = re.search(r"format(?:ie)?: ([0-9A-D, -]+)\.", qs)
        if example and example.group(1) == ans:
            errors.append(f"{rid}: match answer equals format example")
        exp = 2 if len(nums) >= 3 else 1
        if r["points"] != exp:
            errors.append(f"{rid}: match points")
    elif typ == "open":
        if not ans.strip():
            errors.append(f"{rid}: empty open answer")
        txt = ART.get(r["source_title"], {}).get("extract", "").lower()
        cands = [ans] + r["accept"]
        def found(c):
            c = c.lower().rstrip(".")
            if c in txt:
                return True
            # declension-tolerant: every word's 6-char stem must occur, within one window
            stems = [w[:6] for w in re.findall(r"\w+", c)]
            return bool(stems) and re.search(r"\W".join(re.escape(s) + r"\w*" for s in stems), txt) is not None
        if not any(found(c) for c in cands):
            errors.append(f"{rid}: open answer not found verbatim in article ({ans})")
        if r["points"] != 1:
            errors.append(f"{rid}: open points")
    if not isinstance(r["accept"], list):
        errors.append(f"{rid}: accept not list")

# ---- write (LF, UTF-8)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# re-parse
back = [json.loads(line) for line in open(OUT, encoding="utf-8")]
cnt = collections.Counter(r["type"] for r in back)
abcd_dist = collections.Counter(r["answer"] for r in back if r["type"] == "abcd")
arts = collections.Counter(r["source_title"] for r in back)
print("written", OUT, "rows", len(back))
print("types", dict(cnt), {k: f"{100*v/len(back):.1f}%" for k, v in cnt.items()})
print("abcd answer dist", dict(abcd_dist))
print("articles", len(arts), "points total", sum(r["points"] for r in back))
print("ERRORS:" if errors else "no errors", *errors, sep="\n")
