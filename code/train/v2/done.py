"""exit 0 if devset/experiments.csv has a row for (label, <stem>.jsonl) with n > 0 and errors == 0."""
import csv
import os
import sys

lab, stem = sys.argv[1], sys.argv[2]
try:
    with open(os.environ.get("CSV", "/workspace/wmt-matura/devset/experiments.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["label"] == lab and r["files"] == stem + ".jsonl" and int(r["n"] or 0) > 0 \
                    and int(r["errors"] or 0) == 0:
                sys.exit(0)
except (OSError, ValueError, KeyError):
    pass
sys.exit(1)
