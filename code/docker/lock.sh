#!/usr/bin/env bash
# Compile docker/requirements.in -> docker/requirements.txt (fully pinned, hashes, all platforms).
# Needs uv (https://docs.astral.sh/uv/). Run on any host: bash docker/lock.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
UV=${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}
"$UV" pip compile "$HERE/requirements.in" \
  --universal --python-version 3.12 --generate-hashes \
  --no-header --annotation-style line \
  -o "$HERE/requirements.txt"
echo "wrote $HERE/requirements.txt"
