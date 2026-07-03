#!/usr/bin/env python3
"""Enforced launch wrapper for 440.ai agent workers.

This script turns the portable agent-work contract from a prompt generator into
an executable guardrail: preflight first, save the rendered prompt, then either
print the exact safe launch plan or execute the selected worker.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import agent_worker_contract as contract  # noqa: E402

DEFAULT_SECRET_BOUNDARY = (
    "Do not request, print, store, or commit raw secrets, passwords, 2FA codes, "
    "payment data, API keys, or unrestricted customer/customer logs."
)
DEFAULT_ARTIFACT_ROOT = Path(tempfile.gettempdir()) / "hermes-agent-work"
CLAUDE_NOT_AUTHENTICATED = "Not logged in"


@dataclass(frozen=True)
class LaunchArtifacts:
    run_dir: Path
    prompt_path: Path
    output_path: Path


@dataclass(frozen=True)
class LaunchPlan:
    engine: str
    issue_url: str
    workdir: Path
    artifacts: LaunchArtifacts
    command: list[str]
    prompt: str


def issue_slug(issue_url: str) -> str:
    ref = contract.parse_issue_url(issue_url)
    return f"{ref.owner}-{ref.repo}-{ref.number}"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_artifacts(
    issue_url: str,
    artifact_root: Path,
    engine: str,
    stamp: str | None = None,
) -> LaunchArtifacts:
    issue_dir = artifact_root / issue_slug(issue_url)
    issue_dir.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=f"{stamp or utc_stamp()}-{engine}-", dir=issue_dir))
    return LaunchArtifacts(
        run_dir=run_dir,
        prompt_path=run_dir / "worker-prompt.md",
        output_path=run_dir / "worker-output.md",
    )


def prompt_with_permission_boundary(
    *,
    engine: str,
    issue_url: str,
    scope: str,
    non_goals: str,
    permission_boundary: str,
    verification: str,
    secret_boundary: str,
    expected_evidence: str,
) -> str:
    base_prompt = contract.build_worker_prompt(
        engine=engine,
        issue_url=issue_url,
        scope=scope,
        non_goals=non_goals,
        verification=verification,
        secret_boundary=secret_boundary,
        expected_evidence=expected_evidence,
    )
    marker = "\nVerification plan:\n"
    permission_section = f"\nAllowed tools / permission level:\n{permission_boundary.strip()}\n\nVerification plan:\n"
    if marker not in base_prompt:
        raise ValueError("worker prompt format changed; could not insert permission boundary")
    return base_prompt.replace(marker, permission_section, 1)


def build_engine_command(
    *,
    engine: str,
    workdir: Path,
    artifacts: LaunchArtifacts,
    codex_sandbox: str,
    claude_allowed_tools: str,
    claude_max_turns: int,
    prompt: str,
) -> list[str]:
    if engine == "codex":
        return [
            "codex",
            "exec",
            "--sandbox",
            codex_sandbox,
            "--cd",
            str(workdir),
            "--output-last-message",
            str(artifacts.output_path),
            "-",
        ]
    if engine == "claude":
        return [
            "claude",
            "-p",
            prompt,
            "--allowedTools",
            claude_allowed_tools,
            "--max-turns",
            str(claude_max_turns),
        ]
    if engine == "hermes":
        return ["hermes", "chat", "-q", prompt]
    raise ValueError(f"unsupported engine: {engine}")


def display_command(command: list[str], prompt: str, prompt_path: Path) -> list[str]:
    safe: list[str] = []
    for arg in command:
        safe.append(f"<prompt from {prompt_path}>" if arg == prompt else arg)
    return safe


def build_launch_plan(args: argparse.Namespace, stamp: str | None = None) -> LaunchPlan:
    artifacts = make_artifacts(args.issue_url, Path(args.artifact_dir), args.engine, stamp=stamp)
    workdir = Path(args.workdir).resolve()
    prompt = prompt_with_permission_boundary(
        engine=args.engine,
        issue_url=args.issue_url,
        scope=args.scope,
        non_goals=args.non_goals,
        permission_boundary=args.permission_boundary,
        verification=args.verification,
        secret_boundary=args.secret_boundary,
        expected_evidence=args.expected_evidence,
    )
    command = build_engine_command(
        engine=args.engine,
        workdir=workdir,
        artifacts=artifacts,
        codex_sandbox=args.codex_sandbox,
        claude_allowed_tools=args.claude_allowed_tools,
        claude_max_turns=args.claude_max_turns,
        prompt=prompt,
    )
    return LaunchPlan(
        engine=args.engine,
        issue_url=args.issue_url,
        workdir=workdir,
        artifacts=artifacts,
        command=command,
        prompt=prompt,
    )


def write_prompt(plan: LaunchPlan) -> None:
    plan.artifacts.run_dir.mkdir(parents=True, exist_ok=True)
    plan.artifacts.prompt_path.write_text(plan.prompt, encoding="utf-8")


def preflight(args: argparse.Namespace) -> list[str]:
    issue = contract.load_issue_json(args.issue_json, args.issue_url)
    return contract.preflight_errors(issue, allow_active=args.allow_active)


def claude_auth_blocker(status_text: str, return_code: int) -> str | None:
    if return_code == 0 and CLAUDE_NOT_AUTHENTICATED not in status_text:
        return None
    return "\n".join(
        [
            "Status: blocked — needs-permission",
            "",
            "What I tried:",
            "- Checked Claude Code authentication before launch.",
            "",
            "What failed:",
            f"- {status_text.strip() or 'Claude auth status failed.'}",
            "",
            "Why this blocks the outcome:",
            "- Claude Code cannot be used as a specialized worker until a human completes auth.",
            "",
            "Smallest action needed:",
            "- Run `claude auth login` or configure an approved non-chat secret-store auth path.",
            "",
            "Safe alternatives available now:",
            "- Use Hermes or Codex worker wrappers; keep Claude assignments blocked until auth is verified.",
        ]
    ) + "\n"


def check_claude_auth(run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> str | None:
    result = run(["claude", "auth", "status", "--text"], text=True, capture_output=True)
    return claude_auth_blocker((result.stdout or "") + (result.stderr or ""), result.returncode)


def print_plan(plan: LaunchPlan, dry_run: bool, prompt: str) -> None:
    payload = {
        "status": "dry-run" if dry_run else "launching",
        "engine": plan.engine,
        "issue_url": plan.issue_url,
        "workdir": str(plan.workdir),
        "prompt_path": str(plan.artifacts.prompt_path),
        "output_path": str(plan.artifacts.output_path),
        "command": display_command(plan.command, prompt, plan.artifacts.prompt_path),
    }
    print(json.dumps(payload, indent=2))


def command_launch(args: argparse.Namespace) -> int:
    errors = preflight(args)
    if errors:
        print("Preflight: blocked", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2

    plan = build_launch_plan(args)
    write_prompt(plan)

    if args.engine == "claude" and args.check_claude_auth:
        blocker = check_claude_auth()
        if blocker:
            plan.artifacts.output_path.write_text(blocker, encoding="utf-8")
            print_plan(plan, dry_run=True, prompt=plan.prompt)
            print(blocker, end="")
            return 2

    if not args.execute:
        print_plan(plan, dry_run=True, prompt=plan.prompt)
        return 0

    print_plan(plan, dry_run=False, prompt=plan.prompt)
    if args.engine == "codex":
        result = subprocess.run(plan.command, input=plan.prompt, text=True)
        return result.returncode

    result = subprocess.run(plan.command, text=True, capture_output=True)
    output = (result.stdout or "") + (result.stderr or "")
    plan.artifacts.output_path.write_text(output, encoding="utf-8")
    print(output, end="")
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, choices=sorted(contract.ENGINES))
    parser.add_argument("--issue-url", required=True)
    parser.add_argument("--issue-json", help="local gh-style issue JSON for offline checks")
    parser.add_argument("--allow-active", action="store_true", help="allow launch when issue already has status: active")
    parser.add_argument("--scope", required=True)
    parser.add_argument("--non-goals", required=True)
    parser.add_argument("--permission-boundary", required=True)
    parser.add_argument("--verification", required=True)
    parser.add_argument("--secret-boundary", default=DEFAULT_SECRET_BOUNDARY)
    parser.add_argument("--expected-evidence", required=True)
    parser.add_argument("--workdir", default=".")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--execute", action="store_true", help="actually launch the worker; default is dry-run")
    parser.add_argument("--codex-sandbox", default="read-only", choices=["read-only", "workspace-write", "danger-full-access"])
    parser.add_argument("--claude-allowed-tools", default="Read")
    parser.add_argument("--claude-max-turns", type=int, default=5)
    parser.add_argument("--check-claude-auth", action="store_true", help="write a needs-permission blocker if Claude Code is unauthenticated")
    parser.set_defaults(func=command_launch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
