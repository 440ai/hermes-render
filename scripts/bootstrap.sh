#!/command/with-contenv sh
# Render tools startup hook.
#
# The upstream Hermes container seeds /opt/data/config.yaml in its own
# cont-init hook. This hook runs immediately after that and patches in the
# Render MCP server, Render skill dirs, and internal-dashboard auth defaults.

set -eu

DATA_DIR="${HERMES_HOME:-/opt/data}"
PATCHER="/opt/render-tools/patch-config.py"

# Make sure the data dir exists and the hermes user can write to it
# before we run the patcher. Idempotent — if /opt/data is already a
# mounted, chowned disk this is a no-op.
mkdir -p "${DATA_DIR}"
if ! chown -R hermes:hermes "${DATA_DIR}" 2>/dev/null; then
  echo "[render-tools] warning: could not chown ${DATA_DIR}; continuing" >&2
fi

# Patch config.yaml. We never fail the boot on a patch error — the agent
# can still run without the Render MCP server registered, and the user
# can always add it manually from the dashboard.
if [ -x "${PATCHER}" ]; then
  if command -v s6-setuidgid >/dev/null 2>&1; then
    run_as_hermes="s6-setuidgid hermes"
  elif command -v gosu >/dev/null 2>&1; then
    run_as_hermes="gosu hermes"
  else
    run_as_hermes=""
  fi

  if ! ${run_as_hermes} "${PATCHER}" "${DATA_DIR}/config.yaml"; then
    echo "[render-tools] warning: config patch failed; continuing with unmodified config" >&2
  fi
else
  echo "[render-tools] warning: ${PATCHER} not found or not executable; skipping" >&2
fi
