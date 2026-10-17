"""Panel webowy zespolu Vibers (Warsaw Model Trainers, matura z historii).

Wylacznie do odczytu, poza proxy w zakladce "Sprawdz pytanie".
Serwowane z Maca pod adresem Tailscale, patrz panel/README.md.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import html
import io
import json
import os
import random
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlencode

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

# --------------------------------------------------------------------------
# Konfiguracja / stale sciezki
# --------------------------------------------------------------------------

# WMT_PANEL_BASE_DIR pozwala uruchomic panel na lokalnej kopii danych (testy); domyslnie ~/wmt-matura
BASE_DIR = Path(os.environ.get("WMT_PANEL_BASE_DIR") or Path(__file__).resolve().parents[1]).resolve()
LOGS_DIR = BASE_DIR / "logs"
MODELS_DIR = BASE_DIR / "models"
KB_DIR = BASE_DIR / "kb"
KB_DATA_DIR = BASE_DIR / "kb_data"
DEVSET_DIR = BASE_DIR / "devset"
RUNS_DIR = DEVSET_DIR / "runs"
EXPERIMENTS_CSV = DEVSET_DIR / "experiments.csv"
SHA256_CACHE_PATH = LOGS_DIR / "sha256_cache.json"

# katalogi, w ktorych wolno szukac plikow wynikow per-pytanie (jsonl)
RESULT_DIRS = [BASE_DIR / "results", DEVSET_DIR / "results", RUNS_DIR]

LLAMA_BASE = "http://127.0.0.1:18080"
PROXY_TIMEOUT = 120.0
MODEL_SIZE_LIMIT_GB = 8.0  # dziesietne GB (bajty / 1e9)
# tak samo jak benchmark bazowy (harness/batch.py call_base): temperatura 0, max 512 tokenow
BASE_ASK_PARAMS = {"temperature": 0, "max_tokens": 512}

# porty, na ktorych moga dzialac lokalne instancje harnessu (probe /health)
HARNESS_PROBE_PORTS = list(range(18000, 18011))
HARNESS_PROBE_TIMEOUT = 0.7
DEFAULT_HARNESS_PORT = 18000

LEADERBOARD_URL = "https://warsawmodeltrainers.dev/matura#board"
EXAM_URL = "https://warsawmodeltrainers.dev/matura#exam"
RULES_URL = "https://warsawmodeltrainers.dev/rules"

CURRENT_USER = os.environ.get("USER") or os.environ.get("LOGNAME") or ""

# Pelny benchmark druzyny = te 9 plikow razem (673 pytania); tourney160 = sweep wszystkich modeli.
FULL_BENCH_FILES = (
    "dev-a.jsonl", "dev-b.jsonl", "dev-c.jsonl", "dev-f.jsonl", "dev-g.jsonl", "dev-h.jsonl",
    "tourney160.jsonl", "cke-2023.jsonl", "cke-more.jsonl",
)
SCOPE_FULL = "full"
SWEEP_FILE = "tourney160.jsonl"
SMALL_THRESHOLD_PCT = 35.0

METRICS = {"strict": "ścisła", "lenient": "łagodna"}
DEFAULT_METRIC = "strict"
QTYPES = ("abcd", "pf", "chrono", "match", "open")
QTYPE_NAMES = {
    "abcd": "zamknięte ABCD", "pf": "prawda/fałsz", "chrono": "chronologia",
    "match": "dopasowanie", "open": "otwarte",
}

# Etykiety w experiments.csv: [<seria>-]<model>-<wariant>, np. final-bielik-4.5b-v3-harness-v2-lora,
# l40s-qwen3-8b-base-raw, mac-qwen35-0.8b-harness-kb. Pozostale (hv2-*, kb-*, devac-*) to eksperymenty.
SERIES_PREFIXES = (("final-", "final"), ("l40s-", "l40s"), ("mac-", "mac"), ("integ-devall-", "integ"), ("t-", "t"))
LABEL_RE = re.compile(r"^(?P<model>.+?)-(?P<variant>(?:base|harness)(?:-.+)?)$")
MODEL_ALIASES = {"bielik": "bielik-11b-v3", "bielik11": "bielik-11b-v3", "bielik45": "bielik-4.5b-v3"}
VARIANT_NAMES = {
    "base-raw": "goły model",
    "base-raw-nothink": "goły model, bez thinking",
    "base-sys": "model + prompt systemowy",
    "base-sys-v2": "model + prompt systemowy v2",
    "harness-nokb": "harness v1 bez bazy wiedzy",
    "harness-kb": "harness v1 + baza wiedzy",
    "harness-v2": "harness v2 (BM25 + reranker)",
    "harness-v2-lora": "harness v2 + LoRA",
}
VARIANT_ORDER = list(VARIANT_NAMES)

# ============================================================================
# PEŁNA MATURA — stałe (sekcja dodana przez agenta; kod patrz niżej w pliku)
# ============================================================================
MATURA_PAPERS = ["mentor2023", "cke2024", "cke2025", "cke2026"]
MATURA_PAPER_NAMES = {
    "mentor2023": "Mentor 2023 (benchmark tekstowy)",
    "cke2024": "CKE 2024",
    "cke2025": "CKE 2025",
    "cke2026": "CKE 2026",
}
MATURA_SYSTEMS = ["raw", "harness_nolora", "harness_lora"]
MATURA_SYSTEM_NAMES = {
    "raw": "goły Bielik",
    "harness_nolora": "nasz system (bez LoRA)",
    "harness_lora": "nasz system (z LoRA)",
}
MATURA_CATS = ["closed", "open", "essay"]
MATURA_CAT_NAMES = {"closed": "zamknięte", "open": "otwarte", "essay": "wypracowanie"}
MATURA_CLOSED_HINTS = {"abcd", "abcd_parts", "pf", "match", "chrono"}
MATURA_ESSAY_HINTS = {"essay"}

app = FastAPI(title="WMT Panel", docs_url=None, redoc_url=None, openapi_url=None)


def esc(value: Any) -> str:
    """Bezpieczne escapowanie do HTML (nigdy nie ufamy tresci plikow/danych)."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def run_cmd(args: list[str], timeout: float = 5.0) -> str:
    """Uruchamia stale polecenie systemowe (bez udzialu danych od uzytkownika)."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout or ""
    except Exception:
        return ""


def parse_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_int(v: Any) -> Optional[int]:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def json_dict(v: Any) -> dict:
    try:
        d = json.loads(v or "{}")
    except (TypeError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def fmt_pct(frac: Optional[float]) -> str:
    if frac is None:
        return "–"
    return "{:.1f}%".format(frac * 100).replace(".", ",")


def fmt_pts(pp: Optional[float]) -> str:
    """Roznica w punktach procentowych (wartosc juz w pkt)."""
    if pp is None:
        return "–"
    return "{:+.1f} pkt".format(pp).replace(".", ",")


def fmt_gb(gb: Optional[float]) -> str:
    return "–" if gb is None else "{:.2f} GB".format(gb).replace(".", ",")


def sv(v: Optional[float]) -> str:
    """Wartosc do data-sort-value (brak danych laduje na dole przy sortowaniu malejacym)."""
    return "-999" if v is None else "{:.6f}".format(v)


def short_ts(ts: str) -> str:
    m = re.match(r"^\d{4}-(\d{2})-(\d{2})T(\d{2}:\d{2})", ts or "")
    return "{}.{} {}".format(m.group(2), m.group(1), m.group(3)) if m else (ts or "")


def url(path: str, **params: Any) -> str:
    q = {k: v for k, v in params.items() if v not in (None, "")}
    return path + ("?" + urlencode(q) if q else "")


def norm_metric(m: Optional[str]) -> str:
    return m if m in METRICS else DEFAULT_METRIC


def mark(ok: Optional[bool]) -> str:
    if ok is None:
        return "<span class=\"muted\">?</span>"
    return "<span class=\"ok\" title=\"poprawnie\">&#10003;</span>" if ok else "<span class=\"fail\" title=\"błędnie\">&#10007;</span>"


# --------------------------------------------------------------------------
# System (procesy, pamiec, dysk)
# --------------------------------------------------------------------------

CATEGORY_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    ("llama-server", re.compile(r"llama-server", re.I)),
    ("harness (serwer odpowiedzi)", re.compile(r"(^|[\s/])python[\w.]*\s+-m\s+harness\b|harness[/\\](server|app|main)", re.I)),
    ("uvicorn", re.compile(r"\buvicorn\b", re.I)),
    ("budowa bazy wiedzy (KB)", re.compile(r"kb\.build|kb_build|build_index|build_chunks|eval_recall", re.I)),
    ("pobieranie modelu (hf)", re.compile(r"\bhf\s+download\b|huggingface[-_]cli|huggingface_hub", re.I)),
    ("pobieranie (curl)", re.compile(r"(^|/)curl\s", re.I)),
]


def classify_process(cmd: str) -> Optional[str]:
    for label, pattern in CATEGORY_PATTERNS:
        if pattern.search(cmd):
            return label
    return None


def get_processes() -> list[dict]:
    """Tylko procesy WLASNEGO uzytkownika (maszyna jest dzielona z innymi)."""
    out = run_cmd(["ps", "-axo", "user,pid,pcpu,pmem,etime,command"])
    rows: list[dict] = []
    lines = out.splitlines()
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        user, pid, pcpu, pmem, etime, cmd = parts
        if CURRENT_USER and user != CURRENT_USER:
            continue
        if "ps -axo" in cmd:
            continue
        label = classify_process(cmd)
        if not label:
            continue
        extra = ""
        if label == "llama-server":
            m = re.search(r"-m\s+(\S+)", cmd)
            p = re.search(r"--port\s+(\d+)", cmd)
            extra = "model={} port={}".format(m.group(1) if m else "?", p.group(1) if p else "?")
        else:
            p = re.search(r"--port[= ](\d+)|:(\d{4,5})\b", cmd)
            if p:
                extra = "port={}".format(p.group(1) or p.group(2))
        rows.append({"pid": pid, "cpu": pcpu, "mem": pmem, "etime": etime, "label": label, "cmd": cmd, "extra": extra})
    rows.sort(key=lambda r: (r["label"], r["pid"]))
    return rows


def get_memory_info() -> dict:
    out = run_cmd(["memory_pressure"], timeout=5.0)
    info: dict[str, Any] = {"free_pct": None, "total_gb": None, "raw_ok": bool(out)}
    m = re.search(r"System-wide memory free percentage:\s*(\d+)%", out)
    if m:
        info["free_pct"] = int(m.group(1))
    m2 = re.search(r"The system has (\d+) \((\d+) pages", out)
    if m2:
        total_bytes = int(m2.group(1))
        info["total_gb"] = round(total_bytes / (1024 ** 3), 1)
    for key, pattern in (
        ("pages_free", r"Pages free:\s*(\d+)"),
        ("pages_active", r"Pages active:\s*(\d+)"),
        ("pages_inactive", r"Pages inactive:\s*(\d+)"),
        ("pages_wired", r"Pages wired down:\s*(\d+)"),
    ):
        mm = re.search(pattern, out)
        if mm:
            info[key] = int(mm.group(1))
    return info


def get_disk_info() -> dict:
    try:
        import shutil

        usage = shutil.disk_usage(str(Path.home()))
        return {
            "total_gb": round(usage.total / 1e9, 1),
            "used_gb": round(usage.used / 1e9, 1),
            "free_gb": round(usage.free / 1e9, 1),
            "pct_used": round(100.0 * usage.used / usage.total, 1) if usage.total else None,
        }
    except Exception:
        return {"total_gb": None, "used_gb": None, "free_gb": None, "pct_used": None}


def get_load_avg() -> Optional[tuple[float, float, float]]:
    try:
        return os.getloadavg()
    except (OSError, AttributeError):
        return None


def render_system_html() -> str:
    procs = get_processes()
    mem = get_memory_info()
    disk = get_disk_info()
    load = get_load_avg()

    rows_html = []
    if procs:
        for p in procs:
            rows_html.append(
                "<tr><td>{lbl}</td><td class=\"num\">{pid}</td><td class=\"num\">{cpu}%</td>"
                "<td class=\"num\">{mem}%</td><td>{etime}</td><td>{extra}</td>"
                "<td class=\"cmdcell\"><code>{cmd}</code></td></tr>".format(
                    lbl=esc(p["label"]), pid=esc(p["pid"]), cpu=esc(p["cpu"]), mem=esc(p["mem"]),
                    etime=esc(p["etime"]), extra=esc(p["extra"]), cmd=esc(p["cmd"]),
                )
            )
        proc_table = (
            "<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr>"
            "<th>Kategoria</th><th>PID</th><th>CPU</th><th>MEM</th><th>Czas</th><th>Info</th><th>Polecenie</th>"
            "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
        )
    else:
        proc_table = "<p class=\"muted\">Brak pasujących procesów (llama-server / harness / uvicorn / budowa KB / pobierania).</p>"

    mem_bits = []
    if mem.get("free_pct") is not None:
        mem_bits.append("wolna pamięć: <b>{}%</b>".format(mem["free_pct"]))
    if mem.get("total_gb") is not None:
        mem_bits.append("RAM całkowity: <b>{} GiB</b>".format(mem["total_gb"]))
    if mem.get("pages_wired") is not None:
        mem_bits.append("strony wired: {}".format(mem["pages_wired"]))
    mem_line = " &middot; ".join(mem_bits) if mem_bits else "brak danych z memory_pressure"

    disk_line = "brak danych"
    if disk.get("free_gb") is not None:
        disk_line = "wolne: <b>{} GB</b> / {} GB ({}% zajęte)".format(disk["free_gb"], disk["total_gb"], disk["pct_used"])

    load_line = "brak danych"
    if load:
        load_line = "1 min: <b>{:.2f}</b> &middot; 5 min: {:.2f} &middot; 15 min: {:.2f}".format(*load)

    return (
        "<div class=\"kpis\">"
        "<div class=\"kpi\"><div class=\"kpi-label\">Pamięć</div><div class=\"kpi-value\">{mem}</div></div>"
        "<div class=\"kpi\"><div class=\"kpi-label\">Dysk (~)</div><div class=\"kpi-value\">{disk}</div></div>"
        "<div class=\"kpi\"><div class=\"kpi-label\">Load average</div><div class=\"kpi-value\">{load}</div></div>"
        "</div>{procs}"
    ).format(mem=mem_line, disk=disk_line, load=load_line, procs=proc_table)


# --------------------------------------------------------------------------
# Modele (*.gguf + sha256 w tle)
# --------------------------------------------------------------------------

_sha_lock = threading.Lock()
_sha_pending: set[str] = set()


def _load_sha_cache() -> dict:
    try:
        return json.loads(SHA256_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_sha_cache(cache: dict) -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SHA256_CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(SHA256_CACHE_PATH)
    except Exception:
        pass


def _compute_sha256_bg(path_str: str, size: int, mtime: float) -> None:
    try:
        h = hashlib.sha256()
        with open(path_str, "rb") as f:
            for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
                h.update(chunk)
        digest = h.hexdigest()
        with _sha_lock:
            cache = _load_sha_cache()
            cache[path_str] = {"size": size, "mtime": mtime, "sha256": digest}
            _save_sha_cache(cache)
    except Exception:
        pass
    finally:
        with _sha_lock:
            _sha_pending.discard(path_str)


def get_models() -> list[dict]:
    models: list[dict] = []
    cache = _load_sha_cache()
    if not MODELS_DIR.exists():
        return models
    for path in sorted(MODELS_DIR.rglob("*.gguf")):
        try:
            st = path.stat()
        except OSError:
            continue
        size_gb = st.st_size / 1_000_000_000
        key = str(path)
        entry = cache.get(key)
        sha = None
        status = "obliczanie..."
        if entry and entry.get("size") == st.st_size and entry.get("mtime") == st.st_mtime:
            sha = entry.get("sha256")
            status = "ok"
        else:
            with _sha_lock:
                if key not in _sha_pending:
                    _sha_pending.add(key)
                    threading.Thread(
                        target=_compute_sha256_bg, args=(key, st.st_size, st.st_mtime), daemon=True
                    ).start()
        models.append(
            {
                "name": path.relative_to(MODELS_DIR).as_posix(),
                "size_gb": size_gb,
                "ok_size": size_gb <= MODEL_SIZE_LIMIT_GB,
                "sha256": sha,
                "status": status,
            }
        )
    return models


def render_models_html() -> str:
    models = get_models()
    if not models:
        return "<p class=\"muted\">Brak plików *.gguf w models/.</p>"
    rows = []
    for m in models:
        badge_cls = "badge-ok" if m["ok_size"] else "badge-bad"
        badge_txt = "OK &le; {:.1f} GB".format(MODEL_SIZE_LIMIT_GB) if m["ok_size"] else "ZA DUŻY"
        sha_html = "<code>{}</code>".format(esc(m["sha256"])) if m["sha256"] else "<span class=\"muted\">{}</span>".format(esc(m["status"]))
        rows.append(
            "<tr><td>{name}</td><td class=\"num\" data-sort-value=\"{sizeraw}\">{size:.2f} GB</td>"
            "<td><span class=\"badge {cls}\">{badge}</span></td><td class=\"cmdcell\">{sha}</td></tr>".format(
                name=esc(m["name"]), sizeraw=m["size_gb"], size=m["size_gb"], cls=badge_cls, badge=badge_txt, sha=sha_html
            )
        )
    return (
        "<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr>"
        "<th>Plik</th><th>Rozmiar</th><th>Limit 8.0 GB</th><th>sha256</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        "<p class=\"muted small\">sha256 liczony leniwie w tle i cachowany w logs/sha256_cache.json - nigdy nie blokuje odpowiedzi.</p>"
    )


_gguf_cache: dict[str, Any] = {"ts": 0.0, "data": {}}


def gguf_by_dir() -> dict[str, list[tuple[str, int]]]:
    """models/<katalog> -> [(sciezka wzgledna, rozmiar w bajtach)], cache 30 s."""
    now = time.time()
    if now - _gguf_cache["ts"] > 30:
        data: dict[str, list[tuple[str, int]]] = {}
        if MODELS_DIR.exists():
            for p in MODELS_DIR.rglob("*.gguf"):
                try:
                    size = p.stat().st_size
                except OSError:
                    continue
                rel = p.relative_to(MODELS_DIR)
                top = rel.parts[0] if len(rel.parts) > 1 else ""
                data.setdefault(top, []).append((rel.as_posix(), size))
        _gguf_cache["data"] = data
        _gguf_cache["ts"] = now
    return _gguf_cache["data"]


def canonical_model(name: Optional[str]) -> Optional[str]:
    """Nazwa z etykiety/configu -> nazwa katalogu w models/ (np. bielik-1.5b -> bielik-1.5b-v3)."""
    if not name:
        return None
    key = name.strip().lower()
    key = MODEL_ALIASES.get(key, key)
    dirs = gguf_by_dir()
    if key in dirs:
        return key
    cands = [d for d in dirs if d.startswith(key + "-")]
    return cands[0] if len(cands) == 1 else None


def model_gguf(model: str) -> Optional[dict]:
    files = gguf_by_dir().get(model) or []
    if not files:
        return None
    main = max(files, key=lambda f: f[1])  # najwiekszy plik to LLM (pomija np. glowice mtp-*)
    return {"file": main[0], "size_gb": main[1] / 1e9, "others": [f for f in files if f != main]}


# --------------------------------------------------------------------------
# Baza wiedzy (KB)
# --------------------------------------------------------------------------

def dir_size(path: Path) -> int:
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except OSError:
        pass
    return total


_kb_size_cache: dict[str, Any] = {"ts": 0.0, "data": {}}


def get_kb_sizes() -> dict[str, int]:
    now = time.time()
    if now - _kb_size_cache["ts"] > 5:
        data: dict[str, int] = {}
        if KB_DATA_DIR.exists():
            for child in sorted(KB_DATA_DIR.iterdir()):
                try:
                    data[child.name] = dir_size(child) if child.is_dir() else child.stat().st_size
                except OSError:
                    pass
        _kb_size_cache["data"] = data
        _kb_size_cache["ts"] = now
    return _kb_size_cache["data"]


def find_recall_files() -> list[Path]:
    out: list[Path] = []
    for d in (KB_DIR, KB_DATA_DIR):
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and "recall" in p.name.lower() and p.suffix.lower() in (".json", ".csv", ".md"):
                out.append(p)
    return sorted(out)


def render_recall_html(p: Path) -> str:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "<p class=\"muted\">Nie można odczytać {}.</p>".format(esc(p.name))
    if p.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
            text = pretty
        except Exception:
            pass
    elif p.suffix.lower() == ".csv":
        try:
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if rows:
                head, *body = rows
                thead = "".join("<th>{}</th>".format(esc(c)) for c in head)
                tbody = "".join(
                    "<tr>" + "".join("<td>{}</td>".format(esc(c)) for c in r) + "</tr>" for r in body
                )
                return (
                    "<div class=\"tablewrap\"><table><thead><tr>{}</tr></thead>"
                    "<tbody>{}</tbody></table></div>"
                ).format(thead, tbody)
        except Exception:
            pass
    return "<pre class=\"logbox\">{}</pre>".format(esc(text[:20000]))


def render_kb_html() -> str:
    sizes = get_kb_sizes()
    parts = []
    if sizes:
        rows = "".join(
            "<tr><td>{}</td><td class=\"num\" data-sort-value=\"{}\">{:.2f} MB</td></tr>".format(
                esc(k), v, v / 1_000_000
            )
            for k, v in sizes.items()
        )
        parts.append(
            "<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr><th>Katalog</th><th>Rozmiar</th>"
            "</tr></thead><tbody>{}</tbody></table></div>".format(rows)
        )
    else:
        parts.append("<p class=\"muted\">Brak danych w kb_data/ (jeszcze nie zbudowane?).</p>")

    kb_logs = sorted(LOGS_DIR.glob("*.log")) if LOGS_DIR.exists() else []
    kb_build_logs = [p for p in kb_logs if "kb" in p.name.lower()]
    if kb_build_logs:
        newest = max(kb_build_logs, key=lambda p: p.stat().st_mtime)
        try:
            lines = newest.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        except OSError:
            lines = []
        parts.append(
            "<p class=\"muted small\">Ostatni log budowy KB: <code>{}</code></p><pre class=\"logbox\">{}</pre>".format(
                esc(newest.name), esc("\n".join(lines))
            )
        )
    else:
        parts.append("<p class=\"muted\">Brak logów budowy KB w logs/.</p>")

    recall_files = find_recall_files()
    if recall_files:
        for rf in recall_files:
            rel = rf.relative_to(BASE_DIR).as_posix()
            parts.append("<h3 class=\"subhead\">Wyniki recall: {}</h3>".format(esc(rel)))
            parts.append(render_recall_html(rf))
    else:
        parts.append(
            "<p class=\"muted\">Brak wyników recall (nie znaleziono *recall*.json|csv|md w kb/ ani kb_data/).</p>"
        )
    return "".join(parts)


# --------------------------------------------------------------------------
# Zestaw testowy (devset)
# --------------------------------------------------------------------------

_devset_cache: dict[str, tuple[tuple[float, int], list[dict]]] = {}


def load_devset_file(path: Path) -> list[dict]:
    try:
        st = path.stat()
    except OSError:
        return []
    key = (st.st_mtime, st.st_size)
    hit = _devset_cache.get(str(path))
    if hit and hit[0] == key:
        return hit[1]
    items = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    _devset_cache[str(path)] = (key, items)
    return items


def devset_names() -> list[str]:
    return sorted(p.name for p in DEVSET_DIR.glob("*.jsonl")) if DEVSET_DIR.exists() else []


def devset_type_counts(name: str) -> Optional[dict[str, int]]:
    if name not in devset_names():
        return None
    counts: dict[str, int] = {}
    for it in load_devset_file(DEVSET_DIR / name):
        t = str(it.get("type", "?"))
        counts[t] = counts.get(t, 0) + 1
    return counts


def full_bench_n() -> int:
    names = set(devset_names())
    return sum(len(load_devset_file(DEVSET_DIR / f)) for f in FULL_BENCH_FILES if f in names)


def render_devset_html() -> str:
    if not DEVSET_DIR.exists():
        return "<p class=\"muted\">Brak katalogu devset/.</p>"
    files = sorted(DEVSET_DIR.glob("*.jsonl"))
    if not files:
        return "<p class=\"muted\">Brak plików devset/*.jsonl.</p>"
    parts = []
    summary_rows = []
    for fp in files:
        items = load_devset_file(fp)
        era_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        for it in items:
            era = str(it.get("era", "?"))
            typ = str(it.get("type", "?"))
            era_counts[era] = era_counts.get(era, 0) + 1
            type_counts[typ] = type_counts.get(typ, 0) + 1
        era_str = ", ".join("{}: {}".format(esc(k), v) for k, v in sorted(era_counts.items()))
        type_str = ", ".join("{}: {}".format(esc(k), v) for k, v in sorted(type_counts.items()))
        in_full = fp.name in FULL_BENCH_FILES
        summary_rows.append(
            "<tr><td>{name}</td><td class=\"num\">{n}</td>{types}<td class=\"num\">{other}</td><td>{full}</td></tr>".format(
                name=esc(fp.name), n=len(items),
                types="".join("<td class=\"num\">{}</td>".format(type_counts.get(t, 0) or "") for t in QTYPES),
                other=sum(v for k, v in type_counts.items() if k not in QTYPES) or "",
                full="<span class=\"badge badge-ok\">tak</span>" if in_full else "",
            )
        )

        rows = []
        for it in items:
            rows.append(
                "<tr><td>{id}</td><td>{era}</td><td>{typ}</td>"
                "<td class=\"qcell\">{q}</td><td>{gold}</td></tr>".format(
                    id=esc(it.get("id", "")),
                    era=esc(it.get("era", "")),
                    typ=esc(it.get("type", "")),
                    q=esc(it.get("question", "")).replace("\n", "<br>"),
                    gold=esc(it.get("answer", "")),
                )
            )
        table = (
            "<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr>"
            "<th>ID</th><th>Era</th><th>Typ</th><th>Pytanie</th><th>Odpowiedź wzorcowa</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        )
        parts.append(
            "<details class=\"devset-file\"><summary><b>{name}</b> &middot; {n} pytań "
            "&middot; era: {era} &middot; typ: {typ}</summary>{table}</details>".format(
                name=esc(fp.name), n=len(items), era=era_str or "-", typ=type_str or "-", table=table
            )
        )
    summary = (
        "<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr><th>Plik</th><th>Pytań</th>"
        + "".join("<th>{}</th>".format(esc(t)) for t in QTYPES)
        + "<th>inne</th><th>W pełnym benchmarku</th></tr></thead><tbody>" + "".join(summary_rows) + "</tbody></table></div>"
        "<p class=\"muted small\">Pełny benchmark = {} ({} pytań). Kliknij plik niżej, żeby zobaczyć pytania.</p>".format(
            esc(", ".join(f.replace(".jsonl", "") for f in FULL_BENCH_FILES)), full_bench_n()
        )
    )
    return summary + "".join(parts)


# ============================================================================
# PEŁNA MATURA (sekcja dodana przez agenta) — pełne arkusze CKE, odpowiedzi
# trzech wariantów systemu (raw / harness bez LoRA / harness z LoRA) i ocena
# egzaminatora wg oficjalnej punktacji CKE.
#
# Dane wyłącznie z devset/cke_full/ (papiery, odpowiedzi, grades.jsonl) —
# nigdy nie commitowane, patrz CLAUDE.md. Ta sekcja tylko czyta pliki *.jsonl,
# tym samym wzorcem cache'owania po (mtime, size) co load_devset_file() wyżej.
# paper/system przechodzą zawsze przez whitelistę (MATURA_PAPERS/MATURA_SYSTEMS)
# zanim trafią do nazwy pliku — brak path traversal. grades.jsonl może nie
# istnieć albo być niepełne (ocena w toku) — każda funkcja niżej działa i bez
# niego, pokazując same odpowiedzi.
# ============================================================================

CKE_FULL_DIR = DEVSET_DIR / "cke_full"


def matura_classify(type_hint: Optional[str]) -> str:
    """Klasyfikuje zadanie do 'closed' (zamkniete) / 'open' (otwarte) / 'essay' (wypracowanie)."""
    t = (type_hint or "").lower()
    if t in MATURA_ESSAY_HINTS:
        return "essay"
    if t in MATURA_CLOSED_HINTS:
        return "closed"
    return "open"


def matura_task_sort_key(task_id: Any) -> tuple:
    """Porzadek numeryczny zadan: 1, 2.1, 2.2, ..., 26 (wypracowanie jest ostatnim numerem z definicji arkusza)."""
    m = re.match(r"^(\d+)(?:\.(\d+))?", str(task_id))
    if not m:
        return (9999, 0, str(task_id))
    return (int(m.group(1)), int(m.group(2) or 0), "")


def load_cke_paper(paper: str) -> list[dict]:
    if paper not in MATURA_PAPERS:
        return []
    items = load_devset_file(CKE_FULL_DIR / "{}.jsonl".format(paper))
    return sorted(items, key=lambda it: matura_task_sort_key(it.get("id")))


def load_matura_answers(system: str, paper: str) -> dict[str, dict]:
    if system not in MATURA_SYSTEMS or paper not in MATURA_PAPERS:
        return {}
    rows = load_devset_file(CKE_FULL_DIR / "answers_{}_{}.jsonl".format(system, paper))
    return {str(r.get("id")): r for r in rows}


def load_matura_grades() -> dict[tuple[str, str, str], dict]:
    """(system, paper, id) -> wiersz z grades.jsonl; pusty dict, jesli plik jeszcze nie istnieje (ocena w toku)."""
    rows = load_devset_file(CKE_FULL_DIR / "grades.jsonl")
    out: dict[tuple[str, str, str], dict] = {}
    for r in rows:
        key = (r.get("system"), r.get("paper"), str(r.get("id")))
        out[key] = r
    return out


def matura_badge_info(points: Optional[float], max_: Optional[float]) -> tuple[str, str]:
    if points is None or not max_:
        return "pt-pending", "ocena w toku"

    def _n(x: float) -> str:
        return str(int(x)) if float(x).is_integer() else str(x)

    label = "{}/{}".format(_n(points), _n(max_))
    if points <= 0:
        return "pt-zero", label
    if points >= max_:
        return "pt-full", label
    return "pt-part", label


def matura_badge_html(points: Optional[float], max_: Optional[float], dom_id: str = "") -> str:
    cls, label = matura_badge_info(points, max_)
    idattr = " id=\"{}\"".format(esc(dom_id)) if dom_id else ""
    return "<span class=\"badge {}\"{}>{}</span>".format(cls, idattr, esc(label))


# "... 2 bledy -1 => A3; B1 (...)" -> A = narracja historyczna (0-12), B = kompozycja/kryteria formalne (0-3);
# sprawdzone na wszystkich 12 ocenionych wypracowaniach w grades.jsonl (A+B == points za kazdym razem).
MATURA_ESSAY_A_RE = re.compile(r"\bA(\d{1,2})\b")
MATURA_ESSAY_B_RE = re.compile(r"\bB(\d{1,2})\b")
MATURA_ESSAY_ERR_RE = re.compile(r"\(([^)]+)\)\s*-\d+")


def parse_essay_scores(reason: str) -> tuple[Optional[int], Optional[int]]:
    if not reason:
        return None, None
    ma = MATURA_ESSAY_A_RE.search(reason)
    mb = MATURA_ESSAY_B_RE.search(reason)
    return (int(ma.group(1)) if ma else None, int(mb.group(1)) if mb else None)


def parse_essay_errors(reason: str) -> list[str]:
    """Najlepszy wysilek: wyciaga liste bledow z nawiasu bezposrednio przed '-N' w uzasadnieniu (np.
    '(Chocim 1621/1633 jako kleski, utrata Kresow) -2'). Gdy nie pasuje, pelny 'reason' i tak jest pokazany osobno."""
    if not reason:
        return []
    m = MATURA_ESSAY_ERR_RE.search(reason)
    if not m:
        return []
    return [x.strip() for x in m.group(1).split(",") if x.strip()]


def matura_essay_words(answer_row: Optional[dict]) -> int:
    if not answer_row:
        return 0
    meta = answer_row.get("essay_meta")
    if isinstance(meta, dict) and meta.get("words"):
        w = parse_int(meta.get("words"))
        if w is not None:
            return w
    text = answer_row.get("answer") or ""
    return len(text.split())


def render_matura_task_row(item: dict, paper: str, sys_key: str, answers: dict[str, dict],
                            grades: dict[tuple[str, str, str], dict]) -> str:
    tid = str(item.get("id"))
    cat = matura_classify(item.get("type_hint"))
    g = grades.get((sys_key, paper, tid))
    pts = g.get("points") if g else None
    mx = (g.get("max") if g else None) or item.get("points")
    badge = matura_badge_html(pts, mx, dom_id="mg-{}-{}".format(sys_key, tid))
    ans = answers.get(tid)
    answer_html = qcell(ans.get("answer", "")) if ans else "<span class=\"muted\">brak odpowiedzi</span>"
    reason = (g.get("reason") if g else "") or ""
    reason_html = (
        "<span class=\"muted small\" id=\"mr-{0}-{1}\">ocena w toku</span>".format(esc(sys_key), esc(tid))
        if g is None else "<span id=\"mr-{0}-{1}\">{2}</span>".format(esc(sys_key), esc(tid), esc(reason))
    )
    details = (
        "<details class=\"qd\"><summary class=\"small\">treść i kryteria</summary>"
        "<div class=\"qfull\"><b>Treść zadania:</b><br>{q}<br><br><b>Zasady oceniania (CKE):</b><br>{r}</div></details>"
    ).format(q=esc(item.get("question", "")).replace("\n", "<br>"),
              r=esc(item.get("rubric_text", "")).replace("\n", "<br>"))
    return (
        "<tr data-cat=\"{cat}\"><td>{tid}</td>"
        "<td class=\"cat\">{catname}<br><span class=\"muted small\">({hint})</span></td>"
        "<td class=\"c\">{badge}</td><td class=\"qcell\">{ans}</td><td class=\"qcell\">{reason}</td><td>{det}</td></tr>"
    ).format(cat=esc(cat), tid=esc(tid), catname=esc(MATURA_CAT_NAMES[cat]), hint=esc(item.get("type_hint", "")),
              badge=badge, ans=answer_html, reason=reason_html, det=details)


def render_matura_compare_row(item: dict, paper: str, sys_a: str, sys_b: str, answers_a: dict[str, dict],
                               answers_b: dict[str, dict], grades: dict[tuple[str, str, str], dict]) -> str:
    tid = str(item.get("id"))
    cat = matura_classify(item.get("type_hint"))

    def side(sys_key: str, answers: dict[str, dict]) -> str:
        g = grades.get((sys_key, paper, tid))
        pts = g.get("points") if g else None
        mx = (g.get("max") if g else None) or item.get("points")
        badge = matura_badge_html(pts, mx, dom_id="mg-{}-{}".format(sys_key, tid))
        ans = answers.get(tid)
        answer_html = qcell(ans.get("answer", "")) if ans else "<span class=\"muted\">brak odpowiedzi</span>"
        reason = (g.get("reason") if g else "") or ""
        reason_html = (
            "<span class=\"muted small\" id=\"mr-{0}-{1}\">ocena w toku</span>".format(esc(sys_key), esc(tid))
            if g is None else "<span id=\"mr-{0}-{1}\">{2}</span>".format(esc(sys_key), esc(tid), esc(reason))
        )
        return "<td class=\"c\">{}</td><td class=\"qcell\">{}</td><td class=\"qcell\">{}</td>".format(
            badge, answer_html, reason_html)

    details = (
        "<details class=\"qd\"><summary class=\"small\">treść i kryteria</summary>"
        "<div class=\"qfull\"><b>Treść zadania:</b><br>{q}<br><br><b>Zasady oceniania (CKE):</b><br>{r}</div></details>"
    ).format(q=esc(item.get("question", "")).replace("\n", "<br>"),
              r=esc(item.get("rubric_text", "")).replace("\n", "<br>"))
    return "<tr data-cat=\"{cat}\"><td>{tid}</td><td class=\"cat\">{catname}</td>{a}{b}<td>{det}</td></tr>".format(
        cat=esc(cat), tid=esc(tid), catname=esc(MATURA_CAT_NAMES[cat]),
        a=side(sys_a, answers_a), b=side(sys_b, answers_b), det=details)


def render_matura_essay_block(item: dict, paper: str, sys_key: str, answers: dict[str, dict],
                               grades: dict[tuple[str, str, str], dict]) -> str:
    tid = str(item.get("id"))
    g = grades.get((sys_key, paper, tid))
    pts = g.get("points") if g else None
    mx = (g.get("max") if g else None) or item.get("points")
    reason = (g.get("reason") if g else "") or ""
    arg_pts, coh_pts = parse_essay_scores(reason)
    errors = parse_essay_errors(reason)
    ans = answers.get(tid) or {}
    text = ans.get("answer", "")
    words = matura_essay_words(ans)
    badge = matura_badge_html(pts, mx, dom_id="mg-{}-{}".format(sys_key, tid))
    sub_badges = []
    if arg_pts is not None:
        sub_badges.append("<span class=\"badge\">narracja historyczna: {}/12</span>".format(esc(arg_pts)))
    if coh_pts is not None:
        sub_badges.append("<span class=\"badge\">kompozycja: {}/3</span>".format(esc(coh_pts)))
    err_html = ""
    if errors:
        err_html = "<div class=\"small\"><b>Wykryte błędy merytoryczne:</b><ul class=\"plain\">{}</ul></div>".format(
            "".join("<li>{}</li>".format(esc(e)) for e in errors))
    reason_html = (
        "<span class=\"muted small\" id=\"mr-{0}-{1}\">ocena w toku</span>".format(esc(sys_key), esc(tid))
        if g is None else "<span id=\"mr-{0}-{1}\">{2}</span>".format(esc(sys_key), esc(tid), esc(reason))
    )
    body_html = (
        "<pre class=\"logbox\">{}</pre>".format(esc(text)) if text
        else "<p class=\"muted\">brak odpowiedzi</p>"
    )
    details = (
        "<details class=\"qd\"><summary class=\"small\">treść zadania i kryteria CKE</summary>"
        "<div class=\"qfull\">{q}<br><br><b>Zasady oceniania:</b><br>{r}</div></details>"
    ).format(q=esc(item.get("question", "")).replace("\n", "<br>"),
              r=esc(item.get("rubric_text", "")).replace("\n", "<br>"))
    return (
        "<div class=\"essaybox\"><h3 class=\"subhead\">Wypracowanie (zadanie {tid}) &middot; {sysname}</h3>"
        "{details}<div class=\"segs\">{badge} {sub}<span class=\"muted small\">{words} słów</span></div>"
        "{body}{err}<div class=\"small\"><b>Uzasadnienie egzaminatora:</b> {reason}</div></div>"
    ).format(tid=esc(tid), sysname=esc(MATURA_SYSTEM_NAMES.get(sys_key, sys_key)), details=details, badge=badge,
              sub="".join(b + " " for b in sub_badges), words=words, body=body_html, err=err_html, reason=reason_html)


def render_matura_summary_body() -> str:
    grades = load_matura_grades()
    papers_items = {p: load_cke_paper(p) for p in MATURA_PAPERS}
    cat_of: dict[tuple[str, str], str] = {}
    for p, items in papers_items.items():
        for it in items:
            cat_of[(p, str(it.get("id")))] = matura_classify(it.get("type_hint"))

    header = "<tr><th>System</th>" + "".join(
        "<th>{}</th>".format(esc(MATURA_PAPER_NAMES[p])) for p in MATURA_PAPERS
    ) + "<th>Razem</th><th>Przyrost vs goły Bielik</th></tr>"

    raw_overall_pct: Optional[float] = None
    body_rows = []
    for sysk in MATURA_SYSTEMS:  # "raw" jest pierwszy z definicji -> policzony przed liczeniem przyrostu
        tot_pts = tot_max = 0
        cells = []
        for p in MATURA_PAPERS:
            items = papers_items[p]
            per_cat = {c: [0, 0, 0, 0] for c in MATURA_CATS}  # pkt, max, ocenione, wszystkie
            for it in items:
                tid = str(it.get("id"))
                cat = cat_of[(p, tid)]
                g = grades.get((sysk, p, tid))
                per_cat[cat][3] += 1
                mx = it.get("points") or 0
                if g is not None:
                    per_cat[cat][0] += g.get("points") or 0
                    per_cat[cat][1] += g.get("max") or mx
                    per_cat[cat][2] += 1
            lines = []
            p_sum = m_sum = gr_sum = n_sum = 0
            for c in MATURA_CATS:
                pts, mx, gr, n = per_cat[c]
                p_sum += pts
                m_sum += mx
                gr_sum += gr
                n_sum += n
                if n == 0:
                    continue
                pct = fmt_pct(pts / mx) if mx else "–"
                partial = "" if gr == n else " <span class=\"muted\">({}/{} ocenione)</span>".format(gr, n)
                lines.append("<div class=\"small\">{}: {}/{} ({}){}</div>".format(
                    esc(MATURA_CAT_NAMES[c]), pts, mx or "–", pct, partial))
            tot_pts += p_sum
            tot_max += m_sum
            pct_all = fmt_pct(p_sum / m_sum) if m_sum else "–"
            pending = "" if gr_sum == n_sum else (
                "<div class=\"small warn\">ocena w toku ({}/{})</div>".format(gr_sum, n_sum))
            cells.append(
                "<td class=\"cellwrap\"><a href=\"{href}\"><b>razem: {p_sum}/{m_sum} ({pct})</b></a>"
                "{pending}{lines}</td>".format(
                    href=esc(url("/matura/{}".format(p), sys=sysk)), p_sum=p_sum, m_sum=m_sum or "–",
                    pct=pct_all, pending=pending, lines="".join(lines)))
        pct_overall = (tot_pts / tot_max) if tot_max else None
        if sysk == "raw":
            raw_overall_pct = pct_overall
        gain_html = "<span class=\"muted\">–</span>"
        if sysk != "raw" and pct_overall is not None and raw_overall_pct is not None:
            gain_pp = (pct_overall - raw_overall_pct) * 100
            cls = "status-good" if gain_pp >= 0 else "status-crit"
            gain_html = "<span class=\"status {}\">{}</span>".format(cls, fmt_pts(gain_pp))
        razem_html = "<b>{}/{}</b> ({})".format(
            tot_pts, tot_max or "–", fmt_pct(pct_overall) if pct_overall is not None else "–")
        body_rows.append(
            "<tr><td class=\"gold\">{name}</td>{cells}<td>{razem}</td><td>{gain}</td></tr>".format(
                name=esc(MATURA_SYSTEM_NAMES[sysk]), cells="".join(cells), razem=razem_html, gain=gain_html))
    return (
        "<div class=\"tablewrap\"><table><thead>{}</thead><tbody>{}</tbody></table></div>"
        "<p class=\"muted small\">Przyrost liczony na sumie punktów ze wszystkich czterech arkuszy "
        "(tylko zadania już ocenione); dopóki ocena trwa, liczba może się jeszcze zmienić.</p>"
    ).format(header, "".join(body_rows))


def render_matura_summary_page() -> str:
    body = (
        "<p class=\"intro\">Pełne arkusze CKE (matura z historii): odpowiedzi trzech wariantów systemu "
        "i ocena egzaminatora wg oficjalnej punktacji CKE. Treść CKE jest chroniona prawem autorskim — "
        "widoczna tylko tutaj, w prywatnym panelu (patrz CLAUDE.md).</p>"
        "<div id=\"matura-summary-body\">{}</div>"
    ).format(render_matura_summary_body())
    return section("Pełna matura &middot; podsumowanie", body, sid="sec-matura-summary")


def render_matura_paper_page(paper: str, sys_key: str, mode: str, sys_a: str, sys_b: str) -> str:
    items = load_cke_paper(paper)
    grades = load_matura_grades()
    parts = ["<div id=\"matura-paper-marker\" data-paper=\"{}\" hidden></div>".format(esc(paper))]

    seg = []
    for sk in MATURA_SYSTEMS:
        active = " active" if (mode == "single" and sk == sys_key) else ""
        seg.append("<a class=\"seg{}\" href=\"{}\">{}</a>".format(
            active, esc(url("/matura/" + paper, sys=sk)), esc(MATURA_SYSTEM_NAMES[sk])))
    pairs = [("raw", "harness_nolora"), ("raw", "harness_lora"), ("harness_nolora", "harness_lora")]
    compare_links = []
    for pa, pb in pairs:
        active = " active" if (mode == "compare" and {sys_a, sys_b} == {pa, pb}) else ""
        compare_links.append("<a class=\"seg{}\" href=\"{}\">{} vs {}</a>".format(
            active, esc(url("/matura/" + paper, mode="compare", a=pa, b=pb)),
            esc(MATURA_SYSTEM_NAMES[pa]), esc(MATURA_SYSTEM_NAMES[pb])))
    parts.append("<div class=\"segs\"><span class=\"seg-label\">System:</span>{}</div>".format("".join(seg)))
    parts.append("<div class=\"segs\"><span class=\"seg-label\">Porównaj:</span>{}</div>".format(
        "".join(compare_links)))

    non_essay = [it for it in items if matura_classify(it.get("type_hint")) != "essay"]
    essay_items = [it for it in items if matura_classify(it.get("type_hint")) == "essay"]

    if mode == "compare":
        answers_a = load_matura_answers(sys_a, paper)
        answers_b = load_matura_answers(sys_b, paper)
        head = (
            "<tr><th rowspan=\"2\">Zad.</th><th rowspan=\"2\">Typ</th>"
            "<th colspan=\"3\">{}</th><th colspan=\"3\">{}</th><th rowspan=\"2\">Treść i kryteria</th></tr>"
            "<tr><th>Pkt</th><th>Odpowiedź</th><th>Uzasadnienie</th>"
            "<th>Pkt</th><th>Odpowiedź</th><th>Uzasadnienie</th></tr>"
        ).format(esc(MATURA_SYSTEM_NAMES[sys_a]), esc(MATURA_SYSTEM_NAMES[sys_b]))
        rows = "".join(render_matura_compare_row(it, paper, sys_a, sys_b, answers_a, answers_b, grades)
                       for it in non_essay)
        parts.append("<div class=\"tablewrap\"><table><thead>{}</thead><tbody>{}</tbody></table></div>".format(
            head, rows))
        for it in essay_items:
            parts.append(render_matura_essay_block(it, paper, sys_a, answers_a, grades))
            parts.append(render_matura_essay_block(it, paper, sys_b, answers_b, grades))
    else:
        answers = load_matura_answers(sys_key, paper)
        head = "<tr><th>Zad.</th><th>Typ</th><th>Pkt</th><th>Odpowiedź</th><th>Uzasadnienie</th><th>Treść i kryteria</th></tr>"
        rows = "".join(render_matura_task_row(it, paper, sys_key, answers, grades) for it in non_essay)
        parts.append("<div class=\"tablewrap\"><table><thead>{}</thead><tbody>{}</tbody></table></div>".format(
            head, rows))
        for it in essay_items:
            parts.append(render_matura_essay_block(it, paper, sys_key, answers, grades))
    return section(
        "Pełna matura &middot; {}".format(esc(MATURA_PAPER_NAMES.get(paper, paper))),
        "".join(parts), sid="sec-matura-paper")


# ============================================================================
# KONIEC: PEŁNA MATURA (dalszy ciąg funkcji poniżej to reszta panelu)
# ============================================================================


# --------------------------------------------------------------------------
# Wyniki: experiments.csv -> przebiegi -> systemy (etykieta x zakres)
# --------------------------------------------------------------------------

def load_experiments() -> tuple[list[str], list[dict]]:
    if not EXPERIMENTS_CSV.exists():
        return [], []
    try:
        with EXPERIMENTS_CSV.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            cols = reader.fieldnames or []
    except OSError:
        return [], []
    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return cols, rows


def resolve_run_file(rel: str) -> Optional[Path]:
    if not rel:
        return None
    try:
        p = (BASE_DIR / rel).resolve()
    except (OSError, ValueError):
        return None
    for d in RESULT_DIRS:
        try:
            d_resolved = d.resolve()
        except OSError:
            continue
        try:
            p.relative_to(d_resolved)
        except ValueError:
            continue
        if p.is_file() and p.suffix == ".jsonl":
            return p
    return None


def rel_of(p: Path) -> str:
    try:
        return p.relative_to(BASE_DIR).as_posix()
    except ValueError:
        return p.as_posix()


def parse_label(label: str, cfg: dict) -> tuple[str, Optional[str], Optional[str]]:
    """Etykieta -> (seria, model, wariant). Wariant None = eksperyment spoza konwencji."""
    rest, series = label, ""
    for prefix, name in SERIES_PREFIXES:
        if rest.startswith(prefix):
            rest, series = rest[len(prefix):], name
            break
    cfg_model = cfg.get("llm_model") if isinstance(cfg.get("llm_model"), str) else None
    model: Optional[str] = None
    variant: Optional[str] = None
    m = LABEL_RE.match(rest)
    if m:
        raw = m.group("model").lower()
        model = canonical_model(raw)
        if model is None and MODEL_ALIASES.get(raw.split("-")[0]):
            alias = MODEL_ALIASES[raw.split("-")[0]]
            model = canonical_model(alias) or alias
        if model is None and series:
            model = raw  # znana seria: ufamy etykiecie, nawet jesli GGUF-a nie ma na tym Macu
        if model is not None:
            variant = m.group("variant")
    if model is None:
        model = canonical_model(cfg_model) or cfg_model
    return series, model, variant


def normalize_row(r: dict) -> dict:
    label = (r.get("label") or "").strip()
    endpoint = (r.get("endpoint") or "").strip().lower()
    cfg = json_dict(r.get("config"))
    series, model, variant = parse_label(label, cfg)
    files = [f.strip() for f in (r.get("files") or "").split(";") if f.strip()]
    n = parse_int(r.get("n")) or 0
    out: dict[str, Any] = {
        "label": label,
        "kind": "B" if endpoint == "base" else ("T" if endpoint == "answer" else "?"),
        "series": series,
        "model": model,
        "variant": variant,
        "cfg": cfg,
        "files_key": ";".join(files) or "?",
        "n": n,
        "ts": r.get("timestamp") or "",
        "run_file": (r.get("run_file") or "").strip(),
        "p50": parse_float(r.get("p50_s")),
        "errors": parse_int(r.get("errors")) or 0,
        "per_type": json_dict(r.get("per_type")),
        "points_strict": parse_int(r.get("points_strict")),
        "points_max": parse_int(r.get("points_max")),
    }
    for m in ("strict", "extract", "lenient"):
        v = parse_float(r.get("acc_" + m))
        out[m] = v
        out["c_" + m] = None if v is None else round(v * n)
    out["run_path"] = resolve_run_file(out["run_file"])
    return out


def make_system(label: str, scope: str, rows: list[dict]) -> dict:
    """System = etykieta na danym zakresie (jeden plik albo pelny benchmark = suma 9 plikow)."""
    head = rows[0]
    n = sum(r["n"] for r in rows)
    s: dict[str, Any] = {
        "label": label, "scope": scope, "kind": head["kind"], "series": head["series"],
        "model": head["model"], "variant": head["variant"], "rows": rows, "n": n,
        "coverage": len(rows), "complete": scope != SCOPE_FULL or len(rows) == len(FULL_BENCH_FILES),
        "ts": max(r["ts"] for r in rows),
    }
    for m in ("strict", "extract", "lenient"):
        cs = [r["c_" + m] for r in rows]
        s[m] = None if (not n or any(c is None for c in cs)) else sum(cs) / n
    ps = [r["points_strict"] for r in rows]
    pm = [r["points_max"] for r in rows]
    s["points_strict"] = sum(ps) if all(p is not None for p in ps) else None
    s["points_max"] = sum(pm) if all(p is not None for p in pm) else None
    return s


_index_cache: dict[str, Any] = {"key": None, "ts": 0.0, "data": None}


def data_version() -> str:
    parts = []
    for p in (EXPERIMENTS_CSV, RUNS_DIR):
        try:
            st = p.stat()
            parts.append("{:.0f}-{}".format(st.st_mtime, st.st_size))
        except OSError:
            parts.append("x")
    return "_".join(parts)


def get_index() -> dict:
    key = data_version()
    if _index_cache["data"] is not None and _index_cache["key"] == key and time.time() - _index_cache["ts"] < 30:
        return _index_cache["data"]
    _cols, raw_rows = load_experiments()
    rows = [normalize_row(r) for r in raw_rows]  # najnowsze pierwsze
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest.setdefault((r["label"], r["files_key"]), r)
    by_label: dict[str, dict[str, dict]] = {}
    for (label, fk), r in latest.items():
        by_label.setdefault(label, {})[fk] = r
    scopes: dict[str, list[dict]] = {}
    for label, per_file in by_label.items():
        for fk, r in per_file.items():
            scopes.setdefault(fk, []).append(make_system(label, fk, [r]))
        full_rows = [per_file[f] for f in FULL_BENCH_FILES if f in per_file]
        if full_rows:
            scopes.setdefault(SCOPE_FULL, []).append(make_system(label, SCOPE_FULL, full_rows))
    data = {"rows": rows, "scopes": scopes, "by_label": by_label}
    _index_cache.update(key=key, ts=time.time(), data=data)
    return data


def scope_title(scope: str) -> str:
    if scope == SCOPE_FULL:
        return "pełny benchmark ({} pytań)".format(full_bench_n() or "?")
    return scope.replace(".jsonl", "")


def ordered_scopes(idx: dict) -> list[str]:
    def key(sc: str) -> tuple:
        if sc == SCOPE_FULL:
            return (0, "")
        if sc in FULL_BENCH_FILES:
            return (1, FULL_BENCH_FILES.index(sc))
        return (2, sc)
    return sorted(idx["scopes"], key=key)


def variant_name(v: Optional[str], label: str = "") -> str:
    if v is None:
        return "eksperyment"
    return VARIANT_NAMES.get(v, v)


def pick_base(systems: list[dict], t: dict) -> Optional[dict]:
    """B dla systemu T: goly model (base-raw) tego samego modelu na tym samym zakresie, najlepiej z tej samej serii."""
    raw = [s for s in systems if s["kind"] == "B" and s["model"] == t["model"] and s["variant"] == "base-raw" and s["complete"]]
    if not raw:
        return None
    same = [s for s in raw if s["series"] == t["series"]]
    return max(same or raw, key=lambda s: s["ts"])


def best_t(systems: list[dict], m: str) -> Optional[dict]:
    cands = [s for s in systems if s["kind"] == "T" and s["complete"] and s[m] is not None]
    return max(cands, key=lambda s: (s[m], s["ts"])) if cands else None


def model_gains(idx: dict, scope: str, m: str) -> list[dict]:
    systems = idx["scopes"].get(scope, [])
    out = []
    for model in sorted({s["model"] for s in systems if s["model"]}):
        t = best_t([s for s in systems if s["model"] == model], m)
        if t is None:
            continue
        b = pick_base(systems, t)
        gain = None if (b is None or b[m] is None) else (t[m] - b[m]) * 100
        out.append({"model": model, "t": t, "b": b, "gain": gain})
    out.sort(key=lambda g: (g["gain"] is not None, g["gain"] or 0.0, g["t"][m]), reverse=True)
    return out


def best_for_model(idx: dict, model: str, m: str) -> Optional[dict]:
    """Najlepszy benchmark modelu: pelny benchmark, jesli jest; inaczej tourney160; inaczej najwiekszy zakres."""
    for scope in (SCOPE_FULL, SWEEP_FILE):
        t = best_t([s for s in idx["scopes"].get(scope, []) if s["model"] == model], m)
        if t is not None:
            return t
    cands = [
        s for sc, ss in idx["scopes"].items() if sc != SCOPE_FULL
        for s in ss if s["model"] == model and s["kind"] == "T" and s[m] is not None
    ]
    return max(cands, key=lambda s: (s["n"], s[m])) if cands else None


_sweep_params_cache: dict[str, Any] = {"key": None, "data": {}}


def md_tables(text: str) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    cur: list[list[str]] = []
    for line in text.splitlines() + [""]:
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                cur.append(cells)
        elif cur:
            tables.append(cur)
            cur = []
    return tables


def model_params(model: str) -> str:
    files = sorted(DEVSET_DIR.glob("sweep_results*.md")) if DEVSET_DIR.exists() else []
    try:
        key = tuple((f.name, f.stat().st_mtime) for f in files)
    except OSError:
        key = None
    if key != _sweep_params_cache["key"]:
        data: dict[str, str] = {}
        for f in files:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for table in md_tables(text):
                header = [h.lower() for h in table[0]]
                if "model" in header and "params" in header:
                    im, ip = header.index("model"), header.index("params")
                    for row in table[1:]:
                        if len(row) > max(im, ip) and row[ip]:
                            name = canonical_model(row[im]) or row[im].lower()
                            data.setdefault(name, row[ip])
        _sweep_params_cache.update(key=key, data=data)
    if model in _sweep_params_cache["data"]:
        return _sweep_params_cache["data"][model]
    m = re.search(r"(?<![a-z0-9.])(e?\d+(?:\.\d+)?)b(?![a-z])", model)
    return m.group(1).upper() + "B" if m else "?"


def small_models(idx: dict, m: str) -> list[dict]:
    """Kategoria 'Maly, ale wariat': modele posortowane rosnaco wg rozmiaru GGUF."""
    scopes = (SCOPE_FULL, SWEEP_FILE)
    models = sorted({s["model"] for sc in scopes for s in idx["scopes"].get(sc, []) if s["model"] and s["kind"] == "T"})
    out = []
    for model in models:
        g = model_gguf(model)
        e: dict[str, Any] = {"model": model, "gguf": g, "size_gb": g["size_gb"] if g else None,
                             "params": model_params(model), "best": {}, "base": {}}
        for sc in scopes:
            systems = idx["scopes"].get(sc, [])
            t = best_t([s for s in systems if s["model"] == model], m)
            if t is not None:
                e["best"][sc] = t
                e["base"][sc] = pick_base(systems, t)
        out.append(e)
    out.sort(key=lambda e: (e["size_gb"] is None, e["size_gb"] or 0.0))
    return out


def small_winner(entries: list[dict], scope: str, m: str) -> Optional[dict]:
    for e in entries:
        t = e["best"].get(scope)
        if t is not None and e["size_gb"] is not None and t[m] * 100 >= SMALL_THRESHOLD_PCT:
            return e
    return None


def system_type_acc(s: dict) -> dict[str, float]:
    """Trafnosc per typ pytania (extract, z per_type w experiments.csv), wazona liczba pytan danego typu."""
    num: dict[str, float] = {}
    den: dict[str, float] = {}
    for r in s["rows"]:
        counts = devset_type_counts(r["files_key"])
        for t, v in r["per_type"].items():
            fv = parse_float(v)
            if fv is None:
                continue
            w = (counts or {}).get(t)
            if w is None:
                if len(s["rows"]) > 1:
                    continue
                w = 1
            num[t] = num.get(t, 0.0) + fv * w
            den[t] = den.get(t, 0.0) + w
    return {t: num[t] / den[t] for t in num if den.get(t)}


_records_cache: dict[str, tuple[tuple[float, int], list[dict]]] = {}


def load_run_records(p: Path) -> list[dict]:
    try:
        st = p.stat()
    except OSError:
        return []
    key = (st.st_mtime, st.st_size)
    hit = _records_cache.get(str(p))
    if hit and hit[0] == key:
        return hit[1]
    records = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    records.append(rec)
    except OSError:
        return []
    if len(_records_cache) > 64:
        _records_cache.clear()
    _records_cache[str(p)] = (key, records)
    return records


def context_titles(meta: dict) -> list[str]:
    ctx = meta.get("ctx") if isinstance(meta, dict) else None
    titles: list[str] = []
    if isinstance(ctx, list):
        for c in ctx:
            if isinstance(c, dict) and c.get("title"):
                titles.append(str(c["title"]))
            elif isinstance(c, str):
                titles.append(c)
    return titles


def rec_type(rec: dict) -> str:
    meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else {}
    return str(rec.get("type") or meta.get("qtype") or "?")


# --------------------------------------------------------------------------
# Wykresy (inline SVG). T = nasz system (seria 1, niebieski), B = goly model (seria 2, pomaranczowy).
# --------------------------------------------------------------------------

def bar_path(x: float, y: float, w: float, h: float, r: float = 4.0) -> str:
    """Slupek poziomy: prosty przy osi, zaokraglony (4px) na koncu z danymi."""
    if w <= 0:
        return ""
    r = min(r, w, h / 2)
    return "M{x:.1f},{y:.1f}h{a:.1f}a{r},{r} 0 0 1 {r},{r}v{v:.1f}a{r},{r} 0 0 1 -{r},{r}h-{a:.1f}z".format(
        x=x, y=y, a=w - r, r=r, v=h - 2 * r
    )


def trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def legend_html(items: list[tuple[str, str]]) -> str:
    return "<div class=\"legend\">" + "".join(
        "<span class=\"legend-item\"><span class=\"key key-{}\"></span>{}</span>".format(esc(cls), esc(txt))
        for cls, txt in items
    ) + "</div>"


def svg_axis(parts: list[str], plot_x: float, plot_w: float, top: float, bottom: float) -> None:
    for tick in (0, 25, 50, 75, 100):
        x = plot_x + plot_w * tick / 100
        parts.append('<line x1="{x:.1f}" y1="{t:.1f}" x2="{x:.1f}" y2="{b:.1f}" class="grid"/>'.format(x=x, t=top, b=bottom))
        parts.append('<text x="{x:.1f}" y="{y:.1f}" class="tick" text-anchor="middle">{v}%</text>'.format(x=x, y=bottom + 14, v=tick))


def svg_hbars(items: list[dict], threshold: Optional[float] = None, label_w: int = 230, width: int = 760) -> str:
    """Poziome slupki 0-100%. items: {label, sub?, value (ulamek), cls ('t'|'b'), title, href?}."""
    if not items:
        return ""
    row_h, bar_h, top = (30 if any(it.get("sub") for it in items) else 26), 14, 10
    plot_x = label_w + 10
    plot_w = width - plot_x - 64
    bottom = top + len(items) * row_h + 4
    parts: list[str] = []
    svg_axis(parts, plot_x, plot_w, top - 4, bottom)
    for i, it in enumerate(items):
        y = top + i * row_h
        cy = y + row_h / 2
        v = it.get("value")
        g = ['<g class="mark"><title>{}</title>'.format(esc(it.get("title") or it["label"]))]
        g.append('<rect x="0" y="{:.1f}" width="{}" height="{}" class="hit"/>'.format(y, width, row_h))
        g.append('<text x="{}" y="{:.1f}" class="lbl" text-anchor="end">{}</text>'.format(
            label_w, cy + (-1 if it.get("sub") else 4), esc(trunc(it["label"], 34))))
        if it.get("sub"):
            g.append('<text x="{}" y="{:.1f}" class="lbl-sub" text-anchor="end">{}</text>'.format(label_w, cy + 11, esc(trunc(it["sub"], 40))))
        if v is not None:
            w = max(0.0, min(v, 1.0)) * plot_w
            g.append('<path d="{}" class="bar-{}"/>'.format(bar_path(plot_x, cy - bar_h / 2, w, bar_h), esc(it.get("cls", "t"))))
            g.append('<text x="{:.1f}" y="{:.1f}" class="val">{}</text>'.format(plot_x + w + 6, cy + 4, esc(fmt_pct(v))))
        else:
            g.append('<text x="{:.1f}" y="{:.1f}" class="lbl-sub">brak danych</text>'.format(plot_x + 4, cy + 4))
        g.append("</g>")
        body = "".join(g)
        if it.get("href"):
            body = '<a href="{}">{}</a>'.format(esc(it["href"]), body)
        parts.append(body)
    if threshold is not None:
        x = plot_x + plot_w * threshold / 100
        parts.append('<line x1="{x:.1f}" y1="{t}" x2="{x:.1f}" y2="{b:.1f}" class="thr"/>'.format(x=x, t=top - 6, b=bottom))
        parts.append('<text x="{:.1f}" y="{}" class="thr-lbl">próg {:.0f}%</text>'.format(x + 4, top - 1, threshold))
    h = bottom + 22
    return '<div class="chartwrap"><svg class="chart" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">{p}</svg></div>'.format(
        w=width, h=h, p="".join(parts))


def svg_dumbbell(rows: list[dict], label_w: int = 200, width: int = 760) -> str:
    """Przyrost: kropka B -> kropka T na wspolnej osi 0-100%, po prawej podpis przyrostu."""
    if not rows:
        return ""
    row_h, top = 26, 10
    plot_x = label_w + 10
    plot_w = width - plot_x - 86
    bottom = top + len(rows) * row_h + 4
    parts: list[str] = []
    svg_axis(parts, plot_x, plot_w, top - 4, bottom)
    for i, r in enumerate(rows):
        y = top + i * row_h
        cy = y + row_h / 2
        g = ['<g class="mark"><title>{}</title>'.format(esc(r.get("title") or r["label"]))]
        g.append('<rect x="0" y="{:.1f}" width="{}" height="{}" class="hit"/>'.format(y, width, row_h))
        g.append('<text x="{}" y="{:.1f}" class="lbl" text-anchor="end">{}</text>'.format(label_w, cy + 4, esc(trunc(r["label"], 30))))
        xt = plot_x + plot_w * max(0.0, min(r["t"], 1.0))
        if r.get("b") is not None:
            xb = plot_x + plot_w * max(0.0, min(r["b"], 1.0))
            g.append('<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" class="db-line"/>'.format(xb, cy, xt, cy))
            g.append('<circle cx="{:.1f}" cy="{:.1f}" r="5" class="dot-b"/>'.format(xb, cy))
        g.append('<circle cx="{:.1f}" cy="{:.1f}" r="5" class="dot-t"/>'.format(xt, cy))
        g.append('<text x="{}" y="{:.1f}" class="val val-strong">{}</text>'.format(plot_x + plot_w + 12, cy + 4, esc(fmt_pts(r.get("gain")))))
        g.append("</g>")
        body = "".join(g)
        if r.get("href"):
            body = '<a href="{}">{}</a>'.format(esc(r["href"]), body)
        parts.append(body)
    h = bottom + 22
    return '<div class="chartwrap"><svg class="chart" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">{p}</svg></div>'.format(
        w=width, h=h, p="".join(parts))


def svg_paired(rows: list[dict], label_w: int = 150, width: int = 640) -> str:
    """Pary slupkow T/B na wiersz (np. typy pytan). rows: {label, t, b (ulamki), title}."""
    if not rows:
        return ""
    bar_h, gap, top = 10, 2, 10
    row_h = 2 * bar_h + gap + 12
    plot_x = label_w + 10
    plot_w = width - plot_x - 60
    bottom = top + len(rows) * row_h
    parts: list[str] = []
    svg_axis(parts, plot_x, plot_w, top - 4, bottom)
    for i, r in enumerate(rows):
        y = top + i * row_h + 4
        g = ['<g class="mark"><title>{}</title>'.format(esc(r.get("title") or r["label"]))]
        g.append('<rect x="0" y="{:.1f}" width="{}" height="{}" class="hit"/>'.format(y - 4, width, row_h))
        g.append('<text x="{}" y="{:.1f}" class="lbl" text-anchor="end">{}</text>'.format(label_w, y + bar_h + 3, esc(trunc(r["label"], 24))))
        for j, (key, cls) in enumerate((("t", "t"), ("b", "b"))):
            v = r.get(key)
            if v is None:
                continue
            by = y + j * (bar_h + gap)
            w = max(0.0, min(v, 1.0)) * plot_w
            g.append('<path d="{}" class="bar-{}"/>'.format(bar_path(plot_x, by, w, bar_h, 3), cls))
            g.append('<text x="{:.1f}" y="{:.1f}" class="val">{}</text>'.format(plot_x + w + 5, by + bar_h - 1, esc(fmt_pct(v))))
        g.append("</g>")
        parts.append("".join(g))
    h = bottom + 22
    return '<div class="chartwrap"><svg class="chart" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">{p}</svg></div>'.format(
        w=width, h=h, p="".join(parts))


def svg_mini(t: Optional[float], b: Optional[float]) -> str:
    """Mini-wykres do komorki tabeli: T (gora) i B (dol), skala 0-100%."""
    w, bh = 110, 5
    parts = []
    for j, (v, cls) in enumerate(((t, "t"), (b, "b"))):
        if v is None:
            continue
        parts.append('<rect x="0" y="{}" width="{:.1f}" height="{}" rx="1.5" class="bar-{}"/>'.format(
            1 + j * (bh + 2), max(1.0, min(v, 1.0) * w), bh, cls))
    title = "T {} · B {}".format(fmt_pct(t), fmt_pct(b))
    return '<svg class="mini" width="{w}" height="14" viewBox="0 0 {w} 14" role="img"><title>{t}</title>{p}</svg>'.format(
        w=w, t=esc(title), p="".join(parts))


# --------------------------------------------------------------------------
# Wspolne kawalki HTML
# --------------------------------------------------------------------------

def model_link(model: Optional[str], m: str) -> str:
    if not model:
        return "<span class=\"muted\">?</span>"
    return "<a href=\"{}\">{}</a>".format(esc(url("/model/" + quote(model), m=m)), esc(model))


def run_link(row: Optional[dict], m: str, text: str = "pytania") -> str:
    if row is None:
        return ""
    if row.get("run_path") is None:
        # wartosc zostaje widoczna; brak linku = plik per pytanie jest na innej maszynie
        return "<span class=\"{}\" title=\"brak pliku per pytanie na tym Macu: {}\">{}</span>".format(
            "muted small" if text == "pytania" else "nofile", esc(row.get("run_file") or "-"),
            "brak pliku" if text == "pytania" else esc(text))
    return "<a href=\"{}\">{}</a>".format(esc(url("/run", file=rel_of(row["run_path"]), m=m)), esc(text))


def compare_link(b_row: Optional[dict], t_row: Optional[dict], m: str, text: str = "porównaj pytania") -> str:
    if not b_row or not t_row or b_row.get("run_path") is None or t_row.get("run_path") is None:
        return ""
    return "<a href=\"{}\">{}</a>".format(
        esc(url("/porownaj", b=rel_of(b_row["run_path"]), t=rel_of(t_row["run_path"]), m=m)), esc(text))


def compare_pair_with_files(idx: dict, scope: str, model: str, m: str) -> str:
    """Najlepsza para B/T modelu na zakresie, dla ktorej oba pliki per pytanie sa na tym Macu."""
    systems = [s for s in idx["scopes"].get(scope, []) if s["model"] == model and len(s["rows"]) == 1 and s["rows"][0]["run_path"]]
    t = best_t(systems, m)
    b = pick_base(systems, t) if t else None
    if not t or not b:
        return ""
    return compare_link(b["rows"][0], t["rows"][0], m, "porównaj ({})".format(t["label"]))


def kind_badge(kind: str) -> str:
    if kind == "T":
        return "<span class=\"kind kind-t\" title=\"nasz system (harness)\">T</span>"
    if kind == "B":
        return "<span class=\"kind kind-b\" title=\"model bazowy\">B</span>"
    return "<span class=\"kind\">?</span>"


def tile(label: str, value: str, sub: str = "", href: str = "", extra_cls: str = "") -> str:
    link = "<a class=\"tile-link\" href=\"{}\">szczegóły &rarr;</a>".format(esc(href)) if href else ""
    return "<div class=\"tile {cls}\"><div class=\"tile-label\">{l}</div><div class=\"tile-value\">{v}</div><div class=\"tile-sub\">{s}</div>{a}</div>".format(
        cls=esc(extra_cls), l=label, v=value, s=sub, a=link)


def section(title: str, body: str, sid: str = "", note: str = "") -> str:
    return "<section class=\"card\"{sid}><h2>{t}</h2>{n}{b}</section>".format(
        sid=' id="{}"'.format(esc(sid)) if sid else "", t=title,
        n="<p class=\"muted small intro\">{}</p>".format(note) if note else "", b=body)


def pass_badge(ok: Optional[bool]) -> str:
    if ok is None:
        return "<span class=\"muted\">–</span>"
    if ok:
        return "<span class=\"status status-good\">&#10003; &ge; {:.0f}%</span>".format(SMALL_THRESHOLD_PCT)
    return "<span class=\"status status-crit\">&#10007; &lt; {:.0f}%</span>".format(SMALL_THRESHOLD_PCT)


def size_badge(gb: Optional[float]) -> str:
    if gb is None:
        return "<span class=\"muted small\">brak GGUF na Macu</span>"
    cls = "badge-ok" if gb <= MODEL_SIZE_LIMIT_GB else "badge-bad"
    return "{} <span class=\"badge {}\">{}</span>".format(esc(fmt_gb(gb)), cls, "&le; 8 GB" if gb <= MODEL_SIZE_LIMIT_GB else "ZA DUŻY")


def metric_note(m: str) -> str:
    return "Ocena <b>{}</b>{}. Przełącznik w nagłówku zmienia ocenę na wszystkich stronach.".format(
        esc(METRICS[m]), " (dokładny format odpowiedzi, jak automatyczny sprawdzający)" if m == "strict" else " (poprawna odpowiedź gdziekolwiek w tekście)")


def filter_bar(target: str, selects: list[tuple[str, str, list[tuple[str, str]]]], search: bool = True) -> str:
    """Pasek filtrow po stronie klienta; wiersze tabeli maja atrybuty data-<klucz>."""
    parts = ["<div class=\"filters\" data-target=\"{}\">".format(esc(target))]
    for key, label, options in selects:
        opts = "".join("<option value=\"{}\">{}</option>".format(esc(v), esc(t)) for v, t in options)
        parts.append("<label>{} <select data-key=\"{}\">{}</select></label>".format(esc(label), esc(key), opts))
    if search:
        parts.append("<label>szukaj <input type=\"search\" data-key=\"q\" placeholder=\"tekst, id, tytuł...\"></label>")
    parts.append("<span class=\"filter-count muted small\"></span></div>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Strona: Przeglad
# --------------------------------------------------------------------------

def render_overview(idx: dict, m: str) -> str:
    parts = []
    tiles = []
    gain_scope = SCOPE_FULL if model_gains(idx, SCOPE_FULL, m) else SWEEP_FILE
    gains = [g for g in model_gains(idx, gain_scope, m) if g["gain"] is not None]
    if gains:
        g = gains[0]
        tiles.append(tile(
            "Największy przyrost &middot; priorytet",
            esc(fmt_pts(g["gain"])),
            "{model}: T {t} &minus; B {b}<br><span class=\"small\">{tl} vs {bl} &middot; {sc}</span>".format(
                model=model_link(g["model"], m), t=esc(fmt_pct(g["t"][m])), b=esc(fmt_pct(g["b"][m])),
                tl=esc(g["t"]["label"]), bl=esc(g["b"]["label"]), sc=esc(scope_title(gain_scope))),
            url("/przyrost", m=m), "tile-hero"))
    else:
        tiles.append(tile("Największy przyrost", "–", "brak par B/T w experiments.csv", url("/przyrost", m=m)))

    best_scope = SCOPE_FULL if best_t(idx["scopes"].get(SCOPE_FULL, []), m) else SWEEP_FILE
    best = best_t(idx["scopes"].get(best_scope, []), m)
    if best:
        tiles.append(tile(
            "Najlepszy wynik",
            esc(fmt_pct(best[m])),
            "{model} &middot; {v}<br><span class=\"small\">{l} &middot; {sc}</span>".format(
                model=model_link(best["model"], m), v=esc(variant_name(best["variant"])), l=esc(best["label"]),
                sc=esc(scope_title(best_scope))),
            url("/wynik", m=m)))
    else:
        tiles.append(tile("Najlepszy wynik", "–", "brak przebiegów systemu", url("/wynik", m=m)))

    entries = small_models(idx, m)
    win = small_winner(entries, SWEEP_FILE, m)
    if win:
        t = win["best"][SWEEP_FILE]
        tiles.append(tile(
            "Mały, ale wariat",
            esc(win["model"]),
            "{gb} &middot; {p} param. &middot; {s} ({marg} nad progiem)<br><span class=\"small\">{l} &middot; {sc}</span>".format(
                gb=esc(fmt_gb(win["size_gb"])), p=esc(win["params"]), s=esc(fmt_pct(t[m])),
                marg=esc(fmt_pts(t[m] * 100 - SMALL_THRESHOLD_PCT)), l=esc(t["label"]), sc=esc(scope_title(SWEEP_FILE))),
            url("/maly", m=m)))
    else:
        tiles.append(tile("Mały, ale wariat", "–", "żaden model nie ma &ge; 35%", url("/maly", m=m)))
    parts.append("<div class=\"tiles\">" + "".join(tiles) + "</div>")

    # przyrost w skrocie: pelny benchmark + sweep
    for scope in (SCOPE_FULL, SWEEP_FILE):
        rows = [g for g in model_gains(idx, scope, m) if g["gain"] is not None][:8]
        if not rows:
            continue
        chart = svg_dumbbell([
            {"label": g["model"], "t": g["t"][m], "b": g["b"][m], "gain": g["gain"],
             "href": url("/model/" + quote(g["model"]), m=m),
             "title": "{}: T {} ({}) − B {} ({}) = {}".format(g["model"], fmt_pct(g["t"][m]), g["t"]["label"],
                                                          fmt_pct(g["b"][m]), g["b"]["label"], fmt_pts(g["gain"]))}
            for g in rows])
        parts.append(section(
            "Przyrost T &minus; B: {}".format(esc(scope_title(scope))),
            legend_html([("b", "goły model (B)"), ("t", "nasz system (T)")]) + chart,
            note="Top {} modeli wg przyrostu. Kliknij model, żeby zobaczyć jego wszystkie wyniki. {}".format(len(rows), metric_note(m))))

    # ostatnie przebiegi
    recent = idx["rows"][:10]
    if recent:
        body = "".join(
            "<tr><td>{ts}</td><td>{k} {l}</td><td>{model}</td><td>{sc}</td><td class=\"num\">{n}</td>"
            "<td class=\"num\">{s}</td><td class=\"num\">{le}</td><td>{link}</td></tr>".format(
                ts=esc(short_ts(r["ts"])), k=kind_badge(r["kind"]), l=esc(r["label"]), model=model_link(r["model"], m),
                sc=esc(r["files_key"].replace(".jsonl", "")), n=r["n"], s=esc(fmt_pct(r["strict"])),
                le=esc(fmt_pct(r["lenient"])), link=run_link(r, m))
            for r in recent)
        parts.append(section(
            "Ostatnie przebiegi",
            "<div class=\"tablewrap\"><table><thead><tr><th>Czas</th><th>Etykieta</th><th>Model</th><th>Zestaw</th>"
            "<th class=\"num\">n</th><th class=\"num\">Ścisła</th><th class=\"num\">Łagodna</th><th>Per pytanie</th></tr></thead>"
            "<tbody>" + body + "</tbody></table></div><p class=\"small\"><a href=\"{}\">wszystkie przebiegi &rarr;</a></p>".format(
                esc(url("/przebiegi", m=m)))))

    # stan danych
    rows = idx["rows"]
    missing = [r for r in rows if r["run_path"] is None]
    missing_final = sorted({r["label"] for r in missing if r["series"] == "final"})
    try:
        csv_mtime = time.strftime("%d.%m %H:%M", time.localtime(EXPERIMENTS_CSV.stat().st_mtime))
    except OSError:
        csv_mtime = "?"
    info = [
        "<li><code>devset/experiments.csv</code>: {} przebiegów, ostatnia zmiana {}</li>".format(len(rows), esc(csv_mtime)),
        "<li>pliki per pytanie (<code>devset/runs/</code>): {} z {} przebiegów ma plik na tym Macu</li>".format(len(rows) - len(missing), len(rows)),
    ]
    if missing_final:
        info.append(
            "<li class=\"warn\">Brak plików per pytanie dla najlepszych systemów ({}). Wyniki procentowe są, ale "
            "podgląd pytań i porównania B/T zadziałają dopiero, gdy pliki z <code>run_file</code> trafią do "
            "<code>devset/runs/</code> na Macu; panel podchwyci je sam.</li>".format(esc(", ".join(missing_final))))
    parts.append(section("Stan danych", "<ul class=\"plain\">" + "".join(info) + "</ul>"))
    return "".join(parts)


# --------------------------------------------------------------------------
# Strona: Przyrost
# --------------------------------------------------------------------------

def render_gain_page(idx: dict, m: str) -> str:
    other = "lenient" if m == "strict" else "strict"
    parts = []
    for scope in (SCOPE_FULL, SWEEP_FILE):
        gains = model_gains(idx, scope, m)
        if not gains:
            continue
        with_b = [g for g in gains if g["gain"] is not None]
        chart = svg_dumbbell([
            {"label": g["model"], "t": g["t"][m], "b": g["b"][m], "gain": g["gain"],
             "href": url("/model/" + quote(g["model"]), m=m),
             "title": "{}: T {} ({}) − B {} ({}) = {}".format(g["model"], fmt_pct(g["t"][m]), g["t"]["label"],
                                                          fmt_pct(g["b"][m]), g["b"]["label"], fmt_pts(g["gain"]))}
            for g in with_b])
        body_rows = []
        for g in gains:
            t, b = g["t"], g["b"]
            gain_other = None if (b is None or b[other] is None or t[other] is None) else (t[other] - b[other]) * 100
            gg = model_gguf(g["model"])
            if scope == SCOPE_FULL:
                per_q = "<a href=\"{}\">per zestaw</a>".format(esc(url("/model/" + quote(g["model"]), m=m) + "#zestawy"))
            else:
                per_q = compare_link(b["rows"][0] if b else None, t["rows"][0], m) or compare_pair_with_files(idx, scope, g["model"], m) \
                    or run_link(t["rows"][0], m)
            body_rows.append(
                "<tr><td>{model}</td><td class=\"num\" data-sort-value=\"{gbv}\">{gb}</td>"
                "<td class=\"small\">{bl}</td><td class=\"num\" data-sort-value=\"{bv}\">{b}</td>"
                "<td class=\"small\">{tl}</td><td class=\"num\" data-sort-value=\"{tv}\">{t}</td>"
                "<td class=\"num strong\" data-sort-value=\"{gv}\">{g}</td><td class=\"num\" data-sort-value=\"{g2v}\">{g2}</td>"
                "<td>{mini}</td><td>{pq}</td></tr>".format(
                    model=model_link(g["model"], m), gbv=sv(gg["size_gb"] if gg else None), gb=esc(fmt_gb(gg["size_gb"] if gg else None)),
                    bl=esc(b["label"]) if b else "<span class=\"muted\">brak base-raw</span>",
                    bv=sv(b[m] if b else None), b=esc(fmt_pct(b[m] if b else None)),
                    tl=esc(t["label"]), tv=sv(t[m]), t=esc(fmt_pct(t[m])),
                    gv=sv(g["gain"]), g=esc(fmt_pts(g["gain"])), g2v=sv(gain_other), g2=esc(fmt_pts(gain_other)),
                    mini=svg_mini(t[m], b[m] if b else None), pq=per_q))
        table = (
            "<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr><th>Model</th><th class=\"num\">GGUF</th>"
            "<th>B: system</th><th class=\"num\">B</th><th>T: najlepszy system</th><th class=\"num\">T</th>"
            "<th class=\"num\">Przyrost ({m})</th><th class=\"num\">Przyrost ({o})</th><th>T / B</th><th>Per pytanie</th>"
            "</tr></thead><tbody>{rows}</tbody></table></div>".format(m=esc(METRICS[m]), o=esc(METRICS[other]), rows="".join(body_rows)))
        parts.append(section(
            "Przyrost na: {}".format(esc(scope_title(scope))),
            legend_html([("b", "goły model (B)"), ("t", "nasz system (T)")]) + chart + table,
            note="T = najlepszy system z harnessem dla modelu, B = nietknięty model bazowy (<code>base-raw</code>, bez "
                 "promptu systemowego) na tych samych pytaniach, najlepiej z tej samej serii przebiegów. {}".format(metric_note(m))))
    if not parts:
        parts.append(section("Przyrost", "<p class=\"muted\">Brak par B/T (etykiety *-base-raw i *-harness-*) w experiments.csv.</p>"))
    parts.append(render_variant_ladder(idx, m))
    return "".join(parts)


def render_variant_ladder(idx: dict, m: str) -> str:
    """Co daje kazdy element: wynik kazdego wariantu modelu na tym samym zakresie."""
    blocks = []
    for scope in (SCOPE_FULL, SWEEP_FILE):
        systems = [s for s in idx["scopes"].get(scope, []) if s["complete"] and s["model"] and s["variant"] and s[m] is not None]
        per_model: dict[str, dict[str, dict]] = {}
        for s in systems:
            cur = per_model.setdefault(s["model"], {}).get(s["variant"])
            if cur is None or s[m] > cur[m]:
                per_model[s["model"]][s["variant"]] = s
        per_model = {k: v for k, v in per_model.items() if len(v) >= 2}
        if not per_model:
            continue
        variants = [v for v in VARIANT_ORDER if any(v in d for d in per_model.values())]
        variants += sorted({v for d in per_model.values() for v in d} - set(variants))
        rows = []
        for model in sorted(per_model, key=lambda k: -max(s[m] for s in per_model[k].values())):
            d = per_model[model]
            cells = []
            for v in variants:
                s = d.get(v)
                if s is None:
                    cells.append("<td class=\"num muted\" data-sort-value=\"-999\">–</td>")
                else:
                    link = run_link(s["rows"][0], m, fmt_pct(s[m])) if scope != SCOPE_FULL else esc(fmt_pct(s[m]))
                    cells.append("<td class=\"num\" data-sort-value=\"{}\" title=\"{}\">{}</td>".format(sv(s[m]), esc(s["label"]), link))
            rows.append("<tr><td>{}</td>{}</tr>".format(model_link(model, m), "".join(cells)))
        blocks.append(
            "<h3 class=\"subhead\">{}</h3><div class=\"tablewrap\"><table class=\"sortable\"><thead><tr><th>Model</th>{}</tr></thead>"
            "<tbody>{}</tbody></table></div>".format(
                esc(scope_title(scope)),
                "".join("<th class=\"num\" title=\"{}\">{}</th>".format(esc(v), esc(variant_name(v))) for v in variants),
                "".join(rows)))
    if not blocks:
        return ""
    return section("Warianty systemu: co daje każdy element", "".join(blocks),
                   note="Każda kolumna to wariant (goły model, harness v1 bez/z bazą wiedzy, harness v2, LoRA). "
                        "Przy kilku seriach tego samego wariantu pokazany jest najlepszy wynik. {}".format(metric_note(m)))


# --------------------------------------------------------------------------
# Strona: Najlepszy wynik
# --------------------------------------------------------------------------

def render_best_page(idx: dict, m: str, zestaw: str, typ: str) -> str:
    scopes = [sc for sc in ordered_scopes(idx) if any(s["kind"] == "T" for s in idx["scopes"][sc])]
    if zestaw not in scopes:
        zestaw = SCOPE_FULL if SCOPE_FULL in scopes else (SWEEP_FILE if SWEEP_FILE in scopes else (scopes[0] if scopes else ""))
    if typ not in QTYPES:
        typ = ""
    if not zestaw:
        return section("Najlepszy wynik", "<p class=\"muted\">Brak przebiegów systemu w experiments.csv.</p>")

    def seg(param: str, value: str, text: str, current: str) -> str:
        params = {"m": m, "zestaw": zestaw, "typ": typ}
        params[param] = value
        return "<a class=\"seg{}\" href=\"{}\">{}</a>".format(" active" if value == current else "", esc(url("/wynik", **params)), esc(text))

    ctrl = (
        "<div class=\"segs\"><span class=\"seg-label\">Zestaw</span>" + "".join(
            seg("zestaw", sc, "pełny (673)" if sc == SCOPE_FULL else sc.replace(".jsonl", ""), zestaw) for sc in scopes) + "</div>"
        "<div class=\"segs\"><span class=\"seg-label\">Typ pytań</span>" + seg("typ", "", "wszystkie", typ) + "".join(
            seg("typ", t, QTYPE_NAMES[t], typ) for t in QTYPES) + "</div>"
    )

    systems = idx["scopes"].get(zestaw, [])

    def value(s: dict) -> Optional[float]:
        return system_type_acc(s).get(typ) if typ else s[m]

    ranked = [s for s in systems if s["kind"] == "T" and s["complete"] and value(s) is not None]
    ranked.sort(key=lambda s: (value(s), s["ts"]), reverse=True)
    partial = [s for s in systems if s["kind"] == "T" and not s["complete"]]
    what = "trafność extract dla typu „{}” (z per_type w experiments.csv)".format(QTYPE_NAMES[typ]) if typ else "ocena " + METRICS[m]

    parts = [section("Najlepszy wynik: filtr", ctrl,
                     note="Ranking systemów z harnessem (T) na wybranym zestawie. Filtr typu pytań używa trafności extract, bo tylko "
                          "ją zapisuje eval.py per typ.")]
    if ranked:
        top = ranked[0]
        b = pick_base(systems, top)
        tiles = [
            tile("Najlepszy system", esc(fmt_pct(value(top))), "{} &middot; {}<br><span class=\"small\">{} &middot; {}</span>".format(
                model_link(top["model"], m), esc(variant_name(top["variant"])), esc(top["label"]), esc(what)), "", "tile-hero"),
            tile("Jego goły model (B)", esc(fmt_pct(value(b) if b else None)), esc(b["label"]) if b else "brak base-raw"),
            tile("Liczba pytań", str(top["n"]), esc(scope_title(zestaw))),
        ]
        chart = svg_hbars([
            {"label": s["label"], "sub": variant_name(s["variant"]), "value": value(s), "cls": "t",
             "href": url("/model/" + quote(s["model"]), m=m) if s["model"] else "",
             "title": "{} ({}): {}".format(s["label"], variant_name(s["variant"]), fmt_pct(value(s)))}
            for s in ranked[:15]])
        rows = []
        for i, s in enumerate(ranked, 1):
            bb = pick_base(systems, s)
            bv = value(bb) if bb else None
            vv = value(s)
            gain = None if (bv is None or vv is None) else (vv - bv) * 100
            per_q = run_link(s["rows"][0], m) if zestaw != SCOPE_FULL else "<a href=\"{}\">per zestaw</a>".format(
                esc(url("/model/" + quote(s["model"] or ""), m=m) + "#zestawy"))
            rows.append(
                "<tr><td class=\"num\">{i}</td><td>{l}</td><td>{model}</td><td>{v}</td>"
                "<td class=\"num strong\" data-sort-value=\"{tv}\">{t}</td><td class=\"num\" data-sort-value=\"{bvv}\">{b}</td>"
                "<td class=\"num\" data-sort-value=\"{gv}\">{g}</td><td class=\"num\">{n}</td><td class=\"num\" data-sort-value=\"{p50v}\">{p50}</td>"
                "<td>{ts}</td><td>{pq}</td></tr>".format(
                    i=i, l=esc(s["label"]), model=model_link(s["model"], m), v=esc(variant_name(s["variant"])),
                    tv=sv(vv), t=esc(fmt_pct(vv)), bvv=sv(bv), b=esc(fmt_pct(bv)), gv=sv(gain), g=esc(fmt_pts(gain)),
                    n=s["n"], p50v=sv(s["rows"][0]["p50"] if len(s["rows"]) == 1 else None),
                    p50=esc("{:.1f} s".format(s["rows"][0]["p50"]).replace(".", ",") if len(s["rows"]) == 1 and s["rows"][0]["p50"] is not None else "–"),
                    ts=esc(short_ts(s["ts"])), pq=per_q))
        table = (
            "<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr><th class=\"num\">#</th><th>System</th><th>Model</th><th>Wariant</th>"
            "<th class=\"num\">T</th><th class=\"num\">B</th><th class=\"num\">Przyrost</th><th class=\"num\">n</th><th class=\"num\">p50</th>"
            "<th>Czas</th><th>Per pytanie</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
        parts.append("<div class=\"tiles\">" + "".join(tiles) + "</div>")
        parts.append(section("Ranking: {} &middot; {}".format(esc(scope_title(zestaw)), esc(what)), chart + table))
    else:
        parts.append(section("Ranking", "<p class=\"muted\">Brak systemów z pełnym pokryciem dla tego filtra.</p>"))
    if partial:
        prow = "".join(
            "<tr><td>{}</td><td>{}</td><td class=\"num\">{}/{}</td><td class=\"num\">{}</td><td class=\"num\">{}</td></tr>".format(
                esc(s["label"]), model_link(s["model"], m), s["coverage"], len(FULL_BENCH_FILES), s["n"], esc(fmt_pct(value(s))))
            for s in sorted(partial, key=lambda s: -s["coverage"]))
        parts.append(section("Niepełne pokrycie (nie wliczane do rankingu)",
                             "<details><summary class=\"small\">{} systemów ma przebiegi tylko na części z 9 zestawów (pokaż)</summary>"
                             "<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr><th>System</th><th>Model</th>"
                             "<th class=\"num\">Zestawy</th><th class=\"num\">n</th><th class=\"num\">Wynik na tym, co jest</th></tr></thead>"
                             "<tbody>".format(len(partial)) + prow + "</tbody></table></div></details>"))
    parts.append(render_matrix(idx, m, typ))
    return "".join(parts)


def render_matrix(idx: dict, m: str, typ: str = "", model: Optional[str] = None) -> str:
    """Macierz system x zestaw z pelnego benchmarku; kazda komorka prowadzi do pytan tego przebiegu."""
    full = [s for s in idx["scopes"].get(SCOPE_FULL, []) if model is None or s["model"] == model]
    if not full:
        return ""

    def cell_val(r: dict) -> Optional[float]:
        if typ:
            v = parse_float(r["per_type"].get(typ))
            return v
        return r[m]

    def total(s: dict) -> Optional[float]:
        return system_type_acc(s).get(typ) if typ else s[m]

    full.sort(key=lambda s: (s["kind"] != "T", -(total(s) or 0)))
    best_col: dict[str, float] = {}
    for s in full:
        if s["kind"] != "T":
            continue
        for r in s["rows"]:
            v = cell_val(r)
            if v is not None and v > best_col.get(r["files_key"], -1):
                best_col[r["files_key"]] = v
    rows = []
    for s in full:
        per = {r["files_key"]: r for r in s["rows"]}
        cells = []
        for f in FULL_BENCH_FILES:
            r = per.get(f)
            if r is None:
                cells.append("<td class=\"num muted\" data-sort-value=\"-999\">–</td>")
                continue
            v = cell_val(r)
            cls = "num best" if (s["kind"] == "T" and v is not None and v == best_col.get(f)) else "num"
            txt = fmt_pct(v)
            inner = run_link(r, m, txt) if r["run_path"] is not None else "<span title=\"brak pliku per pytanie na Macu\">{}</span>".format(esc(txt))
            cells.append("<td class=\"{}\" data-sort-value=\"{}\">{}</td>".format(cls, sv(v), inner))
        tv = total(s)
        rows.append("<tr><td>{k} {l}</td><td>{model}</td><td class=\"num strong\" data-sort-value=\"{tv}\">{t}{cov}</td>{cells}</tr>".format(
            k=kind_badge(s["kind"]), l=esc(s["label"]), model=model_link(s["model"], m), tv=sv(tv), t=esc(fmt_pct(tv)),
            cov="" if s["complete"] else " <span class=\"muted small\">({}/{})</span>".format(s["coverage"], len(FULL_BENCH_FILES)),
            cells="".join(cells)))
    head = "".join("<th class=\"num\">{}</th>".format(esc(f.replace(".jsonl", ""))) for f in FULL_BENCH_FILES)
    what = "extract, typ „{}”".format(QTYPE_NAMES[typ]) if typ else METRICS[m]
    return section(
        "Wyniki per zestaw ({})".format(esc(what)),
        "<div class=\"tablewrap\"><table class=\"sortable matrix\"><thead><tr><th>System</th><th>Model</th><th class=\"num\">Pełny</th>"
        + head + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>",
        sid="zestawy",
        note="Każda komórka to jeden przebieg eval.py; kliknij wartość, żeby zobaczyć odpowiedzi na pytania. "
             "Pogrubienie = najlepszy system T w kolumnie. Wartość bez linku = plik per pytanie jest na innej maszynie.")


# --------------------------------------------------------------------------
# Strona: Maly, ale wariat
# --------------------------------------------------------------------------

def render_small_page(idx: dict, m: str) -> str:
    entries = small_models(idx, m)
    if not entries:
        return section("Mały, ale wariat", "<p class=\"muted\">Brak przebiegów systemu na tourney160 ani na pełnym benchmarku.</p>")
    parts = []
    tiles = []
    for scope in (SWEEP_FILE, SCOPE_FULL):
        n_models = sum(1 for e in entries if scope in e["best"])
        if not n_models:
            continue
        win = small_winner(entries, scope, m)
        if win:
            t = win["best"][scope]
            tiles.append(tile(
                "Zwycięzca: {}".format(esc(scope_title(scope))), esc(win["model"]),
                "{gb} &middot; {p} param. &middot; {s} (zapas {marg})<br><span class=\"small\">{l} &middot; "
                "najmniejszy z {k} modeli z wynikami na tym zestawie</span>".format(
                    gb=esc(fmt_gb(win["size_gb"])), p=esc(win["params"]), s=esc(fmt_pct(t[m])),
                    marg=esc(fmt_pts(t[m] * 100 - SMALL_THRESHOLD_PCT)), l=esc(t["label"]), k=n_models),
                url("/model/" + quote(win["model"]), m=m), "tile-hero" if scope == SWEEP_FILE else ""))
        else:
            tiles.append(tile("Zwycięzca: {}".format(esc(scope_title(scope))), "–", "żaden model nie ma &ge; 35%"))
    # najmniejszy model, ktory NIE przeszedl progu (czy warto go dociagnac?)
    win = small_winner(entries, SWEEP_FILE, m)
    if win:
        smaller = [e for e in entries if e["size_gb"] is not None and e["size_gb"] < win["size_gb"] and SWEEP_FILE in e["best"]]
        if smaller:
            c = max(smaller, key=lambda e: e["best"][SWEEP_FILE][m])
            t = c["best"][SWEEP_FILE]
            tiles.append(tile(
                "Mniejszy kandydat", esc(c["model"]),
                "{gb} &middot; {s} (brakuje {miss} do progu)<br><span class=\"small\">{l}</span>".format(
                    gb=esc(fmt_gb(c["size_gb"])), s=esc(fmt_pct(t[m])),
                    miss=esc(fmt_pts(SMALL_THRESHOLD_PCT - t[m] * 100).lstrip("+")), l=esc(t["label"])),
                url("/model/" + quote(c["model"]), m=m)))
    parts.append("<div class=\"tiles\">" + "".join(tiles) + "</div>")

    for scope in (SWEEP_FILE, SCOPE_FULL):
        es = [e for e in entries if scope in e["best"]]
        if not es:
            continue
        chart = svg_hbars([
            {"label": e["model"], "sub": "{} · {} param.".format(fmt_gb(e["size_gb"]), e["params"]),
             "value": e["best"][scope][m], "cls": "t", "href": url("/model/" + quote(e["model"]), m=m),
             "title": "{} ({}): {} · {}".format(e["model"], fmt_gb(e["size_gb"]), fmt_pct(e["best"][scope][m]), e["best"][scope]["label"])}
            for e in es], threshold=SMALL_THRESHOLD_PCT)
        parts.append(section(
            "Najlepszy wynik vs rozmiar: {}".format(esc(scope_title(scope))), chart,
            note="Modele od najmniejszego pliku GGUF. Pionowa linia = próg {:.0f}%. {}".format(SMALL_THRESHOLD_PCT, metric_note(m))))

    rows = []
    for e in entries:
        cells = []
        for scope in (SWEEP_FILE, SCOPE_FULL):
            t = e["best"].get(scope)
            b = e["base"].get(scope)
            if t is None:
                cells.append("<td class=\"num muted\" data-sort-value=\"-999\">–</td><td></td><td class=\"num muted\">–</td><td></td>")
                continue
            ok = t[m] * 100 >= SMALL_THRESHOLD_PCT
            cells.append(
                "<td class=\"num strong\" data-sort-value=\"{tv}\">{t}</td><td class=\"small\">{l}</td>"
                "<td class=\"num\" data-sort-value=\"{bv}\">{b}</td><td>{ok}</td>".format(
                    tv=sv(t[m]), t=run_link(t["rows"][0], m, fmt_pct(t[m])) if scope != SCOPE_FULL else esc(fmt_pct(t[m])),
                    l=esc(t["label"]), bv=sv(b[m] if b else None), b=esc(fmt_pct(b[m] if b else None)), ok=pass_badge(ok)))
        rows.append("<tr><td>{model}</td><td>{p}</td><td class=\"num\" data-sort-value=\"{gbv}\">{gb}</td>{cells}</tr>".format(
            model=model_link(e["model"], m), p=esc(e["params"]), gbv=sv(e["size_gb"]), gb=size_badge(e["size_gb"]), cells="".join(cells)))
    parts.append(section(
        "Wszystkie modele",
        "<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr><th>Model</th><th>Param.</th><th class=\"num\">GGUF</th>"
        "<th class=\"num\">T tourney160</th><th>system</th><th class=\"num\">B</th><th>próg</th>"
        "<th class=\"num\">T pełny</th><th>system</th><th class=\"num\">B</th><th>próg</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>",
        note="Rozmiar = największy plik *.gguf w models/&lt;model&gt;/ (bajty / 1e9). Harness v2 używa dodatkowo rerankera "
             "bge-reranker-v2-m3 (ok. 0,64 GB); jeśli organizatorzy liczą rozmiar łącznie, doliczcie go."))
    return "".join(parts)


# --------------------------------------------------------------------------
# Strona: Modele (lista) i model (szczegoly)
# --------------------------------------------------------------------------

def known_models(idx: dict) -> set[str]:
    return {r["model"] for r in idx["rows"] if r["model"]} | {d for d in gguf_by_dir() if d}


def render_models_page(idx: dict, m: str) -> str:
    models = sorted({r["model"] for r in idx["rows"] if r["model"]})
    rows = []
    for model in models:
        t = best_for_model(idx, model, m)
        b = pick_base(idx["scopes"].get(t["scope"], []), t) if t else None
        gain = None if (t is None or b is None or b[m] is None) else (t[m] - b[m]) * 100
        gg = model_gguf(model)
        n_runs = sum(1 for r in idx["rows"] if r["model"] == model)
        ok = None if t is None or t["scope"] not in (SCOPE_FULL, SWEEP_FILE) else t[m] * 100 >= SMALL_THRESHOLD_PCT
        rows.append(
            "<tr><td>{model}</td><td>{p}</td><td class=\"num\" data-sort-value=\"{gbv}\">{gb}</td>"
            "<td class=\"small\">{tl}</td><td>{sc}</td><td class=\"num strong\" data-sort-value=\"{tv}\">{tt}</td>"
            "<td class=\"num\" data-sort-value=\"{bv}\">{bb}</td><td class=\"num\" data-sort-value=\"{gv}\">{g}</td>"
            "<td>{mini}</td><td>{ok}</td><td class=\"num\">{n}</td></tr>".format(
                model=model_link(model, m), p=esc(model_params(model)), gbv=sv(gg["size_gb"] if gg else None),
                gb=size_badge(gg["size_gb"] if gg else None), tl=esc(t["label"]) if t else "<span class=\"muted\">brak systemu T</span>",
                sc=esc(scope_title(t["scope"])) if t else "", tv=sv(t[m] if t else None), tt=esc(fmt_pct(t[m] if t else None)),
                bv=sv(b[m] if b else None), bb=esc(fmt_pct(b[m] if b else None)), gv=sv(gain), g=esc(fmt_pts(gain)),
                mini=svg_mini(t[m] if t else None, b[m] if b else None), ok=pass_badge(ok), n=n_runs))
    no_results = sorted(d for d in gguf_by_dir() if d and d not in models)
    extra = ""
    if no_results:
        extra = "<p class=\"muted small\">GGUF bez żadnych przebiegów w experiments.csv: {}.</p>".format(esc(", ".join(no_results)))
    return section(
        "Modele",
        legend_html([("t", "nasz system (T)"), ("b", "goły model (B)")]) +
        "<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr><th>Model</th><th>Param.</th><th class=\"num\">GGUF</th>"
        "<th>Najlepszy system</th><th>Na zestawie</th><th class=\"num\">T</th><th class=\"num\">B</th><th class=\"num\">Przyrost</th>"
        "<th>T / B</th><th>Próg 35%</th><th class=\"num\">Przebiegi</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>" + extra,
        note="Najlepszy benchmark modelu: pełny benchmark (673), jeśli model ma na nim komplet przebiegów; inaczej tourney160. "
             "Kliknij model, żeby zobaczyć wszystkie jego systemy, wyniki per zestaw i per typ pytań. {}".format(metric_note(m)))


def render_model_page(idx: dict, model: str, m: str) -> str:
    parts = []
    gg = model_gguf(model)
    t = best_for_model(idx, model, m)
    scope = t["scope"] if t else None
    b = pick_base(idx["scopes"].get(scope, []), t) if t else None
    gain = None if (t is None or b is None or b[m] is None) else (t[m] - b[m]) * 100
    sweep_t = best_t([s for s in idx["scopes"].get(SWEEP_FILE, []) if s["model"] == model], m)

    gguf_txt = "<code>{}</code> &middot; {}".format(esc(gg["file"]), size_badge(gg["size_gb"])) if gg else "brak pliku GGUF w models/ na tym Macu"
    if gg and gg["others"]:
        gguf_txt += "<br><span class=\"small muted\">inne pliki: {}</span>".format(
            esc(", ".join("{} ({})".format(f, fmt_gb(s / 1e9)) for f, s in gg["others"])))
    tiles = [
        tile("Najlepszy wynik (T)", esc(fmt_pct(t[m] if t else None)),
             "{} &middot; {}<br><span class=\"small\">{}</span>".format(esc(t["label"]), esc(variant_name(t["variant"])), esc(scope_title(scope)))
             if t else "brak systemu z harnessem", "", "tile-hero"),
        tile("Goły model (B)", esc(fmt_pct(b[m] if b else None)), esc(b["label"]) if b else "brak base-raw na tym zestawie"),
        tile("Przyrost", esc(fmt_pts(gain)), "T &minus; B na {}".format(esc(scope_title(scope))) if t else ""),
        tile("Mały, ale wariat", esc(fmt_pct(sweep_t[m] if sweep_t else None)),
             "{} na tourney160".format(pass_badge(sweep_t[m] * 100 >= SMALL_THRESHOLD_PCT)) if sweep_t else "brak przebiegu na tourney160"),
    ]
    parts.append(section("Model: {}".format(esc(model)),
                         "<p>{}<br>Parametry: <b>{}</b></p><div class=\"tiles\">{}</div>".format(gguf_txt, esc(model_params(model)), "".join(tiles)),
                         note=metric_note(m)))

    # wszystkie systemy na glownych zakresach
    for sc in (SCOPE_FULL, SWEEP_FILE):
        ss = [s for s in idx["scopes"].get(sc, []) if s["model"] == model and s["complete"] and s[m] is not None]
        if not ss:
            continue
        ss.sort(key=lambda s: (s["kind"] != "B", s[m]))
        chart = svg_hbars([
            {"label": s["label"], "sub": variant_name(s["variant"]), "value": s[m], "cls": "t" if s["kind"] == "T" else "b",
             "href": url("/run", file=rel_of(s["rows"][0]["run_path"]), m=m) if len(s["rows"]) == 1 and s["rows"][0]["run_path"] else "",
             "title": "{} ({}): {}".format(s["label"], variant_name(s["variant"]), fmt_pct(s[m]))}
            for s in ss])
        links = []
        if sc != SCOPE_FULL:
            tt = best_t(ss, m)
            if tt:
                bb = pick_base(idx["scopes"].get(sc, []), tt)
                cl = compare_link(bb["rows"][0] if bb else None, tt["rows"][0], m, "porównaj pytania: {} vs {}".format(
                    bb["label"] if bb else "", tt["label"]))
                if cl:
                    links.append(cl)
        parts.append(section("Systemy na: {}".format(esc(scope_title(sc))),
                             legend_html([("b", "goły model (B)"), ("t", "nasz system (T)")]) + chart +
                             ("<p class=\"small\">" + " &middot; ".join(links) + "</p>" if links else "")))

    # porownania per zestaw pelnego benchmarku
    if t is not None and scope == SCOPE_FULL and b is not None:
        bper = {r["files_key"]: r for r in b["rows"]}
        items = []
        for r in t["rows"]:
            br = bper.get(r["files_key"])
            cl = compare_link(br, r, m, r["files_key"].replace(".jsonl", ""))
            items.append(cl or "<span class=\"muted\" title=\"brak plików per pytanie na Macu\">{}</span>".format(
                esc(r["files_key"].replace(".jsonl", ""))))
        parts.append(section("Porównanie pytań B vs T: {} vs {}".format(esc(b["label"]), esc(t["label"])),
                             "<p class=\"linklist\">" + " &middot; ".join(items) + "</p>",
                             note="Dla każdego zestawu: które pytania harness naprawił, a które zepsuł. Szare = brak plików per pytanie na tym Macu."))

    parts.append(render_matrix(idx, m, model=model))

    # typy pytan
    if t is not None:
        ta = system_type_acc(t)
        ba = system_type_acc(b) if b else {}
        types = [x for x in QTYPES if x in ta or x in ba] + sorted((set(ta) | set(ba)) - set(QTYPES))
        if types:
            chart = svg_paired([
                {"label": QTYPE_NAMES.get(x, x), "t": ta.get(x), "b": ba.get(x),
                 "title": "{}: T {} · B {}".format(QTYPE_NAMES.get(x, x), fmt_pct(ta.get(x)), fmt_pct(ba.get(x)))}
                for x in types])
            trows = "".join(
                "<tr><td>{}</td><td class=\"num\">{}</td><td class=\"num\">{}</td><td class=\"num\">{}</td></tr>".format(
                    esc(QTYPE_NAMES.get(x, x)), esc(fmt_pct(ta.get(x))), esc(fmt_pct(ba.get(x))),
                    esc(fmt_pts(None if ta.get(x) is None or ba.get(x) is None else (ta[x] - ba[x]) * 100)))
                for x in types)
            parts.append(section(
                "Typy pytań: {} vs {}".format(esc(t["label"]), esc(b["label"]) if b else "–"),
                legend_html([("t", "nasz system (T)"), ("b", "goły model (B)")]) + chart +
                "<div class=\"tablewrap\"><table><thead><tr><th>Typ</th><th class=\"num\">T</th><th class=\"num\">B</th>"
                "<th class=\"num\">Przyrost</th></tr></thead><tbody>" + trows + "</tbody></table></div>",
                note="Trafność extract per typ (eval.py zapisuje per typ tylko extract), na {}.".format(esc(scope_title(scope)))))

    # wszystkie przebiegi modelu
    runs = [r for r in idx["rows"] if r["model"] == model]
    parts.append(section("Wszystkie przebiegi modelu ({})".format(len(runs)), runs_table(runs, m, "model-runs")))
    return "".join(parts)


# --------------------------------------------------------------------------
# Strona: Przebiegi (lista) i przebieg (pytania)
# --------------------------------------------------------------------------

def runs_table(rows: list[dict], m: str, table_id: str) -> str:
    body = []
    for r in rows:
        body.append(
            "<tr data-scope=\"{fk}\" data-model=\"{model_raw}\" data-kind=\"{kind}\" data-file=\"{hasf}\">"
            "<td data-sort-value=\"{ts_raw}\">{ts}</td><td>{k} {l}</td><td>{model}</td><td class=\"small\">{v}</td>"
            "<td>{sc}</td><td class=\"num\">{n}</td><td class=\"num\" data-sort-value=\"{sv_}\">{s}</td>"
            "<td class=\"num\" data-sort-value=\"{lv}\">{le}</td><td class=\"num\" data-sort-value=\"{ev}\">{e}</td>"
            "<td class=\"num\" data-sort-value=\"{pv}\">{p50}</td><td>{link}</td></tr>".format(
                fk=esc(r["files_key"]), model_raw=esc(r["model"] or ""), kind=esc(r["kind"]), hasf="1" if r["run_path"] else "0",
                ts_raw=esc(r["ts"]), ts=esc(short_ts(r["ts"])), k=kind_badge(r["kind"]), l=esc(r["label"]),
                model=model_link(r["model"], m), v=esc(variant_name(r["variant"])), sc=esc(r["files_key"].replace(".jsonl", "")),
                n=r["n"], sv_=sv(r["strict"]), s=esc(fmt_pct(r["strict"])), lv=sv(r["lenient"]), le=esc(fmt_pct(r["lenient"])),
                ev=sv(r["extract"]), e=esc(fmt_pct(r["extract"])), pv=sv(r["p50"]),
                p50=esc("{:.1f} s".format(r["p50"]).replace(".", ",") if r["p50"] is not None else "–"), link=run_link(r, m)))
    scopes = sorted({r["files_key"] for r in rows})
    models = sorted({r["model"] for r in rows if r["model"]})
    bar = filter_bar(table_id, [
        ("scope", "zestaw", [("", "wszystkie")] + [(s, s.replace(".jsonl", "")) for s in scopes]),
        ("model", "model", [("", "wszystkie")] + [(x, x) for x in models]),
        ("kind", "rodzaj", [("", "B i T"), ("T", "T: system"), ("B", "B: model bazowy")]),
        ("file", "pytania", [("", "wszystkie"), ("1", "z plikiem per pytanie")]),
    ])
    return bar + (
        "<div class=\"tablewrap\"><table class=\"sortable\" id=\"{}\"><thead><tr><th>Czas</th><th>Etykieta</th><th>Model</th>"
        "<th>Wariant</th><th>Zestaw</th><th class=\"num\">n</th><th class=\"num\">Ścisła</th><th class=\"num\">Łagodna</th>"
        "<th class=\"num\">Extract</th><th class=\"num\">p50</th><th>Per pytanie</th></tr></thead><tbody>{}</tbody></table></div>"
    ).format(esc(table_id), "".join(body))


def render_runs_page(idx: dict, m: str) -> str:
    return section(
        "Wszystkie przebiegi ({})".format(len(idx["rows"])),
        runs_table(idx["rows"], m, "all-runs") +
        "<p class=\"small\"><a href=\"/api/experiments.csv\">pobierz surowy experiments.csv</a></p>",
        note="Każdy wiersz to jedno uruchomienie devset/eval.py. „pytania” otwiera odpowiedzi modelu na każde pytanie. "
             "Filtry działają od razu; nagłówki sortują.")


def breakdown_table(records: list[dict], key_fn, title: str, names: Optional[dict] = None) -> str:
    agg: dict[str, list[int]] = {}
    for rec in records:
        k = key_fn(rec)
        a = agg.setdefault(k, [0, 0, 0])
        a[0] += 1
        a[1] += 1 if rec.get("strict") else 0
        a[2] += 1 if rec.get("lenient") else 0
    rows = "".join(
        "<tr><td>{}</td><td class=\"num\">{}</td><td class=\"num\" data-sort-value=\"{}\">{}</td><td class=\"num\" data-sort-value=\"{}\">{}</td></tr>".format(
            esc((names or {}).get(k, k)), a[0], sv(a[1] / a[0]), esc(fmt_pct(a[1] / a[0])), sv(a[2] / a[0]), esc(fmt_pct(a[2] / a[0])))
        for k, a in sorted(agg.items()))
    return (
        "<div class=\"breakdown\"><div class=\"tablewrap\"><table class=\"sortable\"><thead><tr><th>{}</th>"
        "<th class=\"num\">n</th><th class=\"num\">Ścisła</th><th class=\"num\">Łagodna</th></tr></thead><tbody>{}</tbody></table></div></div>"
    ).format(esc(title), rows)


def qcell(text: str, limit: int = 170) -> str:
    text = str(text or "")
    if len(text) <= limit and "\n" not in text.strip():
        return esc(text)
    flat = re.sub(r"\s+", " ", text).strip()
    return "<details class=\"qd\"><summary>{}</summary><div class=\"qfull\">{}</div></details>".format(
        esc(trunc(flat, limit)), esc(text).replace("\n", "<br>"))


def find_counterpart(idx: dict, row: dict, m: str) -> str:
    if not row or row["model"] is None:
        return ""
    systems = idx["scopes"].get(row["files_key"], [])
    me = make_system(row["label"], row["files_key"], [row])
    if row["kind"] == "T":
        b = pick_base(systems, me)
        return compare_link(b["rows"][0] if b else None, row, m, "porównaj z gołym modelem ({})".format(b["label"] if b else ""))
    if row["kind"] == "B":
        ts_ = [s for s in systems if s["model"] == row["model"] and s["kind"] == "T" and s["rows"][0]["run_path"] and s[m] is not None]
        if ts_:
            t = max(ts_, key=lambda s: s[m])
            return compare_link(row, t["rows"][0], m, "porównaj z najlepszym systemem ({})".format(t["label"]))
    return ""


def render_run_page(idx: dict, p: Path, m: str) -> str:
    rel = rel_of(p)
    row = next((r for r in idx["rows"] if r["run_path"] == p), None)
    records = load_run_records(p)
    parts = []
    head = []
    if row:
        head.append("<p>{k} <b>{l}</b> &middot; model {model} &middot; {v} &middot; zestaw <b>{sc}</b> &middot; {ts}</p>".format(
            k=kind_badge(row["kind"]), l=esc(row["label"]), model=model_link(row["model"], m), v=esc(variant_name(row["variant"])),
            sc=esc(row["files_key"]), ts=esc(short_ts(row["ts"]))))
    else:
        head.append("<p class=\"muted\">Tego pliku nie ma w experiments.csv.</p>")
    n = len(records)
    c_s = sum(1 for r in records if r.get("strict"))
    c_l = sum(1 for r in records if r.get("lenient"))
    c_e = sum(1 for r in records if r.get("extract"))
    errs = sum(1 for r in records if r.get("error"))
    pts = sum((r.get("points") or 0) for r in records if r.get("strict"))
    pts_max = sum((r.get("points") or 0) for r in records)
    lats = sorted(r["latency_s"] for r in records if isinstance(r.get("latency_s"), (int, float)))
    p50 = lats[len(lats) // 2] if lats else None
    tiles = [
        tile("Ścisła", esc(fmt_pct(c_s / n if n else None)), "{} / {} pytań".format(c_s, n), "", "tile-hero" if m == "strict" else ""),
        tile("Łagodna", esc(fmt_pct(c_l / n if n else None)), "{} / {} pytań".format(c_l, n), "", "tile-hero" if m == "lenient" else ""),
        tile("Extract", esc(fmt_pct(c_e / n if n else None)), "{} / {}".format(c_e, n)),
        tile("Punkty (ścisła)", "{} / {}".format(pts, pts_max), "błędy wywołań: {} &middot; p50 {}".format(
            errs, esc("{:.1f} s".format(p50).replace(".", ",") if p50 is not None else "–"))),
    ]
    cp = find_counterpart(idx, row, m) if row else ""
    cfg = ""
    if row and row["cfg"]:
        cfg = "<details><summary class=\"small\">konfiguracja harnessu</summary><pre class=\"logbox\">{}</pre></details>".format(
            esc(json.dumps(row["cfg"], ensure_ascii=False, indent=1)))
    parts.append(section(
        "Przebieg: {}".format(esc(row["label"] if row else p.name)),
        "".join(head) + "<div class=\"tiles\">" + "".join(tiles) + "</div>" +
        ("<p>{}</p>".format(cp) if cp else "") + cfg + "<p class=\"muted small\"><code>{}</code></p>".format(esc(rel))))

    if not records:
        parts.append(section("Pytania", "<p class=\"muted\">Plik jest pusty albo nieczytelny.</p>"))
        return "".join(parts)

    parts.append(section("Wynik per typ i epokę", "<div class=\"breakdowns\">" +
                         breakdown_table(records, rec_type, "Typ pytania", QTYPE_NAMES) +
                         breakdown_table(records, lambda r: str(r.get("era") or "?"), "Epoka / źródło") + "</div>"))

    body = []
    for rec in records:
        meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else {}
        st, le = bool(rec.get("strict")), bool(rec.get("lenient"))
        ok = st if m == "strict" else le
        titles = context_titles(meta)
        raw = meta.get("raw")
        raw_txt = "\n---\n".join(str(x) for x in raw) if isinstance(raw, list) else (str(raw) if raw else "")
        pred = str(rec.get("pred") if rec.get("pred") is not None else "")
        pred_html = qcell(pred, 120)
        if raw_txt and raw_txt.strip() != pred.strip():
            pred_html += "<details class=\"qd\"><summary class=\"muted small\">surowe wyjście</summary><div class=\"qfull\">{}</div></details>".format(
                esc(raw_txt).replace("\n", "<br>"))
        if rec.get("error"):
            pred_html += "<div class=\"fail small\">{}</div>".format(esc(rec.get("error")))
        ctx = ""
        if titles:
            ctx = "<details class=\"qd\"><summary class=\"small\">{} art.</summary><div class=\"qfull small\">{}</div></details>".format(
                len(titles), "<br>".join(esc(t) for t in titles))
        typ = rec_type(rec)
        body.append(
            "<tr data-type=\"{typ}\" data-ok=\"{ok}\" data-era=\"{era}\"><td class=\"small\">{id}</td><td>{typn}</td>"
            "<td class=\"small\">{era}</td><td class=\"qcell\">{q}</td><td class=\"gold\">{gold}</td><td class=\"qcell\">{pred}</td>"
            "<td class=\"c\">{ms}</td><td class=\"c\">{ml}</td><td>{ctx}</td><td class=\"num\" data-sort-value=\"{latv}\">{lat}</td></tr>".format(
                typ=esc(typ), ok="1" if ok else "0", era=esc(rec.get("era") or ""), id=esc(rec.get("id")), typn=esc(typ),
                q=qcell(rec.get("question") or ""), gold=esc(rec.get("gold")), pred=pred_html, ms=mark(st), ml=mark(le), ctx=ctx,
                latv=sv(rec.get("latency_s") if isinstance(rec.get("latency_s"), (int, float)) else None),
                lat=esc("{:.1f}".format(rec["latency_s"]).replace(".", ",") if isinstance(rec.get("latency_s"), (int, float)) else "")))
    types = sorted({rec_type(r) for r in records})
    eras = sorted({str(r.get("era") or "") for r in records})
    bar = filter_bar("run-q", [
        ("ok", "wynik ({})".format(METRICS[m]), [("", "wszystkie"), ("0", "tylko błędne"), ("1", "tylko poprawne")]),
        ("type", "typ", [("", "wszystkie")] + [(t, QTYPE_NAMES.get(t, t)) for t in types]),
        ("era", "epoka", [("", "wszystkie")] + [(e, e) for e in eras if e]),
    ])
    parts.append(section(
        "Pytania i odpowiedzi ({})".format(n),
        bar + "<div class=\"tablewrap\"><table class=\"sortable qtable\" id=\"run-q\"><thead><tr><th>ID</th><th>Typ</th><th>Epoka</th>"
        "<th>Pytanie</th><th>Wzorzec</th><th>Odpowiedź modelu</th><th>Ścisła</th><th>Łagodna</th><th>Kontekst</th><th class=\"num\">s</th>"
        "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>",
        note="Kliknij pytanie, żeby rozwinąć pełną treść; „kontekst” to tytuły artykułów Wikipedii podane modelowi przez harness."))
    return "".join(parts)


def render_compare_page(idx: dict, bp: Path, tp: Path, m: str) -> str:
    b_recs = {str(r.get("id")): r for r in load_run_records(bp)}
    t_recs = {str(r.get("id")): r for r in load_run_records(tp)}
    b_row = next((r for r in idx["rows"] if r["run_path"] == bp), None)
    t_row = next((r for r in idx["rows"] if r["run_path"] == tp), None)
    ids = [i for i in t_recs if i in b_recs]
    cats = {"fixed": 0, "broken": 0, "both_ok": 0, "both_bad": 0}
    per_type: dict[str, list[int]] = {}
    body = []
    for qid in ids:
        br, tr = b_recs[qid], t_recs[qid]
        bo, to = bool(br.get(m)), bool(tr.get(m))
        cat = "fixed" if (to and not bo) else "broken" if (bo and not to) else "both_ok" if to else "both_bad"
        cats[cat] += 1
        typ = rec_type(tr)
        pt = per_type.setdefault(typ, [0, 0, 0])
        pt[0] += 1
        pt[1] += 1 if cat == "fixed" else 0
        pt[2] += 1 if cat == "broken" else 0
        badge = {"fixed": "<span class=\"cat cat-fixed\">&#10003; naprawione</span>",
                 "broken": "<span class=\"cat cat-broken\">&#10007; zepsute</span>",
                 "both_ok": "<span class=\"cat\">oba dobrze</span>",
                 "both_bad": "<span class=\"cat\">oba źle</span>"}[cat]
        group = "changed" if cat in ("fixed", "broken") else "same"
        body.append(
            "<tr data-cat=\"{cat} {grp}\" data-type=\"{typ}\"><td class=\"small\">{id}</td><td>{typn}</td><td class=\"qcell\">{q}</td>"
            "<td class=\"gold\">{gold}</td><td class=\"qcell\">{bp} {bm}</td><td class=\"qcell\">{tp} {tm}</td><td>{badge}</td></tr>".format(
                cat=cat, grp=group, typ=esc(typ), id=esc(qid), typn=esc(typ), q=qcell(tr.get("question") or ""),
                gold=esc(tr.get("gold")), bp=qcell(str(br.get("pred") or ""), 100), bm=mark(bo),
                tp=qcell(str(tr.get("pred") or ""), 100), tm=mark(to), badge=badge))
    n = len(ids)
    net = cats["fixed"] - cats["broken"]
    tiles = [
        tile("Naprawione przez harness", str(cats["fixed"]), "B &#10007; &rarr; T &#10003;", "", "tile-hero"),
        tile("Zepsute przez harness", str(cats["broken"]), "B &#10003; &rarr; T &#10007;"),
        tile("Bez zmian", "{} / {}".format(cats["both_ok"], cats["both_bad"]), "oba dobrze / oba źle"),
        tile("Bilans", "{:+d}".format(net), "= {} na {} wspólnych pytaniach".format(esc(fmt_pts(net / n * 100 if n else None)), n)),
    ]
    trows = "".join(
        "<tr><td>{}</td><td class=\"num\">{}</td><td class=\"num\">{}</td><td class=\"num\">{}</td><td class=\"num\">{:+d}</td></tr>".format(
            esc(QTYPE_NAMES.get(k, k)), a[0], a[1], a[2], a[1] - a[2]) for k, a in sorted(per_type.items()))
    head = "<p>B: {} &middot; T: {} &middot; ocena <b>{}</b></p>".format(
        run_link(b_row, m, b_row["label"]) if b_row else esc(bp.name), run_link(t_row, m, t_row["label"]) if t_row else esc(tp.name),
        esc(METRICS[m]))
    miss = len(set(b_recs) ^ set(t_recs))
    if miss:
        head += "<p class=\"muted small\">{} pytań występuje tylko w jednym z plików (pominięte).</p>".format(miss)
    bar = filter_bar("cmp-q", [
        ("cat", "zmiana", [("changed", "tylko zmienione"), ("fixed", "naprawione"), ("broken", "zepsute"), ("", "wszystkie"),
                           ("both_bad", "oba źle"), ("both_ok", "oba dobrze")]),
        ("type", "typ", [("", "wszystkie")] + [(t, QTYPE_NAMES.get(t, t)) for t in sorted(per_type)]),
    ])
    return (
        section("Porównanie pytań: goły model vs nasz system", head + "<div class=\"tiles\">" + "".join(tiles) + "</div>" +
                "<div class=\"tablewrap\"><table><thead><tr><th>Typ</th><th class=\"num\">n</th><th class=\"num\">naprawione</th>"
                "<th class=\"num\">zepsute</th><th class=\"num\">bilans</th></tr></thead><tbody>" + trows + "</tbody></table></div>",
                note="Bilans naprawionych i zepsutych pytań to dokładnie przyrost T &minus; B na tym zestawie.")
        + section("Pytania", bar + "<div class=\"tablewrap\"><table class=\"sortable qtable\" id=\"cmp-q\"><thead><tr><th>ID</th><th>Typ</th>"
                  "<th>Pytanie</th><th>Wzorzec</th><th>B: goły model</th><th>T: nasz system</th><th>Zmiana</th></tr></thead><tbody>"
                  + "".join(body) + "</tbody></table></div>")
    )


# --------------------------------------------------------------------------
# Strona: Sweepy (devset/sweep_results*.md jako tabele)
# --------------------------------------------------------------------------

def sweep_files() -> list[str]:
    return sorted(p.name for p in DEVSET_DIR.glob("sweep_results*.md")) if DEVSET_DIR.exists() else []


def md_inline(text: str) -> str:
    s = esc(text)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def render_markdown(text: str) -> str:
    out: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.strip().startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            tables = md_tables("\n".join(block))
            for tb in tables:
                head, body = tb[0], tb[1:]
                rows = []
                for r in body:
                    cells = []
                    for c in r:
                        v = parse_float(c.replace("%", "").replace(",", "."))
                        cells.append("<td class=\"num\" data-sort-value=\"{}\">{}</td>".format(v, md_inline(c)) if v is not None
                                     else "<td>{}</td>".format(md_inline(c)))
                    rows.append("<tr>" + "".join(cells) + "</tr>")
                out.append("<div class=\"tablewrap\"><table class=\"sortable\"><thead><tr>" +
                           "".join("<th>{}</th>".format(md_inline(h)) for h in head) + "</tr></thead><tbody>" + "".join(rows) +
                           "</tbody></table></div>")
            continue
        mh = re.match(r"^(#{1,4})\s+(.*)$", line)
        if mh:
            out.append("<h3 class=\"subhead\">{}</h3>".format(md_inline(mh.group(2))))
        elif re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append("<li>{}</li>".format(md_inline(re.sub(r"^\s*[-*]\s+", "", lines[i]))))
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif line.strip():
            out.append("<p class=\"small\">{}</p>".format(md_inline(line)))
        i += 1
    return "".join(out)


def render_sweep_page(f: str, m: str) -> str:
    files = sweep_files()
    if not files:
        return section("Sweepy", "<p class=\"muted\">Brak devset/sweep_results*.md.</p>")
    if f not in files:
        f = "sweep_results_mac.md" if "sweep_results_mac.md" in files else files[0]
    segs = "<div class=\"segs\"><span class=\"seg-label\">Plik</span>" + "".join(
        "<a class=\"seg{}\" href=\"{}\">{}</a>".format(" active" if x == f else "", esc(url("/sweep", f=x, m=m)), esc(x.replace(".md", "")))
        for x in files) + "</div>"
    try:
        text = (DEVSET_DIR / f).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    return section("Sweepy modeli", segs, note="Raporty sweepów generowane przez devset/sweep*.py; tabele można sortować.") + section(
        esc(f), render_markdown(text))


# --------------------------------------------------------------------------
# Sprawdz pytanie (proxy do harness / llama-server)
# --------------------------------------------------------------------------

def probe_harness_instance(port: int) -> dict:
    """GET /health na lokalnej instancji harnessu (tylko odczyt, tylko 127.0.0.1)."""
    url_ = "http://127.0.0.1:{}/health".format(port)
    try:
        resp = httpx.get(url_, timeout=HARNESS_PROBE_TIMEOUT)
        if resp.status_code != 200:
            return {"port": port, "ok": False}
        data = resp.json()
        cfg = data.get("config") if isinstance(data.get("config"), dict) else {}
        llm_model = None
        if isinstance(cfg, dict):
            llm_model = cfg.get("llm_model")
        if not llm_model:
            llm_model = data.get("llm_model")
        return {
            "port": port,
            "ok": True,
            "llm_model": llm_model,
            "use_kb": cfg.get("use_kb") if isinstance(cfg, dict) else None,
            "kb_available": (data.get("kb") or {}).get("available") if isinstance(data.get("kb"), dict) else None,
        }
    except Exception:
        return {"port": port, "ok": False}


def probe_harness_instances() -> list[dict]:
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(HARNESS_PROBE_PORTS)) as ex:
        futures = {ex.submit(probe_harness_instance, p): p for p in HARNESS_PROBE_PORTS}
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda r: r["port"])
    return results


@app.get("/api/harness_instances")
def api_harness_instances() -> JSONResponse:
    return JSONResponse({"instances": probe_harness_instances(), "default_port": DEFAULT_HARNESS_PORT})


@app.get("/api/sample")
def api_sample(file: str) -> JSONResponse:
    """Losowe pytanie z devset/<file> (tylko pliki z listy devset/*.jsonl)."""
    if file not in devset_names():
        return JSONResponse({"error": "nieznany plik"}, status_code=404)
    items = [it for it in load_devset_file(DEVSET_DIR / file) if it.get("question")]
    if not items:
        return JSONResponse({"error": "pusty plik"}, status_code=404)
    it = random.choice(items)
    return JSONResponse({"id": it.get("id"), "type": it.get("type"), "era": it.get("era"),
                         "question": it.get("question"), "answer": it.get("answer"), "accept": it.get("accept")})


@app.post("/api/ask")
async def api_ask(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "niepoprawny JSON"}, status_code=400)
    question = str(payload.get("question", "")).strip()
    if not question:
        return JSONResponse({"error": "puste pytanie"}, status_code=400)
    if len(question) > 4000:
        question = question[:4000]

    port = payload.get("port", DEFAULT_HARNESS_PORT)
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = DEFAULT_HARNESS_PORT
    if port not in HARNESS_PROBE_PORTS:
        port = DEFAULT_HARNESS_PORT

    async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
        harness_task = asyncio.create_task(_ask_harness(client, question, port))
        base_task = asyncio.create_task(_ask_base(client, question, port))
        harness_result, base_result = await asyncio.gather(harness_task, base_task)

    return JSONResponse({"harness": harness_result, "base": base_result, "port": port})


async def _ask_harness(client: httpx.AsyncClient, question: str, port: int) -> dict:
    harness_base = "http://127.0.0.1:{}".format(port)
    t0 = time.monotonic()
    try:
        resp = await client.post(harness_base + "/answer", json={"question": question})
        latency = time.monotonic() - t0
        if resp.status_code != 200:
            return {"ok": False, "error": "HTTP {}: {}".format(resp.status_code, resp.text[:300]), "latency_s": latency, "port": port}
        data = resp.json()
        return {
            "ok": True,
            "answer": data.get("answer"),
            "latency_s": latency,
            "titles": [c.get("title") for c in (data.get("contexts") or []) if isinstance(c, dict) and c.get("title")],
            "qtype": data.get("qtype"),
            "port": port,
        }
    except httpx.TimeoutException:
        return {"ok": False, "error": "przekroczono limit {}s (harness)".format(int(PROXY_TIMEOUT)), "latency_s": time.monotonic() - t0, "port": port}
    except httpx.ConnectError:
        return {"ok": False, "error": "harness nie odpowiada (połączenie odrzucone) - czy działa na :{}?".format(port), "latency_s": time.monotonic() - t0, "port": port}
    except Exception as e:
        return {"ok": False, "error": "błąd: {}".format(type(e).__name__), "latency_s": time.monotonic() - t0, "port": port}


async def _ask_base(client: httpx.AsyncClient, question: str, port: int) -> dict:
    harness_base = "http://127.0.0.1:{}".format(port)
    body = {"model": "base", "messages": [{"role": "user", "content": question}], "stream": False, **BASE_ASK_PARAMS}
    t0 = time.monotonic()
    try:
        resp = await client.post(harness_base + "/base/v1/chat/completions", json=body)
        latency = time.monotonic() - t0
        if resp.status_code == 200:
            data = resp.json()
            content = _extract_chat_content(data)
            return {"ok": True, "answer": content, "latency_s": latency, "source": "harness /base (port {})".format(port), "port": port}
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError):
        pass
    except Exception:
        pass

    # fallback: bezposrednio do llama-server (nie zna doboru portu harnessu - zawsze :18080)
    body2 = {**body, "model": "bielik-11b-v3"}
    t1 = time.monotonic()
    try:
        resp2 = await client.post(LLAMA_BASE + "/v1/chat/completions", json=body2)
        latency2 = time.monotonic() - t1
        if resp2.status_code == 200:
            data2 = resp2.json()
            content2 = _extract_chat_content(data2)
            return {"ok": True, "answer": content2, "latency_s": latency2, "source": "llama-server (fallback, :18080)", "port": port}
        return {
            "ok": False,
            "error": "harness /base (port {}) i llama-server nie odpowiedziały poprawnie (HTTP {})".format(port, resp2.status_code),
            "latency_s": latency2,
            "port": port,
        }
    except httpx.TimeoutException:
        return {"ok": False, "error": "przekroczono limit {}s (base/llama-server)".format(int(PROXY_TIMEOUT)), "latency_s": time.monotonic() - t1, "port": port}
    except httpx.ConnectError:
        return {"ok": False, "error": "ani harness /base (port {}), ani llama-server (:18080) nie odpowiadają".format(port), "latency_s": time.monotonic() - t1, "port": port}
    except Exception as e:
        return {"ok": False, "error": "błąd: {}".format(type(e).__name__), "latency_s": time.monotonic() - t1, "port": port}


def _extract_chat_content(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return json.dumps(data, ensure_ascii=False)[:2000]


def render_ask_page() -> str:
    options = "".join("<option value=\"{n}\"{sel}>{n}</option>".format(n=esc(n), sel=" selected" if n == SWEEP_FILE else "")
                      for n in devset_names())
    return section(
        "Sprawdź pytanie",
        "<div class=\"ask-controls\">"
        "<label for=\"harness-port\">Instancja harnessu:</label>"
        "<select id=\"harness-port\"><option value=\"18000\">port 18000 (wykrywanie...)</option></select>"
        "<button type=\"button\" class=\"btn-small\" onclick=\"refreshHarnessInstances()\">odśwież listę</button>"
        "<span id=\"harness-select-note\" class=\"muted small\"></span>"
        "</div>"
        "<div class=\"ask-controls\"><label for=\"sample-file\">Pytanie z zestawu:</label>"
        "<select id=\"sample-file\">{opts}</select>"
        "<button type=\"button\" class=\"btn-small\" onclick=\"sampleQuestion()\">losuj pytanie</button></div>"
        "<textarea id=\"question\" placeholder=\"Wpisz pytanie maturalne albo wylosuj je z zestawu...\"></textarea>"
        "<div id=\"sample-gold\" class=\"gold-box\" hidden></div>"
        "<div><button id=\"ask-btn\" type=\"button\">Zapytaj</button></div>"
        "<div class=\"ask-grid\">"
        "<div class=\"ask-col\"><h4>Harness (RAG, /answer)</h4>"
        "<div id=\"ask-harness-model\" class=\"muted small model-tag\">wybierz instancję i zapytaj</div>"
        "<div id=\"ask-harness\" class=\"muted\">brak zapytania</div></div>"
        "<div class=\"ask-col\"><h4>Model bazowy (bez harnessu)</h4>"
        "<div id=\"ask-base-model\" class=\"muted small model-tag\">wybierz instancję i zapytaj</div>"
        "<div id=\"ask-base\" class=\"muted\">brak zapytania</div></div>"
        "</div>"
        "<p class=\"muted small\">Limit oczekiwania: 120 s na każde źródło. Model bazowy dostaje pytanie jak w benchmarku "
        "(jedna wiadomość użytkownika, temperature=0, max_tokens=512), więc odpowiedź jest powtarzalna. Instancje "
        "harnessu wykrywane przez GET /health na 127.0.0.1, porty 18000-18010 (Mac); każda pokazuje swój llm_model.</p>".format(opts=options),
    )


# --------------------------------------------------------------------------
# Logi
# --------------------------------------------------------------------------

def list_log_names() -> list[str]:
    if not LOGS_DIR.exists():
        return []
    return sorted(p.name for p in LOGS_DIR.glob("*.log"))


@app.get("/api/logs")
def api_logs(name: str) -> PlainTextResponse:
    names = list_log_names()
    if name not in names:
        return PlainTextResponse("nieznany plik logu", status_code=404)
    p = LOGS_DIR / name
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
    except OSError:
        return PlainTextResponse("nie udało się odczytać pliku", status_code=500)
    return PlainTextResponse("\n".join(lines))


def render_logs_html() -> str:
    names = list_log_names()
    if not names:
        return "<p class=\"muted\">Brak plików logs/*.log.</p>"
    options = "".join("<option value=\"{n}\">{n}</option>".format(n=esc(n)) for n in names)
    return (
        "<div class=\"logs-controls\">"
        "<select id=\"log-select\">{options}</select> "
        "<button type=\"button\" class=\"btn-small\" onclick=\"loadLog()\">Pokaż (ost. 60 linii)</button>"
        "</div><pre id=\"log-content\" class=\"logbox\">wybierz log i kliknij Pokaż...</pre>"
    ).format(options=options)


# --------------------------------------------------------------------------
# API danych
# --------------------------------------------------------------------------

@app.get("/api/run")
def api_run(file: str) -> JSONResponse:
    p = resolve_run_file(file)
    if p is None:
        return JSONResponse({"error": "nieznany lub niedozwolony plik"}, status_code=404)
    records = []
    for rec in load_run_records(p):
        meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else {}
        correct = rec.get("lenient")
        if correct is None:
            correct = rec.get("strict")
        records.append(
            {
                "id": rec.get("id"),
                "type": rec_type(rec),
                "era": rec.get("era"),
                "question": rec.get("question"),
                "gold": rec.get("gold"),
                "pred": rec.get("pred"),
                "correct": bool(correct) if correct is not None else None,
                "strict": rec.get("strict"),
                "extract": rec.get("extract"),
                "lenient": rec.get("lenient"),
                "latency_s": rec.get("latency_s"),
                "error": rec.get("error"),
                "titles": context_titles(meta),
            }
        )
    return JSONResponse({"file": file, "records": records})


@app.get("/api/version")
def api_version() -> JSONResponse:
    return JSONResponse({"version": data_version()})


@app.get("/api/experiments.csv")
def api_experiments_csv() -> Response:
    try:
        data = EXPERIMENTS_CSV.read_bytes()
    except OSError:
        return PlainTextResponse("brak experiments.csv", status_code=404)
    return Response(content=data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=experiments.csv"})


@app.get("/api/refresh")
def api_refresh() -> JSONResponse:
    return JSONResponse(
        {
            "system_html": render_system_html(),
            "models_html": render_models_html(),
            "kb_html": render_kb_html(),
        }
    )


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "base_dir": str(BASE_DIR)})


# --------------------------------------------------------------------------
# CSS / JS
# --------------------------------------------------------------------------

CSS = """
:root {
  --bg: #f5f6f8; --fg: #1a1d23; --card: #ffffff; --border: #dfe3e8;
  --accent: #2454ff; --accent-2: #16a34a; --bad: #dc2626; --muted: #6b7280;
  --code-bg: #f0f1f4;
  --series-t: #2a78d6; --series-b: #eb6834; --grid: #e1e0d9; --axis: #c3c2b7;
  --ink-2: #52514e; --ink-3: #898781; --good-text: #006300; --crit: #d03b3b; --hover: rgba(127,127,127,0.10);
  --warn-bg: #fff6e0; --partial: #b45309;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #14161a; --fg: #e6e8eb; --card: #1d2026; --border: #2c3038;
    --accent: #6f9bff; --accent-2: #4ade80; --bad: #f87171; --muted: #9aa1ab;
    --code-bg: #23262d;
    --series-t: #3987e5; --series-b: #d95926; --grid: #2c2c2a; --axis: #383835;
    --ink-2: #c3c2b7; --ink-3: #898781; --good-text: #0ca30c; --crit: #e66767; --hover: rgba(255,255,255,0.06);
    --warn-bg: #3a2f14; --partial: #f2b84b; }
}
* { box-sizing: border-box; }
body { margin:0; padding:0; background:var(--bg); color:var(--fg);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 15px; line-height: 1.45; }
a { color: var(--accent); }
header { padding: 12px 16px 0 16px; border-bottom: 1px solid var(--border); position: sticky; top:0;
  background: var(--bg); z-index: 5; }
.header-row { display:flex; align-items:center; gap:12px; flex-wrap:wrap; justify-content:space-between; }
header h1 { margin: 0; font-size: 1.15rem; }
header .sub { color: var(--muted); font-size: 0.8rem; }
nav.tabs { display:flex; gap:2px; overflow-x:auto; margin-top:8px; }
nav.tabs a { padding: 7px 11px; color: var(--fg); text-decoration:none; white-space:nowrap; font-size:0.9rem;
  border-bottom: 2px solid transparent; }
nav.tabs a:hover { background: var(--hover); }
nav.tabs a.active { border-bottom-color: var(--accent); font-weight:600; }
.banner { background: var(--warn-bg); border:1px solid var(--border); border-radius:8px; padding:8px 12px; margin: 10px 0; }
main { max-width: 1240px; margin: 0 auto; padding: 14px 16px 60px 16px; }
section.card { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 16px; margin-bottom: 16px; }
section.card h2 { margin-top: 0; margin-bottom: 6px; font-size: 1.05rem; display:flex; align-items:center; gap:8px; }
.intro { margin-top: 0; }
.muted { color: var(--muted); }
.small { font-size: 0.82rem; }
.strong { font-weight: 650; }
.warn { background: var(--warn-bg); padding: 4px 8px; border-radius: 6px; }
ul.plain { padding-left: 18px; margin: 4px 0; }
ul.plain li { margin: 3px 0; }
.tablewrap { overflow-x: auto; max-width: 100%; }
table { border-collapse: collapse; width: 100%; font-size: 0.87rem; }
th, td { border-bottom: 1px solid var(--border); padding: 5px 8px; text-align: left; white-space: nowrap; vertical-align: top; }
td.qcell, td.cellwrap { white-space: normal; min-width: 240px; max-width: 460px; }
td.gold { white-space: normal; font-weight: 600; max-width: 180px; }
td.c { text-align:center; }
td.cmdcell { white-space: normal; word-break: break-all; max-width: 420px; font-size: 0.78rem; }
th { position: sticky; top: 0; background: var(--card); cursor: pointer; user-select: none; }
th.sort-asc::after { content: " \\25B2"; }
th.sort-desc::after { content: " \\25BC"; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
td.best { font-weight: 700; }
table.matrix td a { text-decoration: none; }
code { background: var(--code-bg); padding: 1px 4px; border-radius: 4px; font-size: 0.85em; }
.badge { display:inline-block; padding: 1px 7px; border-radius: 999px; font-size: 0.75rem; font-weight:600; }
.badge-ok { background: rgba(22,163,74,0.15); color: var(--accent-2); }
.badge-bad { background: rgba(220,38,38,0.15); color: var(--bad); }
.status { font-size: 0.8rem; font-weight: 600; white-space: nowrap; }
.status-good { color: var(--good-text); }
.status-crit { color: var(--crit); }
.ok { color: var(--good-text); font-weight: 700; }
.fail { color: var(--crit); font-weight: 700; }
.kind { display:inline-block; min-width: 18px; text-align:center; border-radius: 4px; font-size: 0.72rem; font-weight: 700;
  padding: 0 4px; border: 1px solid var(--border); color: var(--ink-2); }
.kind-t { border-color: var(--series-t); }
.kind-b { border-color: var(--series-b); }
.cat { font-size: 0.8rem; white-space: nowrap; color: var(--muted); }
.cat-fixed { color: var(--good-text); font-weight: 600; }
.cat-broken { color: var(--crit); font-weight: 600; }
.tiles { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 8px 0 14px 0; }
.tile { background: var(--card); border:1px solid var(--border); border-radius:10px; padding: 12px 14px; position: relative;
  min-width: 0; overflow-wrap: anywhere; }
.nofile { color: var(--ink-2); border-bottom: 1px dotted var(--ink-3); }
section.card .tile { background: var(--code-bg); border-color: transparent; }
.tile-hero { border-color: var(--series-t) !important; }
.tile-label { font-size: 0.74rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
.tile-value { font-size: 1.75rem; font-weight: 650; margin: 2px 0 4px 0; line-height: 1.2; word-break: break-word; }
.tile-sub { font-size: 0.85rem; color: var(--ink-2); }
.tile-link { display:inline-block; margin-top: 6px; font-size: 0.82rem; text-decoration: none; }
.segs { display:flex; flex-wrap: wrap; gap: 4px; align-items: center; margin: 6px 0; }
.seg-label { font-size: 0.8rem; color: var(--muted); margin-right: 6px; min-width: 70px; }
a.seg { font-size: 0.84rem; padding: 3px 9px; border:1px solid var(--border); border-radius: 999px; text-decoration:none; color: var(--fg); }
a.seg.active { background: var(--fg); color: var(--bg); border-color: var(--fg); }
.metric-toggle { font-size: 0.82rem; color: var(--muted); display:flex; align-items:center; gap: 4px; }
.legend { display:flex; gap: 14px; font-size: 0.82rem; color: var(--ink-2); margin: 4px 0 2px 0; }
.legend-item { display:inline-flex; align-items:center; gap: 6px; }
.key { display:inline-block; width: 10px; height: 10px; border-radius: 50%; }
.key-t { background: var(--series-t); }
.key-b { background: var(--series-b); }
.chartwrap { overflow-x: auto; max-width: 100%; margin: 4px 0 8px 0; }
svg.chart { display:block; }
svg.chart .grid { stroke: var(--grid); stroke-width: 1; }
svg.chart .tick { font-size: 10px; fill: var(--ink-3); font-variant-numeric: tabular-nums; }
svg.chart .lbl { font-size: 11.5px; fill: var(--fg); }
svg.chart .lbl-sub { font-size: 10px; fill: var(--ink-3); }
svg.chart .val { font-size: 11px; fill: var(--ink-2); font-variant-numeric: tabular-nums; }
svg.chart .val-strong { font-weight: 700; fill: var(--fg); }
svg.chart .bar-t, svg.mini .bar-t { fill: var(--series-t); }
svg.chart .bar-b, svg.mini .bar-b { fill: var(--series-b); }
svg.chart .dot-t { fill: var(--series-t); stroke: var(--card); stroke-width: 2; }
svg.chart .dot-b { fill: var(--series-b); stroke: var(--card); stroke-width: 2; }
svg.chart .db-line { stroke: var(--axis); stroke-width: 2; stroke-linecap: round; }
svg.chart .thr { stroke: var(--fg); stroke-width: 1.5; }
svg.chart .thr-lbl { font-size: 10.5px; fill: var(--fg); font-weight: 600; }
svg.chart .hit { fill: transparent; }
svg.chart .mark:hover .hit { fill: var(--hover); }
svg.mini { vertical-align: middle; }
.filters { display:flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 6px 0 10px 0; font-size: 0.85rem; }
.filters select, .filters input { font: inherit; padding: 3px 6px; border-radius: 6px; border: 1px solid var(--border);
  background: var(--card); color: var(--fg); }
.breakdowns { display:flex; flex-wrap: wrap; gap: 20px; }
.breakdown { flex: 1 1 320px; }
details.qd summary { cursor: pointer; }
.qfull { margin-top: 4px; padding: 6px 8px; background: var(--code-bg); border-radius: 6px; }
.linklist a { margin-right: 2px; }
.kpis { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }
.kpi { flex:1 1 200px; background: var(--code-bg); border-radius:8px; padding:8px 12px; }
.kpi-label { font-size:0.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.04em; }
.kpi-value { font-size:0.95rem; margin-top:2px; }
.logbox { background: var(--code-bg); padding: 10px; border-radius: 8px; overflow-x:auto;
  max-height: 340px; overflow-y:auto; font-size: 0.8rem; white-space: pre-wrap; word-break: break-word; }
details.devset-file { margin-bottom: 10px; border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; }
details.devset-file summary { cursor: pointer; }
h3.subhead { font-size: 0.95rem; margin: 14px 0 6px 0; }
.btn-small { font-size: 0.78rem; padding: 3px 8px; border-radius: 6px; border: 1px solid var(--border);
  background: var(--code-bg); color: var(--fg); cursor:pointer; }
.ask-controls { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:8px; font-size:0.88rem; }
.ask-grid { display:flex; gap:14px; flex-wrap:wrap; margin-top:10px; }
.ask-col { flex: 1 1 320px; background: var(--code-bg); border-radius:8px; padding:10px 12px; min-height: 120px; }
.ask-col h4 { margin: 0 0 6px 0; }
.ask-col .model-tag { margin-bottom: 6px; }
.gold-box { margin-top: 6px; padding: 6px 10px; border-radius: 8px; background: var(--code-bg); font-size: 0.88rem; }
textarea#question { width:100%; min-height: 110px; padding:8px; border-radius:8px; border:1px solid var(--border);
  background: var(--card); color: var(--fg); font-family: inherit; font-size: 0.95rem; }
button#ask-btn { margin-top:8px; padding: 8px 16px; border-radius: 8px; border:none; background: var(--accent);
  color:#fff; font-weight:600; cursor:pointer; }
button#ask-btn:disabled { opacity: 0.6; cursor: default; }
.links a { color: var(--accent); text-decoration:none; margin-right: 14px; }
.links a:hover { text-decoration: underline; }
.errbox { color: var(--bad); }
footer { max-width: 1240px; margin: 0 auto; padding: 0 16px 30px 16px; font-size: 0.82rem; }
@media (max-width: 640px) {
  body { font-size: 14px; }
  .ask-grid { flex-direction: column; }
  .tile-value { font-size: 1.45rem; }
}
/* ==== Pełna matura (sekcja dodana przez agenta) ==== */
.badge.pt-full { background: rgba(22,163,74,0.15); color: var(--accent-2); }
.badge.pt-zero { background: rgba(220,38,38,0.15); color: var(--bad); }
.badge.pt-part { background: rgba(180,83,9,0.18); color: var(--partial); }
.badge.pt-pending { background: var(--warn-bg); color: var(--muted); }
.essaybox { background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 12px 14px; margin-top: 12px; }
.essaybox h3 { margin-top: 0; }
"""

JS = r"""
function esc(s) {
  const d = document.createElement('div');
  d.textContent = (s === null || s === undefined) ? '' : String(s);
  return d.innerHTML;
}

function sortTableByColumn(table, idx, asc) {
  var tbody = table.querySelector('tbody');
  if (!tbody) return;
  var ths = table.querySelectorAll('th');
  var rows = Array.prototype.slice.call(tbody.querySelectorAll(':scope > tr'));
  ths.forEach(function (t) { t.classList.remove('sort-asc', 'sort-desc'); });
  if (ths[idx]) ths[idx].classList.add(asc ? 'sort-asc' : 'sort-desc');
  rows.sort(function (a, b) {
    var ca = a.children[idx], cb = b.children[idx];
    var va = ca ? (ca.getAttribute('data-sort-value') || ca.textContent.trim()) : '';
    var vb = cb ? (cb.getAttribute('data-sort-value') || cb.textContent.trim()) : '';
    var na = parseFloat(va), nb = parseFloat(vb);
    var cmp;
    if (!isNaN(na) && !isNaN(nb)) {
      cmp = na - nb;
    } else {
      cmp = va.localeCompare(vb, 'pl');
    }
    return asc ? cmp : -cmp;
  });
  rows.forEach(function (r) { tbody.appendChild(r); });
}

function initSortableTables(root) {
  (root || document).querySelectorAll('table.sortable').forEach(function (table) {
    if (table.dataset.sortBound) return;
    table.dataset.sortBound = '1';
    var ths = table.querySelectorAll('th');
    ths.forEach(function (th, idx) {
      th.addEventListener('click', function () {
        var asc = !th.classList.contains('sort-asc');
        sortTableByColumn(table, idx, asc);
      });
    });
  });
}

// -- filtry tabel po stronie klienta: <div class="filters" data-target="id"> + atrybuty data-<klucz> na wierszach --
function initFilters() {
  document.querySelectorAll('.filters[data-target]').forEach(function (bar) {
    var table = document.getElementById(bar.getAttribute('data-target'));
    if (!table) return;
    var counter = bar.querySelector('.filter-count');
    function apply() {
      var sels = bar.querySelectorAll('select[data-key]');
      var qEl = bar.querySelector('input[data-key="q"]');
      var q = qEl ? qEl.value.trim().toLowerCase() : '';
      var rows = table.querySelectorAll('tbody > tr');
      var shown = 0;
      rows.forEach(function (tr) {
        var ok = true;
        sels.forEach(function (s) {
          if (!ok || !s.value) return;
          var val = ' ' + (tr.getAttribute('data-' + s.getAttribute('data-key')) || '') + ' ';
          if (val.indexOf(' ' + s.value + ' ') < 0) ok = false;
        });
        if (ok && q && tr.textContent.toLowerCase().indexOf(q) < 0) ok = false;
        tr.style.display = ok ? '' : 'none';
        if (ok) shown++;
      });
      if (counter) counter.textContent = 'widoczne: ' + shown + ' / ' + rows.length;
    }
    bar.querySelectorAll('select, input').forEach(function (el) {
      el.addEventListener('change', apply);
      el.addEventListener('input', apply);
    });
    apply();
  });
}

// -- zachowanie stanu sortowania przy auto-odswiezaniu (zakladka System) --

function captureSortState(bodyEl) {
  var state = [];
  if (!bodyEl) return state;
  bodyEl.querySelectorAll('table.sortable').forEach(function (table, ti) {
    var ths = table.querySelectorAll('th');
    for (var i = 0; i < ths.length; i++) {
      if (ths[i].classList.contains('sort-asc') || ths[i].classList.contains('sort-desc')) {
        state[ti] = { col: i, asc: ths[i].classList.contains('sort-asc') };
        break;
      }
    }
  });
  return state;
}

function applySortState(bodyEl, state) {
  if (!bodyEl || !state) return;
  bodyEl.querySelectorAll('table.sortable').forEach(function (table, ti) {
    var s = state[ti];
    if (!s) return;
    sortTableByColumn(table, s.col, s.asc);
  });
}

function loadLog() {
  var sel = document.getElementById('log-select');
  var out = document.getElementById('log-content');
  if (!sel || !out) return;
  out.textContent = 'wczytywanie...';
  fetch('/api/logs?name=' + encodeURIComponent(sel.value))
    .then(function (r) { return r.text(); })
    .then(function (t) { out.textContent = t; })
    .catch(function () { out.textContent = 'błąd sieci'; });
}

var harnessInstances = {};

function renderHarnessSelect(list) {
  var sel = document.getElementById('harness-port');
  var note = document.getElementById('harness-select-note');
  if (!sel) return;
  var prevVal = sel.value;
  harnessInstances = {};
  sel.innerHTML = '';
  var anyOk = false;
  (list || []).forEach(function (inst) {
    harnessInstances[inst.port] = inst;
    var opt = document.createElement('option');
    opt.value = String(inst.port);
    if (inst.ok) {
      anyOk = true;
      opt.textContent = 'port ' + inst.port + ' - ' + (inst.llm_model || 'model nieznany');
    } else {
      opt.textContent = 'port ' + inst.port + ' (niedostępny)';
      opt.disabled = true;
    }
    sel.appendChild(opt);
  });
  var want = null;
  if (harnessInstances[18000] && harnessInstances[18000].ok) want = '18000';
  if (!want) {
    var firstOk = (list || []).find(function (i) { return i.ok; });
    want = firstOk ? String(firstOk.port) : '18000';
  }
  if (prevVal && harnessInstances[prevVal] && harnessInstances[prevVal].ok) {
    sel.value = prevVal;
  } else {
    sel.value = want;
  }
  if (note) note.textContent = anyOk ? '' : 'brak działających instancji harnessu na portach 18000-18010';
}

function refreshHarnessInstances() {
  var note = document.getElementById('harness-select-note');
  if (note) note.textContent = 'wykrywanie instancji (probe /health 18000-18010)...';
  return fetch('/api/harness_instances').then(function (r) { return r.json(); })
    .then(function (data) { renderHarnessSelect(data.instances || []); })
    .catch(function () { if (note) note.textContent = 'błąd wykrywania instancji'; });
}

function setAskModelLabels(port, modelName) {
  var h = document.getElementById('ask-harness-model');
  var b = document.getElementById('ask-base-model');
  if (h) h.textContent = 'port ' + port + ' - model: ' + (modelName || '?');
  if (b) b.textContent = 'model bazowy (bez harnessu, temperature 0): ' + (modelName || '?');
}

var sampled = null;

function sampleQuestion() {
  var sel = document.getElementById('sample-file');
  var ta = document.getElementById('question');
  var box = document.getElementById('sample-gold');
  if (!sel || !ta) return;
  fetch('/api/sample?file=' + encodeURIComponent(sel.value))
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.error) { box.hidden = false; box.textContent = 'błąd: ' + d.error; sampled = null; return; }
      sampled = d;
      ta.value = d.question || '';
      box.hidden = false;
      box.innerHTML = '';
      var b = document.createElement('b');
      b.textContent = 'Odpowiedź wzorcowa: ' + (d.answer === null || d.answer === undefined ? '?' : d.answer);
      box.appendChild(b);
      var s = document.createElement('span');
      s.className = 'muted small';
      s.textContent = '  (' + [d.id, d.type, d.era].filter(Boolean).join(' · ') + ')';
      box.appendChild(s);
    })
    .catch(function () { box.hidden = false; box.textContent = 'błąd sieci'; });
}

function askQuestion() {
  var ta = document.getElementById('question');
  var btn = document.getElementById('ask-btn');
  var harnessCol = document.getElementById('ask-harness');
  var baseCol = document.getElementById('ask-base');
  var portSel = document.getElementById('harness-port');
  var q = ta.value.trim();
  if (!q) return;
  var port = portSel ? parseInt(portSel.value, 10) : 18000;
  if (!port || isNaN(port)) port = 18000;
  var inst = harnessInstances[port];
  setAskModelLabels(port, inst ? inst.llm_model : null);
  btn.disabled = true;
  harnessCol.textContent = 'pytam harness (do 120s)...';
  baseCol.textContent = 'pytam model bazowy (do 120s)...';
  fetch('/api/ask', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question: q, port: port})
  }).then(function (r) { return r.json(); })
    .then(function (data) {
      renderAsk(harnessCol, data.harness, true);
      renderAsk(baseCol, data.base, false);
      var respPort = (data.harness && data.harness.port) || port;
      var respInst = harnessInstances[respPort];
      setAskModelLabels(respPort, respInst ? respInst.llm_model : (inst ? inst.llm_model : null));
    })
    .catch(function () { harnessCol.textContent = 'błąd sieci'; baseCol.textContent = 'błąd sieci'; })
    .finally(function () { btn.disabled = false; });
}

function renderAsk(container, res, isHarness) {
  container.innerHTML = '';
  if (!res) { container.textContent = 'brak odpowiedzi'; return; }
  var lat = document.createElement('div');
  lat.className = 'muted small';
  lat.textContent = 'latencja: ' + (res.latency_s !== undefined ? Number(res.latency_s).toFixed(2) + ' s' : '?') +
    (res.source ? (' - źródło: ' + res.source) : '');
  container.appendChild(lat);
  if (res.ok === false) {
    var err = document.createElement('div');
    err.className = 'errbox';
    err.textContent = res.error || 'błąd';
    container.appendChild(err);
    return;
  }
  var ans = document.createElement('pre');
  ans.className = 'logbox';
  ans.textContent = res.answer === undefined ? '' : res.answer;
  container.appendChild(ans);
  if (isHarness && res.titles && res.titles.length) {
    var t = document.createElement('div');
    t.className = 'muted small';
    t.textContent = 'kontekst (KB): ' + res.titles.join('; ');
    container.appendChild(t);
  }
}

var REFRESH_KEYS = ['system', 'models', 'kb'];

function refreshLive() {
  var savedSort = {};
  REFRESH_KEYS.forEach(function (key) {
    var el = document.getElementById(key + '-body');
    if (el) savedSort[key] = captureSortState(el);
  });
  fetch('/api/refresh').then(function (r) { return r.json(); }).then(function (data) {
    REFRESH_KEYS.forEach(function (key) {
      var el = document.getElementById(key + '-body');
      if (el && data[key + '_html'] !== undefined) {
        el.innerHTML = data[key + '_html'];
      }
    });
    initSortableTables(document);
    REFRESH_KEYS.forEach(function (key) {
      var el = document.getElementById(key + '-body');
      if (el) applySortState(el, savedSort[key]);
    });
    var stamp = document.getElementById('last-refresh');
    if (stamp) stamp.textContent = new Date().toLocaleTimeString('pl-PL');
  }).catch(function () {});
}

// ==== Pełna matura: odswiezanie ocen co 15s bez zwijania <details> (sekcja dodana przez agenta) ====
// Podsumowanie: caly kontener #matura-summary-body wymieniany jest tak samo jak system/models/kb
// wyzej (nie ma tam <details>, wiec pelna wymiana innerHTML jest bezpieczna).
// Widok arkusza: <details> z trescia zadania i kryteriami CKE siedza w kazdym wierszu, wiec zamiast
// wymieniac cala tabele, aktualizujemy punktowo tylko #mg-<system>-<id> (znaczek punktow) i
// #mr-<system>-<id> (uzasadnienie egzaminatora) - <details> nigdy nie jest dotykany, wiec nie moze sie zwinac.
function refreshMaturaSummary() {
  var el = document.getElementById('matura-summary-body');
  if (!el) return;
  fetch('/api/matura/summary').then(function (r) { return r.json(); }).then(function (d) {
    if (d && d.html !== undefined) el.innerHTML = d.html;
  }).catch(function () {});
}

function refreshMaturaPaper() {
  var marker = document.getElementById('matura-paper-marker');
  if (!marker) return;
  var paper = marker.getAttribute('data-paper');
  fetch('/api/matura/grades?paper=' + encodeURIComponent(paper)).then(function (r) { return r.json(); }).then(function (d) {
    Object.keys(d || {}).forEach(function (sys) {
      var bySys = d[sys] || {};
      Object.keys(bySys).forEach(function (tid) {
        var g = bySys[tid];
        var ptsEl = document.getElementById('mg-' + sys + '-' + tid);
        if (ptsEl) { ptsEl.className = 'badge ' + g.cls; ptsEl.textContent = g.label; }
        var reasonEl = document.getElementById('mr-' + sys + '-' + tid);
        if (reasonEl) {
          if (g.graded) { reasonEl.classList.remove('muted', 'small'); reasonEl.textContent = g.reason; }
          else { reasonEl.classList.add('muted', 'small'); reasonEl.textContent = 'ocena w toku'; }
        }
      });
    });
  }).catch(function () {});
}

// -- baner "sa nowe wyniki": wyniki nie przeladowuja sie same, zeby nie gubic filtrow --
function watchDataVersion() {
  var v0 = document.body.getAttribute('data-version');
  var banner = document.getElementById('new-data');
  if (!v0 || !banner) return;
  setInterval(function () {
    fetch('/api/version').then(function (r) { return r.json(); }).then(function (d) {
      if (d.version && d.version !== v0) banner.hidden = false;
    }).catch(function () {});
  }, 20000);
}

document.addEventListener('DOMContentLoaded', function () {
  initSortableTables(document);
  initFilters();
  var btn = document.getElementById('ask-btn');
  if (btn) {
    btn.addEventListener('click', askQuestion);
    refreshHarnessInstances();
    var ta = document.getElementById('question');
    ta.addEventListener('input', function () {
      var box = document.getElementById('sample-gold');
      if (sampled && ta.value.trim() !== String(sampled.question || '').trim()) { box.hidden = true; sampled = null; }
    });
  }
  if (document.getElementById('system-body')) setInterval(refreshLive, 15000);
  if (document.getElementById('matura-summary-body')) setInterval(refreshMaturaSummary, 15000);
  if (document.getElementById('matura-paper-marker')) setInterval(refreshMaturaPaper, 15000);
  watchDataVersion();
});
"""


# --------------------------------------------------------------------------
# Szkielet strony
# --------------------------------------------------------------------------

NAV = [
    ("/", "Przegląd"),
    ("/przyrost", "Przyrost"),
    ("/wynik", "Najlepszy wynik"),
    ("/maly", "Mały, ale wariat"),
    ("/modele", "Modele"),
    ("/przebiegi", "Przebiegi"),
    ("/sweep", "Sweepy"),
    ("/zestaw", "Zestaw testowy"),
    ("/matura", "Pełna matura"),
    ("/zapytaj", "Sprawdź pytanie"),
    ("/system", "System"),
]


def page(request: Request, active: str, title: str, body: str, status_code: int = 200) -> HTMLResponse:
    m = norm_metric(request.query_params.get("m"))
    nav = "".join(
        "<a href=\"{}\"{}>{}</a>".format(esc(url(p, m=m)), " class=\"active\"" if p == active else "", esc(name))
        for p, name in NAV)
    toggle = []
    for key, name in METRICS.items():
        params = dict(request.query_params)
        params["m"] = key
        toggle.append("<a class=\"seg{}\" href=\"{}\">{}</a>".format(
            " active" if key == m else "", esc(request.url.path + "?" + urlencode(params)), esc(name)))
    html_ = (
        "<!DOCTYPE html><html lang=\"pl\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>{title} &middot; Vibers WMT</title><style>{css}</style></head>"
        "<body data-version=\"{ver}\">"
        "<header><div class=\"header-row\"><div><h1>Vibers &middot; Warsaw Model Trainers</h1>"
        "<div class=\"sub\">matura z historii &middot; panel wyników &middot; ostatnie odświeżenie: <span id=\"last-refresh\">{now}</span></div></div>"
        "<div class=\"metric-toggle\" title=\"ścisła = dokładny format odpowiedzi; łagodna = poprawna odpowiedź gdziekolwiek w tekście\">"
        "Ocena: {toggle}</div></div><nav class=\"tabs\">{nav}</nav></header>"
        "<main><div id=\"new-data\" class=\"banner\" hidden>Są nowe wyniki w experiments.csv albo devset/runs/. "
        "<a href=\"\">Odśwież stronę</a></div>{body}</main>"
        "<footer class=\"links muted\"><a href=\"{lb}\" target=\"_blank\" rel=\"noopener\">Leaderboard</a>"
        "<a href=\"{ex}\" target=\"_blank\" rel=\"noopener\">Live exams</a>"
        "<a href=\"{ru}\" target=\"_blank\" rel=\"noopener\">Zasady</a></footer>"
        "<script>{js}</script></body></html>"
    ).format(
        title=esc(title), css=CSS, ver=esc(data_version()), now=esc(time.strftime("%H:%M:%S")),
        toggle="".join(toggle), nav=nav, body=body,
        lb=esc(LEADERBOARD_URL), ex=esc(EXAM_URL), ru=esc(RULES_URL), js=JS,
    )
    return HTMLResponse(html_, status_code=status_code)


def not_found(request: Request, what: str) -> HTMLResponse:
    return page(request, "", "Nie znaleziono", section("Nie znaleziono", "<p>{}</p>".format(esc(what))), status_code=404)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, m: str = DEFAULT_METRIC) -> HTMLResponse:
    return page(request, "/", "Przegląd", render_overview(get_index(), norm_metric(m)))


@app.get("/przyrost", response_class=HTMLResponse)
def gain_view(request: Request, m: str = DEFAULT_METRIC) -> HTMLResponse:
    return page(request, "/przyrost", "Przyrost", render_gain_page(get_index(), norm_metric(m)))


@app.get("/wynik", response_class=HTMLResponse)
def best_view(request: Request, m: str = DEFAULT_METRIC, zestaw: str = SCOPE_FULL, typ: str = "") -> HTMLResponse:
    return page(request, "/wynik", "Najlepszy wynik", render_best_page(get_index(), norm_metric(m), zestaw, typ))


@app.get("/maly", response_class=HTMLResponse)
def small_view(request: Request, m: str = DEFAULT_METRIC) -> HTMLResponse:
    return page(request, "/maly", "Mały, ale wariat", render_small_page(get_index(), norm_metric(m)))


@app.get("/modele", response_class=HTMLResponse)
def models_view(request: Request, m: str = DEFAULT_METRIC) -> HTMLResponse:
    return page(request, "/modele", "Modele", render_models_page(get_index(), norm_metric(m)))


@app.get("/model/{key}", response_class=HTMLResponse)
def model_view(request: Request, key: str, m: str = DEFAULT_METRIC) -> HTMLResponse:
    idx = get_index()
    if key not in known_models(idx):
        return not_found(request, "Nieznany model.")
    return page(request, "/modele", key, render_model_page(idx, key, norm_metric(m)))


@app.get("/przebiegi", response_class=HTMLResponse)
def runs_view(request: Request, m: str = DEFAULT_METRIC) -> HTMLResponse:
    return page(request, "/przebiegi", "Przebiegi", render_runs_page(get_index(), norm_metric(m)))


@app.get("/run", response_class=HTMLResponse)
def run_view(request: Request, file: str = "", m: str = DEFAULT_METRIC) -> HTMLResponse:
    p = resolve_run_file(file)
    if p is None:
        return not_found(request, "Nieznany lub niedozwolony plik przebiegu.")
    return page(request, "/przebiegi", "Przebieg", render_run_page(get_index(), p, norm_metric(m)))


@app.get("/porownaj", response_class=HTMLResponse)
def compare_view(request: Request, b: str = "", t: str = "", m: str = DEFAULT_METRIC) -> HTMLResponse:
    bp, tp = resolve_run_file(b), resolve_run_file(t)
    if bp is None or tp is None:
        return not_found(request, "Nieznany lub niedozwolony plik przebiegu.")
    return page(request, "/przyrost", "Porównanie B vs T", render_compare_page(get_index(), bp, tp, norm_metric(m)))


@app.get("/sweep", response_class=HTMLResponse)
def sweep_view(request: Request, f: str = "", m: str = DEFAULT_METRIC) -> HTMLResponse:
    return page(request, "/sweep", "Sweepy", render_sweep_page(f, norm_metric(m)))


@app.get("/zestaw", response_class=HTMLResponse)
def devset_view(request: Request) -> HTMLResponse:
    return page(request, "/zestaw", "Zestaw testowy", section("Zestaw testowy", render_devset_html()))


# ==== PEŁNA MATURA: trasy (sekcja dodana przez agenta) ====================
@app.get("/matura", response_class=HTMLResponse)
def matura_summary_view(request: Request) -> HTMLResponse:
    return page(request, "/matura", "Pełna matura", render_matura_summary_page())


@app.get("/matura/{paper}", response_class=HTMLResponse)
def matura_paper_view(request: Request, paper: str, sys: str = "harness_lora",
                       mode: str = "single", a: str = "raw", b: str = "harness_lora") -> HTMLResponse:
    if paper not in MATURA_PAPERS:
        return not_found(request, "Nieznany arkusz pełnej matury.")
    sys_key = sys if sys in MATURA_SYSTEMS else "harness_lora"
    mode_key = mode if mode in ("single", "compare") else "single"
    sys_a = a if a in MATURA_SYSTEMS else "raw"
    sys_b = b if b in MATURA_SYSTEMS else "harness_lora"
    body = render_matura_paper_page(paper, sys_key, mode_key, sys_a, sys_b)
    return page(request, "/matura", "{} · pełna matura".format(paper), body)


@app.get("/api/matura/summary")
def api_matura_summary() -> JSONResponse:
    return JSONResponse({"html": render_matura_summary_body()})


@app.get("/api/matura/grades")
def api_matura_grades(paper: str = "") -> JSONResponse:
    if paper not in MATURA_PAPERS:
        return JSONResponse({}, status_code=404)
    grades = load_matura_grades()
    items = load_cke_paper(paper)
    out: dict[str, dict] = {}
    for sysk in MATURA_SYSTEMS:
        sys_out = {}
        for it in items:
            tid = str(it.get("id"))
            g = grades.get((sysk, paper, tid))
            pts = g.get("points") if g else None
            mx = (g.get("max") if g else None) or it.get("points")
            cls, label = matura_badge_info(pts, mx)
            sys_out[tid] = {
                "cls": cls, "label": label,
                "graded": g is not None,
                "reason": (g.get("reason") if g else "") or "",
            }
        out[sysk] = sys_out
    return JSONResponse(out)
# ==== KONIEC: PEŁNA MATURA (trasy) =========================================


@app.get("/zapytaj", response_class=HTMLResponse)
def ask_view(request: Request) -> HTMLResponse:
    return page(request, "/zapytaj", "Sprawdź pytanie", render_ask_page())


@app.get("/system", response_class=HTMLResponse)
def system_view(request: Request) -> HTMLResponse:
    body = (
        "<section class=\"card\" id=\"sec-system\"><h2>System</h2><div id=\"system-body\">{}</div></section>"
        "<section class=\"card\" id=\"sec-models\"><h2>Pliki modeli</h2><div id=\"models-body\">{}</div></section>"
        "<section class=\"card\" id=\"sec-kb\"><h2>Baza wiedzy</h2><div id=\"kb-body\">{}</div></section>"
        "<section class=\"card\"><h2>Logi</h2>{}</section>"
        "<p class=\"muted small\">Sekcje System, Pliki modeli i Baza wiedzy odświeżają się same co 15 s.</p>"
    ).format(render_system_html(), render_models_html(), render_kb_html(), render_logs_html())
    return page(request, "/system", "System", body)
