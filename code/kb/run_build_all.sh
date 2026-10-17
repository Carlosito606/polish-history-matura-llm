#!/usr/bin/env bash
# Build all KB indexes on the Mac (after kb/build_chunks.py). Logs to logs/kb_build_index.log
set -e
cd ~/wmt-matura
source .venv/bin/activate
python -m kb.build_index --chunks kb_data/chunks --out kb_data/index_mini --target-chunks 40000 --max-chunks-per-article 5 --workers 8
python -m kb.build_index --chunks kb_data/chunks --out kb_data/index --workers 8
echo ALL_DONE
