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

if [[ ! -d "$LLM_WIKI_VAULT_DIR/.git" ]]; then
  rm -rf "$LLM_WIKI_VAULT_DIR"
  if ! git clone --branch "$LLM_WIKI_REF" "$LLM_WIKI_REPO" "$LLM_WIKI_VAULT_DIR"; then
    echo "[llm-wiki] warning: could not clone $LLM_WIKI_REPO into $LLM_WIKI_VAULT_DIR" >&2
    mkdir -p "$LLM_WIKI_VAULT_DIR"
  fi
else
  git -C "$LLM_WIKI_VAULT_DIR" fetch origin "$LLM_WIKI_REF" || true
  git -C "$LLM_WIKI_VAULT_DIR" checkout "$LLM_WIKI_REF" || true
  git -C "$LLM_WIKI_VAULT_DIR" pull --ff-only origin "$LLM_WIKI_REF" || true
fi

if [[ -d "$LLM_WIKI_VAULT_DIR/.git" ]]; then
  git -C "$LLM_WIKI_VAULT_DIR" remote set-url origin "$LLM_WIKI_REPO" || true
fi

chown -R abc:abc "$(dirname "$LLM_WIKI_VAULT_DIR")" 2>/dev/null || true
echo "[llm-wiki] vault ready: $LLM_WIKI_VAULT_DIR"
