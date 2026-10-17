#!/usr/bin/env bash
# Segmented, resumable download of the plwiki CirrusSearch content dump.
# Usage: bash kb/download_dump.sh [OUT_DIR] [NSEG]
# Uses fast mirrors (ftp.acc.umu.se, dumps.wikimedia.your.org) with parallel HTTP range requests,
# then concatenates parts and verifies total size.
set -u
OUT=${1:-$HOME/wmt-matura/kb_data/raw}
NSEG=${2:-16}
F=plwiki-20251229-cirrussearch-content.json.gz
MIRRORS=(
  "https://ftp.acc.umu.se/mirror/wikimedia.org/other/cirrussearch/20251229/$F"
  "https://dumps.wikimedia.your.org/other/cirrussearch/20251229/$F"
  "https://dumps.wikimedia.org/other/cirrussearch/20251229/$F"
)
mkdir -p "$OUT/parts"
cd "$OUT" || exit 1
L=$(curl -sIL "${MIRRORS[0]}" | tr -d '\r' | awk 'tolower($1)=="content-length:"{v=$2} END{print v}')
echo "total length: $L"
[ -n "$L" ] || { echo "cannot get length"; exit 1; }
S=$(( (L + NSEG - 1) / NSEG ))
fetch_seg() {
  local i=$1 start=$(( $1 * S )) end=$(( ($1 + 1) * S - 1 ))
  [ $end -ge $L ] && end=$(( L - 1 ))
  local want=$(( end - start + 1 )) p="parts/part.$(printf %03d $i)" tries=0
  touch "$p"
  while :; do
    local have; have=$(stat -c %s "$p" 2>/dev/null || stat -f %z "$p")  # GNU first: on Linux `stat -f` means --file-system
    [ "$have" -ge "$want" ] && break
    local m=${MIRRORS[$(( (i + tries) % 2 ))]}
    curl -sS -L --connect-timeout 20 --speed-limit 20000 --speed-time 60 -r $(( start + have ))-$end "$m" >> "$p"
    tries=$(( tries + 1 ))
    [ $tries -gt 200 ] && { echo "seg $i failed"; return 1; }
  done
  echo "seg $i done ($want bytes)"
}
for i in $(seq 0 $(( NSEG - 1 ))); do fetch_seg "$i" & done
wait
cat parts/part.* > "$F.tmp"
got=$(stat -c %s "$F.tmp" 2>/dev/null || stat -f %z "$F.tmp")
if [ "$got" = "$L" ]; then mv "$F.tmp" "$F"; gzip -t "$F" && echo "DOWNLOAD_OK $F" && rm -rf parts; else echo "SIZE MISMATCH $got != $L"; fi
