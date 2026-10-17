#!/usr/bin/env python
"""Extract image-description ("Opis ilustracji/mapy/obrazu/...") blocks from the CKE
adapted-for-blind (kod 660) history matura .docx papers and map them to task numbers.

Writes data_cke/660/descriptions.jsonl with one line per description:
  {"paper": "...", "task": "...", "description": "...", "source_file": "..."}

Never commits anything (data_cke/ is git-ignored); this script is safe to commit.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import docx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data_cke" / "660" / "descriptions.jsonl"

# (paper label, docx path relative to repo root)
SOURCES = [
    ("2023-maj", "data_cke/660/2023-maj/MHIP-R0-660-2305.docx"),
    ("2022-12-diagnostyczny", "data_cke/660/2022-12-diagnostyczny/MHIP-R0-660-2212.docx"),
    ("informator", "data_cke/660/informator/Informator_EM2023_historia_660.docx"),
]

TASK_RE = re.compile(r"^\s*Zadanie\s+(\d+)(?:\.(\d+))?\.?\s*(.*)$", re.IGNORECASE)
TRIGGER_RE = re.compile(
    r"\bOpis\s+(ilustracji|mapy|obrazu|planu|grafiki|zdj[eę]cia|fotografii|schematu|wykresu|"
    r"tablicy|karykatury|plakatu|rysunku|zr[oó]d[lł]a ikonograficznego)\b",
    re.IGNORECASE,
)
HEADER_RE = re.compile(r"^\s*(Zadanie|Źr[oó]d[lł]o|Fragment)\b", re.IGNORECASE)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def extract(paper: str, rel_path: str) -> list[dict]:
    path = ROOT / rel_path
    d = docx.Document(str(path))
    paras = [p.text for p in d.paragraphs]
    n = len(paras)

    current_task = None
    out = []
    i = 0
    while i < n:
        text = paras[i]
        m = TASK_RE.match(text)
        if m:
            current_task = m.group(1)  # main task number only (drop .subpart)

        if TRIGGER_RE.search(text):
            body = norm(text)
            # strip a leading "Źródło N." / "Opis X." label from the trigger line itself
            body_wo_label = re.sub(r"^(Źr[oó]d[lł]o\s*\d*\.?\s*)?", "", body, flags=re.IGNORECASE)
            collected = []
            if len(body_wo_label) > 80:
                collected.append(body_wo_label)
            # walk forward collecting continuation paragraphs
            j = i + 1
            blanks = 0
            steps = 0
            while j < n and steps < 8:
                nxt = paras[j]
                if not nxt.strip():
                    blanks += 1
                    if blanks >= 2:
                        break
                    j += 1
                    steps += 1
                    continue
                if HEADER_RE.match(nxt) or TRIGGER_RE.search(nxt):
                    break
                collected.append(norm(nxt))
                blanks = 0
                j += 1
                steps += 1
            description = norm(" ".join(collected))
            if description:
                out.append(
                    {
                        "paper": paper,
                        "task": current_task,
                        "description": description,
                        "source_file": rel_path,
                    }
                )
        i += 1
    return out


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for paper, rel_path in SOURCES:
        rows = extract(paper, rel_path)
        print(f"{paper:24s} {rel_path:55s} -> {len(rows)} descriptions")
        all_rows.extend(rows)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"total {len(all_rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
