#!/usr/bin/env python
"""Describe every image of an official exam package in Polish with ONE open vision model (llama-server).

    python scripts/describe_images.py data_cke/mock2023 --url http://127.0.0.1:18110
    python scripts/describe_images.py --exam-json /final/exam.json --url http://127.0.0.1:18110 --out desc.json

Output: {"images/X.png": "<opis po polsku>", ...} -- the exact format of harness/exam_runner.py --image-desc
(the runner replaces '[Obraz: images/X.png]' with '[Opis obrazu: <opis>]'). Keys are the `path` values from
exam.json, in exam order; an image that failed maps to "" (the runner then keeps its placeholder).

Team rule (26.09): the vision model ONLY turns images into text; Bielik answers. So the model gets the image
plus the caption printed next to its placeholder in source_text (e.g. 'Źródło 2. Mapa. Wojny Rzymu z
Kartaginą') -- never the question. The prompt asks for a description in the style of CKE's adapted sheets
for blind students (arkusz 660): kind of image, what is where, every legible inscription copied literally,
legend, arrows, colours only when meaningful, no interpretation, no guessing of names that are not written.

--prompt literal: stricter variant (only what is visible; every letter/number/arrow/legend entry of a map
exactly as the legend says; inscriptions verbatim; 'nieczytelne' for unreadable text; no guessing, no
'prawdopodobnie'); its defaults are max_tokens 800 and repeat_penalty 1.05.

Server: any llama-server started with --mmproj (OpenAI chat API, image as a base64 data URL). Requests are
sequential, temperature 0, max_tokens 600 by default; `chat_template_kwargs.enable_thinking=false` is sent so
hybrid thinking models (Qwen3.5) answer directly. Results are cached per image sha256 + model + prompt in
--cache (default <out>.cache.json); per-image latency and token counts go to <out>.meta.json.
Standard library only; no network except the given --url.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

PLACEHOLDER = re.compile(r"\[Obraz:\s*(images/[^\]\s]+)\s*\]")
SOURCE_LINE = re.compile(r"^\s*(Źródło|Zrodlo)\s+(\d+)\.", re.I)
MAX_CAPTION = 220

SYSTEM = """Opisujesz ilustracje z arkusza egzaminu maturalnego z historii dla ucznia niewidomego, tak jak robi to CKE w arkuszach dostosowanych (arkusz 660). Opisujesz wyłącznie to, co widać na obrazie. Nie odpowiadasz na żadne pytania, niczego nie interpretujesz, nie oceniasz i nie dopisujesz wiedzy historycznej spoza obrazu.

Zasady:
1. Zacznij od rodzaju obrazu: mapa, plan, karykatura, plakat, zdjęcie, obraz (malarstwo), rycina, rysunek, moneta, medal, tablica genealogiczna, wykres, tabela, dokument, strona tytułowa gazety lub czasopisma. Na przykład: „Mapa przedstawia…”, „Na rysunku widać…”.
2. Opisz, co jest przedstawione i gdzie: na pierwszym planie, w tle, po lewej, po prawej, u góry, u dołu, w środku.
3. Przepisz dosłownie KAŻDY czytelny napis, podpis, etykietę, objaśnienie legendy, datę, nazwę i liczbę, w oryginalnej pisowni i języku, w cudzysłowie „…”. Na mapie i planie wymień wszystkie nazwy (państw, krain, miast, rzek, mórz, bitew) i daty widoczne na obrazie oraz każdą pozycję legendy z tym, jak jest oznaczona na mapie. W tablicy genealogicznej odtwórz powiązania: kto jest czyim dzieckiem, a kto małżonkiem, z datami, jeśli są wpisane. Na monecie opisz awers i rewers z napisami.
4. Opisz strzałki (skąd dokąd prowadzą, czego dotyczą) i symbole. Kolory podawaj tylko wtedy, gdy mają znaczenie, na przykład w legendzie mapy.
5. Nie zgaduj. Nie podawaj nazwisk, nazw, dat ani miejsc, których nie ma na obrazie, chyba że są całkowicie jednoznaczne. Napis, którego nie da się odczytać, oznacz jako „(nieczytelne)”.
6. Pisz po polsku, rzeczowo, pełnymi zdaniami albo wyliczeniem z myślnikami „– ”. Bez nagłówków, bez pogrubień, bez wstępów typu „Oto opis”. Zwykle 60–250 słów; najwięcej przy mapach, planach i tablicach genealogicznych z wieloma napisami."""

USER = "Podpis obrazu w arkuszu: „{caption}”.\nOpisz ten obraz zgodnie z zasadami."
USER_NOCAP = "Opisz ten obraz zgodnie z zasadami."

# --prompt literal (26.09 ~19:30): the default prompt let Qwen3.5-9B invent names/dates ("prawdopodobnie ..."),
# which cost points on the mock (8 vs 13 with OCR). This variant asks for a strictly literal inventory:
# only what is visible, legend-exact meaning of every mark on maps/plans, inscriptions copied verbatim,
# "nieczytelne" for what cannot be read, no guessing and no interpretation. Defaults: 800 tokens, rp 1.05.
SYSTEM_LITERAL = """Opisujesz ilustrację z arkusza egzaminu maturalnego z historii dla ucznia niewidomego. Opisujesz WYŁĄCZNIE to, co faktycznie widać na obrazie. Nie odpowiadasz na żadne pytania, niczego nie interpretujesz, nie wyjaśniasz znaczenia obrazu i nie dopisujesz wiedzy historycznej spoza obrazu.

Zasady:
1. Pierwsze zdanie podaje rodzaj obrazu: mapa, plan, karykatura, plakat, zdjęcie, obraz (malarstwo), rycina, rysunek, moneta, medal, tablica genealogiczna, wykres, tabela, dokument, strona tytułowa gazety lub czasopisma.
2. Opisz, co widać i gdzie: u góry, u dołu, po lewej, po prawej, w środku, na pierwszym planie, w tle.
3. Przepisz dosłownie KAŻDY napis, podpis, etykietę, datę i liczbę, dokładnie tak, jak są napisane (oryginalna pisownia i język), w cudzysłowie „…”. Nie poprawiaj, nie tłumacz i nie uzupełniaj napisów.
4. Mapa lub plan: wypisz każdą pozycję legendy dokładnie tak, jak jest napisana, razem z jej oznaczeniem (kolor, kreskowanie, linia, symbol). Potem dla każdej litery, cyfry, strzałki i symbolu na mapie podaj, gdzie się znajduje i co oznacza, wyłącznie słowami legendy albo napisu obok niego. Jeśli legenda nie objaśnia oznaczenia, napisz tylko, jak wygląda i gdzie jest. Wymień wszystkie nazwy i daty wpisane na mapie.
5. Strzałki: skąd dokąd prowadzą i jak są oznaczone. Kolory podawaj tylko wtedy, gdy coś oznaczają.
6. Tablica genealogiczna: kto jest czyim dzieckiem, a kto małżonkiem, wyłącznie według wpisanych imion i dat.
7. Napis albo fragment, którego nie da się odczytać, zapisz jako „nieczytelne”.
8. Nigdy nie zgaduj. Nie podawaj nazwisk, nazw, miejsc, dat ani zamiarów, których nie ma napisanych na obrazie. Nie rozpoznawaj osób po wyglądzie: opisz tylko wygląd, strój, gesty i przedmioty. Nie używaj słów „prawdopodobnie”, „zapewne”, „być może”, „symbolizuje”, „sugeruje”, „nawiązuje”.
9. Pisz po polsku, rzeczowo, pełnymi zdaniami albo wyliczeniem z myślnikami „– ”. Bez nagłówków, bez pogrubień, bez wstępów typu „Oto opis”."""

USER_LITERAL = "Podpis obrazu w arkuszu: „{caption}”.\nOpisz ten obraz zgodnie z zasadami: tylko to, co widać, napisy dosłownie."
USER_LITERAL_NOCAP = "Opisz ten obraz zgodnie z zasadami: tylko to, co widać, napisy dosłownie."

# name -> (system, user with caption, user without caption, default max_tokens, default repeat_penalty)
PROMPTS = {
    "default": (SYSTEM, USER, USER_NOCAP, 600, 1.0),
    "literal": (SYSTEM_LITERAL, USER_LITERAL, USER_LITERAL_NOCAP, 800, 1.05),
}


def prompt_version(name: str) -> str:
    system, user, user_nocap = PROMPTS[name][:3]
    return hashlib.sha256((system + user + user_nocap).encode()).hexdigest()[:12]


PROMPT_VERSION = prompt_version("default")  # same hash as before -> old caches stay valid


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def captions_for(item: dict) -> dict[str, str]:
    """Caption of every image of one item, from source_text only (never the question): the 'Źródło N.' line
    matching the image name (…-S<N>.png), else the nearest text line above its placeholder, else the first
    line of source_text. Long lines (running text of another source) are cut to MAX_CAPTION chars."""
    src = item.get("source_text") or ""
    lines = src.splitlines()
    source_lines: dict[str, str] = {}
    for line in lines:
        m = SOURCE_LINE.match(line)
        if m:
            source_lines.setdefault(m.group(2), line.strip())
    out = {}
    for img in item.get("images") or []:
        path = img["path"]
        cap = ""
        m = re.search(r"-S(\d+)\.", path)
        if m and m.group(1) in source_lines:
            cap = source_lines[m.group(1)]
        if not cap:
            for i, line in enumerate(lines):
                if path in line and PLACEHOLDER.search(line):
                    for j in range(i - 1, -1, -1):
                        t = lines[j].strip()
                        if t and not PLACEHOLDER.search(t):
                            cap = t
                            break
                    break
        if not cap:
            cap = next((line.strip() for line in lines if line.strip() and not PLACEHOLDER.search(line)), "")
        if len(cap) > MAX_CAPTION:
            cap = cap[:MAX_CAPTION].rsplit(" ", 1)[0] + "…"
        out[path] = cap
    return out


def post(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def get(url: str, timeout: float = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def model_id(base: str) -> str:
    try:
        d = get(base + "/v1/models")
        return d["data"][0]["id"]
    except Exception:
        return "unknown"


def clean(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = text.replace("**", "").replace("__", "")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*#+\s*", "", line).rstrip()
        line = re.sub(r"^\s*[*•]\s+", "– ", line)
        line = re.sub(r"^\s*-\s+", "– ", line)
        if line.strip():
            lines.append(line.strip())
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(oto opis[^:]{0,40}|opis( obrazu)?)\s*:\s*", "", text, flags=re.I)
    return text


def trim_unfinished(text: str) -> str:
    """Cut a truncated (max_tokens) answer back to its last full sentence or list entry."""
    if text.endswith((".", "”", ")", "\"")):
        return text
    cut = max(text.rfind(". "), text.rfind("; "), text.rfind(".” "))
    if cut < len(text) * 0.5:
        return text + "…"
    return text[:cut + 1].rstrip() if text[cut] in ".;" else text[:cut + 2].rstrip()


def collapse_repeats(text: str) -> str:
    """Drop a sentence/list entry repeated verbatim (small models loop at temperature 0)."""
    parts = re.split(r"(?<=[.;])\s+|\s+(?=– )", text)
    seen, out = set(), []
    for p in parts:
        k = p.strip().lower()
        if k and k in seen and len(k) > 12:
            continue
        seen.add(k)
        out.append(p.strip())
    return " ".join(out)


def describe(base: str, img: Path, caption: str, args) -> dict:
    b64 = base64.b64encode(img.read_bytes()).decode()
    mime = "image/png" if img.suffix.lower() == ".png" else "image/jpeg"
    system, user, user_nocap = PROMPTS[args.prompt][:3]
    user_text = user.format(caption=caption) if caption else user_nocap
    content = [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
               {"type": "text", "text": user_text}]
    if args.no_system:
        messages = [{"role": "user", "content": [{"type": "text", "text": system + "\n\n"}] + content}]
    else:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
    payload = {"messages": messages, "temperature": 0.0, "top_k": 1, "max_tokens": args.max_tokens,
               "repeat_penalty": args.repeat_penalty, "stream": False, "cache_prompt": False}
    if not args.think:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    t0 = time.time()
    r = post(base + "/v1/chat/completions", payload, args.timeout)
    dt = time.time() - t0
    ch = r["choices"][0]
    raw = ch["message"].get("content") or ""
    text = collapse_repeats(clean(raw))
    if ch.get("finish_reason") == "length":
        text = trim_unfinished(text)
    u = r.get("usage") or {}
    return {"text": text, "raw": raw, "finish": ch.get("finish_reason"), "sec": round(dt, 2),
            "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pkg", nargs="?", default="", help="exam package dir (exam.json + images/)")
    ap.add_argument("--exam-json", default="", help="exam.json path (overrides PKG/exam.json); images are "
                                                   "resolved relative to its folder")
    ap.add_argument("--url", default="http://127.0.0.1:18110", help="llama-server base URL (with --mmproj)")
    ap.add_argument("--out", default="", help="output JSON (default <pkg>/image_vlm.json)")
    ap.add_argument("--cache", default="", help="cache JSON (default <out>.cache.json)")
    ap.add_argument("--prompt", choices=sorted(PROMPTS), default="default",
                    help="default = arkusz-660 style; literal = only what is visible, legend-exact, no guessing")
    ap.add_argument("--max-tokens", type=int, default=None, help="default 600 (default prompt) / 800 (literal)")
    ap.add_argument("--repeat-penalty", type=float, default=None, help="default 1.0 / 1.05 (literal)")
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--think", action="store_true", help="do not send enable_thinking=false")
    ap.add_argument("--no-system", action="store_true", help="put the instructions in the user turn")
    ap.add_argument("--only", default="", help="comma-separated image paths to (re)describe")
    ap.add_argument("--refresh", action="store_true", help="ignore the cache")
    args = ap.parse_args()
    if args.max_tokens is None:
        args.max_tokens = PROMPTS[args.prompt][3]
    if args.repeat_penalty is None:
        args.repeat_penalty = PROMPTS[args.prompt][4]
    pver = prompt_version(args.prompt)

    exam_path = Path(args.exam_json) if args.exam_json else Path(args.pkg) / "exam.json"
    if not exam_path.is_file():
        ap.error(f"no exam.json at {exam_path}")
    root = exam_path.parent
    out = Path(args.out) if args.out else root / "image_vlm.json"
    cache_path = Path(args.cache) if args.cache else out.with_name(out.stem + ".cache.json")
    meta_path = out.with_name(out.stem + ".meta.json")
    base = args.url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]

    exam = json.loads(exam_path.read_text(encoding="utf-8"))
    images: dict[str, dict] = {}
    for it in exam["items"]:
        caps = captions_for(it)
        for im in it.get("images") or []:
            e = images.setdefault(im["path"], {"sha256": im.get("sha256", ""), "caption": "", "items": []})
            e["items"].append(it["id"])
            if not e["caption"] and caps.get(im["path"]):
                e["caption"] = caps[im["path"]]
    only = set(filter(None, args.only.split(",")))

    mid = model_id(base)
    cache = {}
    if cache_path.is_file() and not args.refresh:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    result = json.loads(out.read_text(encoding="utf-8")) if out.is_file() and only else {}
    meta = {"model": mid, "url": base, "prompt": args.prompt, "prompt_version": pver,
            "max_tokens": args.max_tokens, "repeat_penalty": args.repeat_penalty,
            "exam": str(exam_path), "images": {}}
    if meta_path.is_file() and only:
        try:
            meta["images"] = json.loads(meta_path.read_text(encoding="utf-8")).get("images", {})
        except Exception:
            pass
    print(f"{len(images)} images, model={mid}, prompt={args.prompt}/{pver} -> {out}", file=sys.stderr)
    fails = 0
    for path, e in images.items():
        if only and path not in only:
            continue
        f = root / path
        if not f.is_file():
            print(f"MISSING {f}", file=sys.stderr)
            result[path] = ""
            fails += 1
            continue
        h = sha256_file(f)
        if e["sha256"] and e["sha256"] != h:
            print(f"WARNING sha256 mismatch {path}", file=sys.stderr)
        key = f"{h}|{mid}|{pver}|{e['caption']}|{args.max_tokens}"
        if args.repeat_penalty != 1.0:
            key += f"|rp{args.repeat_penalty}"
        if key in cache and not only:
            result[path] = cache[key]["text"]
            meta["images"][path] = {**{k: v for k, v in cache[key].items() if k not in ("text", "raw")},
                                    "cached": True}
            continue
        rec, err = None, ""
        for attempt in range(args.retries + 1):
            try:
                rec = describe(base, f, e["caption"], args)
                if rec["text"]:
                    break
                err = "empty"
            except Exception as ex:  # noqa: BLE001
                err = f"{type(ex).__name__}: {ex}"[:300]
                time.sleep(3)
        if rec and rec["text"]:
            cache[key] = rec
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            result[path] = rec["text"]
            meta["images"][path] = {k: v for k, v in rec.items() if k not in ("text", "raw")}
            print(f"{path}\t{rec['sec']}s\t{rec['completion_tokens']} tok\t{rec['finish']}\t{len(rec['text'])} ch",
                  file=sys.stderr)
        else:
            result[path] = ""
            meta["images"][path] = {"error": err}
            fails += 1
            print(f"{path}\tFAIL {err}", file=sys.stderr)
    ordered = {p: result.get(p, "") for p in images}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ordered, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    secs = [m["sec"] for m in meta["images"].values() if isinstance(m, dict) and m.get("sec")]
    meta["n"] = len(ordered)
    meta["failed"] = fails
    meta["sec_mean"] = round(sum(secs) / len(secs), 2) if secs else None
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"done: {len(ordered) - fails}/{len(ordered)} described, mean {meta['sec_mean']} s/image -> {out}",
          file=sys.stderr)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
