#!/usr/bin/env bash
set -euo pipefail

: "${LLM_WIKI_REPO:=https://github.com/440ai/llm-wiki.git}"
: "${LLM_WIKI_REF:=main}"
: "${LLM_WIKI_VAULT_DIR:=/config/vaults/llm-wiki}"

mkdir -p "$(dirname "$LLM_WIKI_VAULT_DIR")"

setup_git_auth() {
  local token="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
  if [[ -z "$token" ]]; then
    export GIT_TERMINAL_PROMPT=0
    return 0
  fi

  local askpass="/tmp/llm-wiki-git-askpass.sh"
  cat >"$askpass" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  *Username*) printf '%s\n' x-access-token ;;
  *Password*) printf '%s\n' "${GITHUB_TOKEN:-${GH_TOKEN:-}}" ;;
esac
EOF
  chmod 0700 "$askpass"
  export GIT_ASKPASS="$askpass"
  export GIT_TERMINAL_PROMPT=0
}

setup_git_auth

git_vault() {
  git -c "safe.directory=$LLM_WIKI_VAULT_DIR" -C "$LLM_WIKI_VAULT_DIR" "$@"
}

configure_obsidian_vault() {
  local config_dir="${OBSIDIAN_CONFIG_DIR:-/config/.config/obsidian}"
  local config_file="$config_dir/obsidian.json"
  local ts

  mkdir -p "$config_dir" "$LLM_WIKI_VAULT_DIR/.obsidian"

  if [[ -f "$config_file" ]] && grep -Fq "$LLM_WIKI_VAULT_DIR" "$config_file"; then
    return 0
  fi

  if [[ -f "$config_file" ]]; then
    cp "$config_file" "${config_file}.bak.$(date +%s)"
  fi

  ts="$(date +%s)000"
  cat >"$config_file" <<EOF
{
  "vaults": {
    "llm-wiki": {
      "path": "$LLM_WIKI_VAULT_DIR",
      "ts": $ts,
      "open": true
    }
  }
}
EOF
}

if [[ ! -d "$LLM_WIKI_VAULT_DIR/.git" ]]; then
  rm -rf "$LLM_WIKI_VAULT_DIR"
  git clone --branch "$LLM_WIKI_REF" "$LLM_WIKI_REPO" "$LLM_WIKI_VAULT_DIR"
else
  git_vault fetch origin "$LLM_WIKI_REF"
  git_vault checkout "$LLM_WIKI_REF"
  git_vault pull --ff-only origin "$LLM_WIKI_REF"
fi

if [[ -d "$LLM_WIKI_VAULT_DIR/.git" ]]; then
  git_vault remote set-url origin "$LLM_WIKI_REPO"
fi

configure_obsidian_vault
chown -R abc:abc "$(dirname "$LLM_WIKI_VAULT_DIR")" 2>/dev/null || true
echo "[llm-wiki] vault ready: $LLM_WIKI_VAULT_DIR"
