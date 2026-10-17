#!/usr/bin/env bash
# Full KB pipeline on the Mac: download -> chunks -> indexes. Idempotent-ish; logs in logs/.
set -e
cd ~/wmt-matura
source .venv/bin/activate
[ -f kb_data/raw/plwiki-20251229-cirrussearch-content.json.gz ] || bash kb/download_dump.sh kb_data/raw 16
rm -rf kb_data/chunks
python -m kb.build_chunks --dump kb_data/raw/plwiki-20251229-cirrussearch-content.json.gz --out kb_data/chunks --workers 10 --batch 2000
bash kb/run_build_all.sh
