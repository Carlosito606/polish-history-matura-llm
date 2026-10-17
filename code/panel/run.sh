#!/bin/bash
# Idempotentne start/stop/restart/status dla panelu webowego WMT.
# Uzycie: panel/run.sh {start|stop|restart|status}

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${BASE_DIR}/.venv"
LOG_DIR="${BASE_DIR}/logs"
PID_FILE="${LOG_DIR}/panel.pid"
LOG_FILE="${LOG_DIR}/panel.log"
HOST="<tailscale-host>"
PORT="18090"

mkdir -p "${LOG_DIR}"

is_running() {
  if [ -f "${PID_FILE}" ]; then
    local pid
    pid="$(cat "${PID_FILE}" 2>/dev/null)"
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

do_start() {
  if is_running; then
    echo "panel juz dziala (pid $(cat "${PID_FILE}"))"
    return 0
  fi
  if [ ! -x "${VENV_DIR}/bin/uvicorn" ]; then
    echo "BLAD: nie znaleziono ${VENV_DIR}/bin/uvicorn - czy .venv jest zainstalowany?" >&2
    return 1
  fi
  cd "${BASE_DIR}" || return 1
  nohup "${VENV_DIR}/bin/uvicorn" panel.app:app --host "${HOST}" --port "${PORT}" \
    >> "${LOG_FILE}" 2>&1 &
  local pid=$!
  echo "${pid}" > "${PID_FILE}"
  sleep 1
  if kill -0 "${pid}" 2>/dev/null; then
    echo "panel wystartowal (pid ${pid}) na http://${HOST}:${PORT}/"
  else
    echo "BLAD: panel nie wystartowal, zobacz ${LOG_FILE}" >&2
    rm -f "${PID_FILE}"
    return 1
  fi
}

do_stop() {
  if is_running; then
    local pid
    pid="$(cat "${PID_FILE}")"
    kill "${pid}" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.5
    done
    if kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null
    fi
    rm -f "${PID_FILE}"
    echo "panel zatrzymany (pid ${pid})"
  else
    echo "panel nie dzialal"
    rm -f "${PID_FILE}"
  fi
}

do_status() {
  if is_running; then
    echo "panel dziala (pid $(cat "${PID_FILE}")) na http://${HOST}:${PORT}/"
  else
    echo "panel nie dziala"
  fi
}

case "${1:-}" in
  start) do_start ;;
  stop) do_stop ;;
  restart) do_stop; do_start ;;
  status) do_status ;;
  *)
    echo "Uzycie: $0 {start|stop|restart|status}" >&2
    exit 1
    ;;
esac
