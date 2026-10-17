"""Build an image-description map for an official exam package (exam.json + images/).

Output: JSON {"images/X.png": "text", ...} for harness/exam_runner.py --image-desc.
  - official CKE '660' descriptions (data_cke/660/descriptions.jsonl, rows {paper, task, description}) are used
    when --paper is given and a row exists for the item's task number;
  - every other image gets its caption only (the source line that introduces it in source_text).

Tasks with several images but one official description need an explicit choice: --assign TASK=IMAGE
(e.g. --assign 5=images/Z05-S1.png) says which image the description belongs to; without it the description
goes to the first image of the task and a warning is printed.

  python scripts/build_image_desc.py data_cke/mock2023/exam.json data_cke/mock2023/image_desc.json \
      --descriptions data_cke/660/descriptions.jsonl --paper 2023-maj \
      --assign 5=images/Z05-S1.png --assign 24=images/Z24-S2.png
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\[Obraz:\s*(images/[^\]\s]+)\s*\]")
SOURCE_LINE = re.compile(r"^\s*(Źródło|Zrodlo)\s+(\d+)\.", re.I)


def captions_for(item: dict) -> dict[str, str]:
    """Caption of every image of one item: the 'Źródło N.' line matching the image (…-S<N>.png), else the
    nearest text line above its placeholder, else the first line of source_text."""
    src = item.get("source_text") or ""
    lines = src.splitlines()
    source_lines = {}
    for l in lines:
        m = SOURCE_LINE.match(l)
        if m:
            source_lines.setdefault(m.group(2), l.strip())
    out = {}
    for img in item.get("images") or []:
        path = img["path"]
        cap = ""
        m = re.search(r"-S(\d+)\.", path)
        if m and m.group(1) in source_lines:
            cap = source_lines[m.group(1)]
        if not cap:
            for i, l in enumerate(lines):
                if path in l and PLACEHOLDER.search(l):
                    for j in range(i - 1, -1, -1):
                        t = lines[j].strip()
                        if t and not PLACEHOLDER.search(t):
                            cap = t
                            break
                    break
        if not cap:
            cap = next((l.strip() for l in lines if l.strip() and not PLACEHOLDER.search(l)), "")
        out[path] = cap
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exam")
    ap.add_argument("out")
    ap.add_argument("--descriptions", default="")
    ap.add_argument("--paper", default="")
    ap.add_argument("--assign", action="append", default=[], help="TASK=images/X.png")
    args = ap.parse_args(argv)

    exam = json.loads(Path(args.exam).read_text(encoding="utf-8"))
    official: dict[str, str] = {}
    if args.descriptions and args.paper:
        for line in Path(args.descriptions).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("paper") == args.paper and r.get("description"):
                    official[str(r["task"])] = r["description"].strip()
    assign = dict(a.split("=", 1) for a in args.assign)

    task_images: dict[str, list[str]] = {}
    captions: dict[str, str] = {}
    for it in exam["items"]:
        task = str(it.get("group") or it["id"].split(".")[0])
        for p in (img["path"] for img in it.get("images") or []):
            if p not in task_images.setdefault(task, []):
                task_images[task].append(p)
        for p, c in captions_for(it).items():
            captions.setdefault(p, c)

    desc: dict[str, str] = {}
    report = []
    for task, imgs in task_images.items():
        target = None
        if task in official:
            target = assign.get(task) or imgs[0]
            if len(imgs) > 1 and task not in assign:
                print(f"WARNING task {task}: {len(imgs)} images, one description -> {target} (use --assign)",
                      file=sys.stderr)
        for p in imgs:
            if p == target:
                desc[p] = official[task]
                report.append((p, "official-660"))
            else:
                desc[p] = captions.get(p, "")
                report.append((p, "caption-only"))
    Path(args.out).write_text(json.dumps(desc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for p, kind in sorted(report):
        print(f"{p}\t{kind}")
    print(f"{len(desc)} images, {sum(k == 'official-660' for _, k in report)} with official descriptions -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
