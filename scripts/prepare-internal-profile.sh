#!/usr/bin/env bash
set -euo pipefail

: "${HERMES_HOME:=/opt/data}"
: "${HERMES_PROFILE_SOURCE:=/opt/hermes-profile}"
: "${HERMES_OVERWRITE_PROFILE:=0}"
: "${HERMES_OVERWRITE_CONFIG:=1}"
: "${HERMES_WORKSPACE_ROOT:=/workspace}"
: "${HERMES_WORKSPACE_DIR:=$HERMES_WORKSPACE_ROOT/vercel-nextjs-monorepo}"
: "${HERMES_WORKSPACE_REPO:=https://github.com/440ai/vercel-nextjs-monorepo.git}"
: "${HERMES_WORKSPACE_REF:=main}"
: "${HERMES_EXTRA_WORKSPACES:=}"

export HOME="$HERMES_HOME"

as_hermes() {
  if [[ "$(id -u)" == "0" ]] && command -v s6-setuidgid >/dev/null 2>&1; then
    s6-setuidgid hermes "$@"
  elif [[ "$(id -u)" == "0" ]] && command -v runuser >/dev/null 2>&1; then
    runuser -u hermes -- "$@"
  elif [[ "$(id -u)" == "0" ]] && command -v gosu >/dev/null 2>&1; then
    gosu hermes "$@"
  else
    "$@"
  fi
}

sync_managed_block() {
  local block_id="$1"
  local source_file="$2"
  local target_file="$3"

  [[ -f "$source_file" ]] || return 0
  mkdir -p "$(dirname "$target_file")"
  touch "$target_file"

  local begin_marker="<!-- BEGIN 440-MANAGED:${block_id} -->"
  local end_marker="<!-- END 440-MANAGED:${block_id} -->"
  local tmp_file
  tmp_file="$(mktemp)"

  awk -v begin="$begin_marker" -v end="$end_marker" '
    $0 == begin { skip = 1; next }
    $0 == end { skip = 0; next }
    skip != 1 { print }
  ' "$target_file" >"$tmp_file"

  {
    sed -e '${/^$/d;}' "$tmp_file"
    printf '\n\n%s\n' "$begin_marker"
    cat "$source_file"
    printf '\n%s\n' "$end_marker"
  } >"$target_file"

  rm -f "$tmp_file"
}

sync_managed_profile_blocks() {
  local managed_dir="$HERMES_PROFILE_SOURCE/managed"
  [[ -d "$managed_dir" ]] || return 0

  sync_managed_block "slack-concierge-soul" "$managed_dir/SOUL.slack-concierge.md" "$HERMES_HOME/SOUL.md"
  sync_managed_block "slack-concierge-memory" "$managed_dir/MEMORY.slack-concierge.md" "$HERMES_HOME/memories/MEMORY.md"
  sync_managed_block "slack-concierge-user" "$managed_dir/USER.slack-concierge.md" "$HERMES_HOME/memories/USER.md"
}

sync_checked_in_profile() {
  mkdir -p "$HERMES_HOME" "$HERMES_HOME/logs"

  if [[ -d "$HERMES_PROFILE_SOURCE" ]]; then
    if [[ "$HERMES_OVERWRITE_PROFILE" == "1" ]]; then
      cp -a "$HERMES_PROFILE_SOURCE"/. "$HERMES_HOME"/
    else
      (
        cd "$HERMES_PROFILE_SOURCE"
        find . -type f ! -name config.yaml -print
      ) | while IFS= read -r relpath; do
        relpath="${relpath#./}"
        mkdir -p "$(dirname "$HERMES_HOME/$relpath")"
        if [[ ! -f "$HERMES_HOME/$relpath" ]]; then
          cp "$HERMES_PROFILE_SOURCE/$relpath" "$HERMES_HOME/$relpath"
        fi
      done
    fi
  fi

  if [[ -d "$HERMES_PROFILE_SOURCE/plugins" ]]; then
    mkdir -p "$HERMES_HOME/plugins"
    cp -a "$HERMES_PROFILE_SOURCE/plugins"/. "$HERMES_HOME/plugins"/
  fi

  if [[ -d "$HERMES_PROFILE_SOURCE/skills" ]]; then
    mkdir -p "$HERMES_HOME/skills"
    cp -a "$HERMES_PROFILE_SOURCE/skills"/. "$HERMES_HOME/skills"/
  fi

  if [[ -d "$HERMES_PROFILE_SOURCE/roles" ]]; then
    mkdir -p "$HERMES_HOME/roles"
    cp -a "$HERMES_PROFILE_SOURCE/roles"/. "$HERMES_HOME/roles"/
  fi

  sync_managed_profile_blocks

  if [[ "${HERMES_OVERWRITE_CONFIG:-1}" == "1" || ! -f "$HERMES_HOME/config.yaml" ]]; then
    cp "$HERMES_PROFILE_SOURCE/config.yaml" "$HERMES_HOME/config.yaml"
  fi

  if [[ -n "${HERMES_AUTH_JSON_B64:-}" && ! -f "$HERMES_HOME/auth.json" ]]; then
    printf '%s' "$HERMES_AUTH_JSON_B64" | base64 -d >"$HERMES_HOME/auth.json"
    chmod 0600 "$HERMES_HOME/auth.json"
  fi

  chown -R hermes:hermes "$HERMES_HOME" "$HERMES_WORKSPACE_ROOT" 2>/dev/null || true
}

setup_git_auth() {
  local token="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
  if [[ -z "$token" ]]; then
    return 0
  fi

  local askpass="$HERMES_HOME/git-askpass.sh"
  cat >"$askpass" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  *Username*) printf '%s\n' x-access-token ;;
  *Password*) printf '%s\n' "${GITHUB_TOKEN:-${GH_TOKEN:-}}" ;;
esac
EOF
  chmod 0700 "$askpass"
  chown hermes:hermes "$askpass" 2>/dev/null || true
  export GIT_ASKPASS="$askpass"
  export GIT_TERMINAL_PROMPT=0
}

sync_one_workspace() {
  local workspace_dir="$1"
  local repo_url="$2"
  local ref_name="$3"

  mkdir -p "$(dirname "$workspace_dir")"
  chown -R hermes:hermes "$(dirname "$workspace_dir")" 2>/dev/null || true

  if [[ ! -d "$workspace_dir/.git" ]]; then
    rm -rf "$workspace_dir"
    if ! as_hermes git clone --branch "$ref_name" "$repo_url" "$workspace_dir"; then
      echo "[render-tools] warning: could not clone $repo_url into $workspace_dir; creating empty dir" >&2
      mkdir -p "$workspace_dir"
      chown -R hermes:hermes "$workspace_dir" 2>/dev/null || true
    fi
  elif [[ "${HERMES_WORKSPACE_AUTO_UPDATE:-1}" != "0" ]]; then
    as_hermes git -C "$workspace_dir" fetch origin "$ref_name" || true
    as_hermes git -C "$workspace_dir" checkout "$ref_name" || true
    as_hermes git -C "$workspace_dir" pull --ff-only origin "$ref_name" || true
  fi

  as_hermes git config --global --add safe.directory "$workspace_dir" || true
}

sync_extra_workspaces() {
  [[ -n "$HERMES_EXTRA_WORKSPACES" ]] || return 0

  local spec name repo_ref repo_url ref_name workspace_dir
  # Intentional splitting on whitespace/newlines for Render env var specs.
  local specs=( $HERMES_EXTRA_WORKSPACES )
  for spec in "${specs[@]}"; do
    [[ -z "$spec" ]] && continue
    name="${spec%%=*}"
    repo_ref="${spec#*=}"
    repo_url="${repo_ref%%#*}"
    ref_name="${repo_ref#*#}"
    if [[ "$repo_ref" != *"#"* ]]; then
      ref_name="main"
    fi
    if [[ -z "$name" || "$name" == "$spec" || -z "$repo_url" ]]; then
      echo "[render-tools] warning: skipping invalid HERMES_EXTRA_WORKSPACES spec '$spec'" >&2
      continue
    fi
    workspace_dir="$HERMES_WORKSPACE_ROOT/$name"
    sync_one_workspace "$workspace_dir" "$repo_url" "$ref_name"
  done
}

sync_workspace() {
  command -v git >/dev/null 2>&1 || return 0
  setup_git_auth
  sync_one_workspace "$HERMES_WORKSPACE_DIR" "$HERMES_WORKSPACE_REPO" "$HERMES_WORKSPACE_REF"
  sync_extra_workspaces
}

mkdir -p "$HERMES_WORKSPACE_ROOT"
sync_checked_in_profile
if [[ "${HERMES_SKIP_WORKSPACE_SYNC:-0}" != "1" ]]; then
  sync_workspace
fi

plugin_count=0
if [[ -d "$HERMES_HOME/plugins" ]]; then
  plugin_count="$(find "$HERMES_HOME/plugins" -name plugin.yaml -type f 2>/dev/null | wc -l | tr -d ' ')"
fi
echo "[render-tools] internal profile ready: home=$HERMES_HOME workspace=$HERMES_WORKSPACE_ROOT plugin_manifests=$plugin_count"
