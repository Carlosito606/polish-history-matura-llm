#!/usr/bin/env bash
# Full ZPE pipeline: crawl (resumable), then question batches, KB chunks and attribution docs.
set -u
cd "$(dirname "$0")/.."
P=${ZPE_PY:-python}
$P scripts/fetch_zpe.py fetch --minutes "${ZPE_MINUTES:-80}" && \
$P scripts/fetch_zpe.py batches --out data_gen/zpe_batches && \
$P scripts/fetch_zpe.py chunks && \
$P scripts/fetch_zpe.py docs
echo "ZPE_PIPELINE_DONE rc=$?"
