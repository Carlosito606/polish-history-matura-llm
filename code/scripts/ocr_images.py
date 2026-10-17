#!/usr/bin/env python
"""Offline OCR of the images in an official exam package -> image-description JSON for exam_runner.

    python scripts/ocr_images.py data_cke/mock2023                # -> data_cke/mock2023/image_ocr.json
    python scripts/ocr_images.py PKG_DIR --out X.json --jobs 2 --tesseract /usr/bin/tesseract

Output: {"images/X.png": "Tekst widoczny na obrazie (OCR): ..."} -- the exact format of
harness/exam_runner.py --image-desc. An image with no readable text maps to "" (the runner then keeps
its '[Obraz: ...]' placeholder).

Engine: Tesseract (classic OCR, not an LLM), Polish model `pol`, run as a subprocess; no network.
Pillow (optional) upscales and rotates the image first: small map labels need ~3x, vertical labels need
90/270-degree passes. Without Pillow only one pass on the original file runs.
Passes (per image):  psm 3 (page layout, x2) for text blocks/captions;
                     psm 11 (sparse text) at x2, x3, x4 for scattered map/diagram labels;
                     psm 11 at 90 and 270 degrees (x2, x3; stricter filter) for vertical labels.
A sparse label is kept when one pass reads it at confidence >= 88 or two passes agree.
Filtering drops OCR garbage (hatching and drawings read as letters): tokens with no letter/digit,
low-confidence tokens, short letter-only tokens without a vowel, lines under 3 chars; each image is capped
at --max-chars (default 800). Duplicate labels across passes are kept once.

Raw word lists are cached per image sha256 in --cache (default: <out>.cache.json), so changing the filters
never re-runs OCR. Engine name, version and tessdata location are written to <out>.meta.json.
Standard library + optional Pillow only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PREFIX = "Tekst widoczny na obrazie (OCR): "
VOWELS = set("aeiouyąęóAEIOUYĄĘÓ")
# (key, psm, scale, rotation) ; rotation = degrees counter-clockwise (PIL Image.rotate)
PASSES = [("p3x2", 3, 2, 0),
          ("p11x2", 11, 2, 0), ("p11x3", 11, 3, 0), ("p11x4", 11, 4, 0),
          ("p11x2r90", 11, 2, 90), ("p11x3r90", 11, 3, 90), ("p11x2r270", 11, 2, 270), ("p11x3r270", 11, 3, 270)]
DPI = 300  # declared to tesseract for every pass (its text-size heuristics); part of the cache key
FALLBACK_PASSES = [("p3x1", 3, 1, 0), ("p11x1", 11, 1, 0)]

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None


# ---------------------------------------------------------------------------------------------- engine
def engine_info(exe: str, lang: str, tessdata: str | None) -> dict:
    ver = subprocess.run([exe, "--version"], capture_output=True, text=True)
    first = (ver.stdout or ver.stderr).strip().splitlines()
    cmd = [exe, "--list-langs"] + (["--tessdata-dir", tessdata] if tessdata else [])
    langs = subprocess.run(cmd, capture_output=True, text=True)
    out = (langs.stdout + langs.stderr)
    m = re.search(r'List of available languages(?: in "([^"]+)")?', out)
    listed = [l.strip() for l in out.splitlines()[1:] if l.strip()]
    if lang not in listed:
        sys.exit(f"tesseract language '{lang}' not installed (have {listed}); "
                 "apt-get install tesseract-ocr-pol or pass --tessdata DIR")
    tdir = tessdata or (m.group(1) if m and m.group(1) else os.environ.get("TESSDATA_PREFIX", ""))
    if not tdir:
        for c in ("/usr/share/tesseract-ocr/5/tessdata", "/usr/share/tesseract-ocr/4.00/tessdata",
                  "/opt/homebrew/share/tessdata", "/usr/local/share/tessdata"):
            if Path(c, f"{lang}.traineddata").exists():
                tdir = c
                break
    model = Path(tdir, f"{lang}.traineddata") if tdir else None
    return {"engine": "tesseract", "exe": shutil.which(exe) or exe, "version": first[0] if first else "?",
            "version_full": first[:2], "lang": lang, "tessdata_dir": tdir,
            "model_file": str(model) if model else "",
            "model_sha256": sha256_file(model) if model and model.exists() else "",
            "pillow": getattr(sys.modules.get("PIL"), "__version__", None) if Image else None}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_pass(exe: str, lang: str, tessdata: str | None, img: Path, psm: int, scale: int, rot: int) -> list:
    """One tesseract pass -> list of words [text, conf, block, par, line, left, top]."""
    with tempfile.TemporaryDirectory() as td:
        src = img
        if Image is not None and (scale != 1 or rot):
            im = Image.open(img).convert("L")
            if scale != 1:
                im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
            if rot:
                im = im.rotate(rot, expand=True, fillcolor=255)
            src = Path(td) / "in.png"
            im.save(src)
        base = Path(td) / "out"
        cmd = [exe, str(src), str(base), "-l", lang, "--psm", str(psm), "--dpi", str(DPI)]
        if tessdata:
            cmd += ["--tessdata-dir", tessdata]
        cmd += ["tsv"]
        env = dict(os.environ, OMP_THREAD_LIMIT="1")
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        tsv = base.with_suffix(".tsv")
        if r.returncode != 0 or not tsv.exists():
            raise RuntimeError(f"tesseract failed on {img.name}: {r.stderr[-400:]}")
        words = []
        for row in tsv.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            f = row.split("\t")
            if len(f) < 12 or f[0] != "5" or not f[11].strip():
                continue
            words.append([f[11].strip(), float(f[10]), int(f[2]), int(f[3]), int(f[4]), int(f[6]), int(f[7])])
        return words


# ---------------------------------------------------------------------------------------------- filters
def _core(tok: str) -> str:
    return re.sub(r"^[^\w]+|[^\w.]+$", "", tok).rstrip(".") if tok else ""


def good_token(tok: str, conf: float, strict: bool) -> bool:
    """Sparse-label rule: letters>=3 with a vowel (or >=4 in strict/rotated passes), or a 3-4 digit number
    (years), at a confidence threshold; rejects runs of hatching glyphs like 'LLL', 'IIl1'."""
    c = _core(tok)
    if not c or not re.search(r"\w", c):
        return False
    letters = [ch for ch in c if ch.isalpha()]
    digits = [ch for ch in c if ch.isdigit()]
    if letters and len(set(ch.lower() for ch in letters)) < 2:
        return False
    if strict:
        return conf >= 80 and len(letters) >= 4 and bool(VOWELS & set(letters)) and not digits
    if not letters:
        return conf >= 75 and 3 <= len(digits) <= 4 and re.fullmatch(r"\d{3,4}(r?\.?)?", c) is not None
    return conf >= 70 and len(letters) >= 3 and bool(VOWELS & set(letters))


def text_lines(words: list) -> list[str]:
    """psm 3 pass: keep a line when its mean confidence is high and it has real words; inside it drop tokens
    without letters/digits or with very low confidence."""
    lines: dict[tuple, list] = {}
    for w in words:
        lines.setdefault((w[2], w[3], w[4]), []).append(w)
    out = []
    for key in sorted(lines, key=lambda k: (min(w[6] for w in lines[k]), min(w[5] for w in lines[k]))):
        ws = sorted(lines[key], key=lambda w: w[5])
        ws = [w for w in ws if re.search(r"\w", w[0]) and w[1] >= 40]
        if not ws:
            continue
        mean = sum(w[1] for w in ws) / len(ws)
        real = [w for w in ws if good_token(w[0], w[1], False)]
        line = " ".join(w[0] for w in ws).strip()
        if mean >= 70 and real and len(line) >= 3:
            out.append(line)
        elif len(ws) == 1 and good_token(ws[0][0], ws[0][1], False) and len(line) >= 3:
            out.append(line)
    return out


def norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower())


def fold(s: str) -> str:
    """Dedup key: lower case, no diacritics (WIEŻOWA == WIEZOWA), letters/digits only."""
    s = unicodedata.normalize("NFKD", s.lower().replace("ł", "l"))
    return re.sub(r"[^\w]", "", "".join(ch for ch in s if not unicodedata.combining(ch)))


def describe(passes: dict, max_chars: int) -> str:
    parts: list[str] = []
    seen_text = ""
    for key in ("p3x2", "p3x1"):
        for line in text_lines(passes.get(key, [])):
            if fold(line) and fold(line) not in seen_text:
                parts.append(line)
                seen_text += " " + fold(line)
    # sparse labels: union over scales/rotations; a label is kept when one pass reads it with high
    # confidence or at least two passes agree (single low-confidence reads are mostly hatching noise)
    cands: dict[str, dict] = {}
    for key, psm, scale, rot in PASSES + FALLBACK_PASSES:
        if psm != 11 or key not in passes:
            continue
        strict = rot != 0
        for w in passes[key]:
            if not good_token(w[0], w[1], strict):
                continue
            tok = w[0].strip(",;:\"'()[]|„”")
            k = fold(tok)
            if not k:
                continue
            c = cands.setdefault(k, {"tok": tok, "conf": w[1], "n": 0, "pos": (rot != 0, w[6] / scale, w[5] / scale)})
            c["n"] += 1
            better = (w[1], sum(ord(ch) > 127 for ch in tok)) > (c["conf"], sum(ord(ch) > 127 for ch in c["tok"]))
            if better:
                c.update(tok=tok, conf=w[1])
    for k, c in sorted(cands.items(), key=lambda kv: kv[1]["pos"]):
        if (c["conf"] >= 88 or c["n"] >= 2) and k not in seen_text:
            parts.append(c["tok"])
            seen_text += " " + k
    if not parts:
        return ""
    body, total = [], 0
    for p in parts:
        if total + len(p) + 3 > max_chars:
            break
        body.append(p)
        total += len(p) + 3
    return PREFIX + " / ".join(body)


def transcribed(text: str, source: str, thr: float) -> bool:
    """True when the item text supplies a transcription and most OCR words (>= 3 letters) are already in it."""
    if "transkrypcj" not in source.lower():
        return False
    src = set(fold(w) for w in re.findall(r"\w+", source))
    words = [fold(w) for w in re.findall(r"\w+", text[len(PREFIX):]) if len(w) >= 3]
    return bool(words) and sum(w in src for w in words) / len(words) >= thr


# ---------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package", help="exam package dir (exam.json + images/)")
    ap.add_argument("--out", default="", help="output JSON (default <package>/image_ocr.json)")
    ap.add_argument("--cache", default="", help="raw OCR cache (default <out>.cache.json)")
    ap.add_argument("--tesseract", default=os.environ.get("TESSERACT", "tesseract"))
    ap.add_argument("--tessdata", default=os.environ.get("TESSDATA_DIR") or None,
                    help="dir with pol.traineddata (default: the engine's own)")
    ap.add_argument("--lang", default="pol")
    ap.add_argument("--jobs", type=int, default=2, help="parallel tesseract processes (1 thread each)")
    ap.add_argument("--max-chars", type=int, default=800)
    ap.add_argument("--overlap", type=float, default=0.5,
                    help="drop an image's OCR text when this share of its words already appears in a source_text "
                         "that says 'Transkrypcja' (the organizers supplied the image text)")
    args = ap.parse_args()

    pkg = Path(args.package)
    exam_path = pkg / "exam.json" if pkg.is_dir() else pkg
    pkg = exam_path.parent
    out = Path(args.out) if args.out else pkg / "image_ocr.json"
    cache_path = Path(args.cache) if args.cache else out.with_name(out.stem + ".cache.json")
    exam = json.loads(exam_path.read_text(encoding="utf-8"))

    images: dict[str, str] = {}  # path -> expected sha256 ("" if not given)
    sources: dict[str, str] = {}  # path -> source_text of the items that show it
    for it in exam.get("items", []):
        for im in it.get("images") or []:
            if im.get("path"):
                images.setdefault(im["path"], im.get("sha256", ""))
                if (it.get("source_text") or "") not in sources.get(im["path"], ""):
                    sources[im["path"]] = sources.get(im["path"], "") + "\n" + (it.get("source_text") or "")
    if not images:
        print("no images in exam.json")
    info = engine_info(args.tesseract, args.lang, args.tessdata)
    passes = PASSES if Image is not None else FALLBACK_PASSES
    if Image is None:
        print("WARNING: Pillow not installed -> no upscaling/rotation, weaker OCR on small labels", file=sys.stderr)

    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    ckey = f"{info['version']}|{args.lang}|{info['model_sha256'][:16]}|dpi{DPI}"
    shas: dict[str, str] = {}
    jobs = []
    for p, want in images.items():
        f = pkg / p
        if not f.exists():
            print(f"WARNING missing image {p}", file=sys.stderr)
            continue
        h = sha256_file(f)
        if want and want.lower() != h:
            print(f"WARNING sha256 mismatch for {p} (exam.json {want[:12]}, file {h[:12]})", file=sys.stderr)
        shas[p] = h
        entry = cache.setdefault(h, {"file": p, "engine": ckey, "passes": {}})
        if entry.get("engine") != ckey:
            entry.update({"engine": ckey, "passes": {}})
        for key, psm, scale, rot in passes:
            if key not in entry["passes"]:
                jobs.append((h, f, key, psm, scale, rot))

    t0 = time.time()
    if jobs:
        print(f"{len(images)} images, {len(jobs)} OCR passes to run ({args.jobs} parallel) ...", flush=True)

        def work(j):
            h, f, key, psm, scale, rot = j
            s = time.time()
            words = run_pass(args.tesseract, args.lang, args.tessdata, f, psm, scale, rot)
            return h, key, words, time.time() - s, f.name

        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
            for n, (h, key, words, dt, name) in enumerate(ex.map(work, jobs), 1):
                cache[h]["passes"][key] = words
                print(f"  [{n}/{len(jobs)}] {name} {key}: {len(words)} words, {dt:.1f}s", flush=True)
                if n % 4 == 0 or n == len(jobs):
                    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    else:
        print(f"{len(images)} images, all OCR passes cached ({cache_path})")

    result, covered = {}, []
    for p, h in shas.items():
        text = describe(cache[h]["passes"], args.max_chars)
        if text and transcribed(text, sources.get(p, ""), args.overlap):
            text = ""  # source_text already carries a transcription of this image; OCR would add only noise
            covered.append(p)
        result[p] = text
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    meta = dict(info, passes=[p[0] for p in passes], max_chars=args.max_chars, images=len(result),
                empty=[p for p, t in result.items() if not t], covered_by_transcription=covered, ocr_seconds=round(time.time() - t0, 1),
                cache=str(cache_path))
    out.with_name(out.stem + ".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n",
                                                        encoding="utf-8")
    print(f"wrote {out} ({len(result)} images, {sum(1 for t in result.values() if t)} with text, "
          f"{time.time() - t0:.0f}s); engine {info['version']} model {info['model_file']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
