#!/opt/hermes/.venv/bin/python
"""Idempotent patcher for Hermes' ~/.hermes/config.yaml on Render.

Adds two things the first time it runs against a given config.yaml:
  1. mcp_servers.render -- HTTP MCP server pointed at mcp.render.com,
     authenticated via the RENDER_MCP_API_KEY env var. Hermes supports
     ${VAR} substitution in headers, so the key is resolved lazily at
     gateway startup. Users can rotate the key in Render's Environment
     tab without rebuilding the image.

     The Render MCP server is registered without a `tools.include`
     filter, so Hermes can see every MCP tool the provided API key is
     allowed to use. Operators should treat this as full Render account
     access and secure the dashboard/API key accordingly.

  2. skills.external_dirs -- exposes two pre-baked skill bundles to
     skills_list() and the / slash command surface, without colliding
     with the upstream skills_sync flow on /opt/data/skills:
       - /opt/render-tools/skills-local    (Hermes-on-Render overlay)
       - /opt/render-tools/skills-upstream (pinned render-oss/skills)
     The local overlay is listed first so its skill names win on collision.

  3. dashboard.oauth -- selects Hermes' self-hosted OIDC dashboard auth
     provider by default. Runtime issuer/client/scopes are still supplied
     through Render environment variables so secrets stay out of config.yaml.

The patcher is INSERT-only by design. If either key already exists
(even pointing somewhere different), it leaves it alone. This means:
  - Re-running the patcher on every boot is safe.
  - Users who edit config.yaml from the dashboard own those edits.
  - The skill bundle in the image always loads at /opt/render-tools/skills,
    regardless of whether external_dirs has other entries.

Uses PyYAML, which ships with Hermes' .venv.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

# Listed in precedence order: skills-local wins on name collision with
# skills-upstream, which lets our overlay shadow a same-named upstream skill.
RENDER_SKILL_DIRS = (
    "/opt/render-tools/skills-local",
    "/opt/render-tools/skills-upstream",
)
RENDER_MCP_URL = "https://mcp.render.com/mcp"
RENDER_MCP_AUTH = "Bearer ${RENDER_MCP_API_KEY}"
DEFAULT_DASHBOARD_OAUTH = {
    "provider": "self-hosted",
    "self_hosted": {
        "issuer": "${HERMES_DASHBOARD_OIDC_ISSUER}",
        "client_id": "${HERMES_DASHBOARD_OIDC_CLIENT_ID}",
        "scopes": "${HERMES_DASHBOARD_OIDC_SCOPES}",
    },
}

def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[render-tools] cannot read {path}: {exc}", file=sys.stderr)
        return {}
    if not raw.strip():
        return {}
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        print(
            f"[render-tools] {path} is not valid YAML ({exc}); refusing to patch",
            file=sys.stderr,
        )
        sys.exit(0)
    return data if isinstance(data, dict) else {}


def _render_entry() -> dict:
    return {
        "url": RENDER_MCP_URL,
        "headers": {"Authorization": RENDER_MCP_AUTH},
    }


def ensure_render_mcp(config: dict) -> bool:
    """Insert mcp_servers.render if missing. Returns True if changed."""
    mcp_servers = config.get("mcp_servers")
    if mcp_servers is None:
        config["mcp_servers"] = {"render": _render_entry()}
        return True
    if not isinstance(mcp_servers, dict):
        print(
            "[render-tools] mcp_servers is not a mapping; skipping render entry",
            file=sys.stderr,
        )
        return False
    if "render" in mcp_servers:
        return False
    mcp_servers["render"] = _render_entry()
    return True


def ensure_external_skill_dirs(config: dict) -> list[str]:
    """Append the render-tools skill dirs to skills.external_dirs if missing.

    Returns the list of paths that were actually added.
    """
    skills = config.setdefault("skills", {})
    if not isinstance(skills, dict):
        print(
            "[render-tools] skills is not a mapping; skipping external_dirs",
            file=sys.stderr,
        )
        return []
    existing = skills.get("external_dirs")
    if existing is None:
        skills["external_dirs"] = list(RENDER_SKILL_DIRS)
        return list(RENDER_SKILL_DIRS)
    if not isinstance(existing, list):
        print(
            "[render-tools] skills.external_dirs is not a list; skipping",
            file=sys.stderr,
        )
        return []
    added: list[str] = []
    for path in RENDER_SKILL_DIRS:
        if path not in existing:
            existing.append(path)
            added.append(path)
    return added


def ensure_dashboard_oauth(config: dict) -> bool:
    """Insert missing dashboard OAuth defaults without overwriting user choices."""
    dashboard = config.setdefault("dashboard", {})
    if not isinstance(dashboard, dict):
        print(
            "[render-tools] dashboard is not a mapping; skipping dashboard auth defaults",
            file=sys.stderr,
        )
        return False

    oauth = dashboard.get("oauth")
    if oauth is None:
        oauth = {}
        dashboard["oauth"] = oauth
    elif not isinstance(oauth, dict):
        print(
            "[render-tools] dashboard.oauth is not a mapping; skipping dashboard auth defaults",
            file=sys.stderr,
        )
        return False

    changed = False
    if "provider" not in oauth:
        oauth["provider"] = DEFAULT_DASHBOARD_OAUTH["provider"]
        changed = True
    if "self_hosted" not in oauth:
        oauth["self_hosted"] = DEFAULT_DASHBOARD_OAUTH["self_hosted"].copy()
        changed = True
    return changed


def save_config(path: Path, config: dict) -> None:
    text = yaml.safe_dump(
        config,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    tmp = path.with_suffix(path.suffix + ".render-tools.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch-config.py <path/to/config.yaml>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    path.parent.mkdir(parents=True, exist_ok=True)
    config = load_config(path)
    changed_mcp = ensure_render_mcp(config)
    added_dirs = ensure_external_skill_dirs(config)
    changed_dashboard_oauth = ensure_dashboard_oauth(config)
    if changed_mcp or added_dirs or changed_dashboard_oauth:
        save_config(path, config)
        parts = []
        if changed_mcp:
            parts.append("mcp_servers.render")
        for dir_path in added_dirs:
            parts.append(f"skills.external_dirs += {dir_path}")
        if changed_dashboard_oauth:
            parts.append("dashboard.oauth")
        print(f"[render-tools] patched {path}: {', '.join(parts)}")
    else:
        print(f"[render-tools] {path} already has render MCP, skill dirs, and dashboard auth; nothing to do")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
