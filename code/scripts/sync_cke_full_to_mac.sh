#!/bin/bash
# Synchronizuje devset/cke_full/*.jsonl (pelne papiery matury CKE, odpowiedzi
# trzech wariantow systemu, oceny egzaminatora gdy juz sa gotowe) oraz
# data_cke/mentor-astra-descriptions.exam.json z laptopa na Maca (baza),
# przez tar-over-ssh. Idempotentne: kazde uruchomienie po prostu nadpisuje
# pliki po drugiej stronie.
#
# CKE to material chroniony prawem autorskim - nigdy nie commitujemy go do
# repo (patrz CLAUDE.md); ten skrypt to jedyny kanal, ktorym te pliki trafiaja
# na Maca, do prywatnego panelu zespolu.
#
# Uzycie: scripts/sync_cke_full_to_mac.sh   (z Git Bash; LF, nie PowerShell)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REMOTE_HOST="baza"
REMOTE_BASE="wmt-matura"
REMOTE_CKE_FULL="${REMOTE_BASE}/devset/cke_full"

cd "${BASE_DIR}"

shopt -s nullglob
jsonl_files=(devset/cke_full/*.jsonl)
shopt -u nullglob

if [ "${#jsonl_files[@]}" -eq 0 ]; then
  echo "BLAD: brak plikow devset/cke_full/*.jsonl do wyslania (uruchamiasz z katalogu repo?)" >&2
  exit 1
fi

echo "Zdalny katalog: ${REMOTE_HOST}:~/${REMOTE_CKE_FULL}/"
ssh -o BatchMode=yes "${REMOTE_HOST}" "mkdir -p ~/${REMOTE_CKE_FULL}"

echo "Wysylam ${#jsonl_files[@]} plikow *.jsonl z devset/cke_full/:"
printf '  %s\n' "${jsonl_files[@]}"
tar -cf - "${jsonl_files[@]}" | ssh -o BatchMode=yes "${REMOTE_HOST}" "tar -xf - -C ~/${REMOTE_BASE}"

MENTOR_EXAM="data_cke/mentor-astra-descriptions.exam.json"
if [ -f "${MENTOR_EXAM}" ]; then
  echo "Wysylam ${MENTOR_EXAM} -> ~/${REMOTE_CKE_FULL}/mentor-astra-descriptions.exam.json"
  tar -cf - -C data_cke mentor-astra-descriptions.exam.json \
    | ssh -o BatchMode=yes "${REMOTE_HOST}" "tar -xf - -C ~/${REMOTE_CKE_FULL}"
else
  echo "UWAGA: brak ${MENTOR_EXAM} lokalnie, pomijam" >&2
fi

echo
echo "Gotowe. Zawartosc ~/${REMOTE_CKE_FULL}/ na Macu:"
ssh -o BatchMode=yes "${REMOTE_HOST}" "ls -la ~/${REMOTE_CKE_FULL}/"
