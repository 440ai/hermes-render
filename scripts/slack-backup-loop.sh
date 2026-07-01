#!/usr/bin/env bash
set -euo pipefail

interval="${SLACK_BACKUP_INTERVAL_SECONDS:-900}"
enabled="${SLACK_BACKUP_ENABLED:-1}"
enabled_lc="$(printf '%s' "${enabled}" | tr '[:upper:]' '[:lower:]')"

idle_forever() {
  while true; do
    sleep 86400
  done
}

case "${enabled_lc}" in
  1|true|yes|y|on) ;;
  *)
    echo "[slack-backup] loop disabled by SLACK_BACKUP_ENABLED=${enabled}"
    idle_forever
    ;;
esac

if [[ -z "${SLACK_BOT_TOKEN:-}" ]]; then
  echo "[slack-backup] SLACK_BOT_TOKEN is not set; backup loop idle"
  idle_forever
fi

if ! [[ "${interval}" =~ ^[0-9]+$ ]] || [[ "${interval}" -lt 60 ]]; then
  echo "[slack-backup] invalid SLACK_BACKUP_INTERVAL_SECONDS=${interval}; using 900"
  interval="900"
fi

run_backup() {
  if command -v s6-setuidgid >/dev/null 2>&1; then
    s6-setuidgid hermes python3 /opt/render-tools/slack_backup_dump.py
  else
    python3 /opt/render-tools/slack_backup_dump.py
  fi
}

echo "[slack-backup] loop started interval_seconds=${interval}"

while true; do
  if ! run_backup; then
    echo "[slack-backup] run failed; retrying after ${interval}s" >&2
  fi
  sleep "${interval}"
done
