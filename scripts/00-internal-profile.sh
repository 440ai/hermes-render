#!/command/with-contenv sh
set -eu

PROFILE_PREP="/opt/render-tools/prepare-internal-profile.sh"

if [ -x "${PROFILE_PREP}" ]; then
  if ! "${PROFILE_PREP}"; then
    echo "[render-tools] warning: internal profile preparation failed; continuing" >&2
  fi
else
  echo "[render-tools] warning: ${PROFILE_PREP} not found or not executable; skipping profile preparation" >&2
fi
