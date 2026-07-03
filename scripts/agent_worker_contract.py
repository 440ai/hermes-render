#!/usr/bin/env python3
"""Generate and check 440.ai portable agent-work contract prompts.

This helper is intentionally stdlib-only so it works in local repos, Render
shells, and worker launch wrappers without adding dependencies.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "agent-work" / "agent-contract.md"
ISSUE_RE = re.compile(r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)$")
ENGINES = {"hermes", "codex", "claude"}
ACTIVE_LABEL = "status: active"


@dataclass(frozen=True)
class IssueRef:
    owner: str
    repo: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"


def parse_issue_url(url: str) -> IssueRef:
    match = ISSUE_RE.match(url.strip())
    if not match:
        raise ValueError("issue URL must look like https://github.com/<owner>/<repo>/issues/<number>")
    return IssueRef(
        owner=match.group("owner"),
        repo=match.group("repo"),
        number=int(match.group("number")),
    )


def load_contract(path: Path = CONTRACT_PATH) -> str:
    return path.read_text(encoding="utf-8").strip()


def label_names(issue: dict[str, Any]) -> set[str]:
    labels = issue.get("labels", [])
    names: set[str] = set()
    for label in labels:
        if isinstance(label, str):
            names.add(label)
        elif isinstance(label, dict) and isinstance(label.get("name"), str):
            names.add(label["name"])
    return names


def fetch_issue(issue_url: str) -> dict[str, Any]:
    ref = parse_issue_url(issue_url)
    output = subprocess.check_output(
        [
            "gh",
            "issue",
            "view",
            str(ref.number),
            "-R",
            ref.slug,
            "--json",
            "url,title,state,labels",
        ],
        text=True,
    )
    return json.loads(output)


def load_issue_json(path: str | None, issue_url: str) -> dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return fetch_issue(issue_url)


def preflight_errors(issue: dict[str, Any], allow_active: bool = False) -> list[str]:
    errors: list[str] = []
    state = str(issue.get("state", "")).upper()
    if state and state != "OPEN":
        errors.append(f"issue is not open: {state}")
    labels = label_names(issue)
    if ACTIVE_LABEL in labels and not allow_active:
        errors.append("issue already has status: active; coordinator confirmation required")
    return errors


def closeout_errors(evidence: str, verification: str, blocker: str | None = None) -> list[str]:
    errors: list[str] = []
    if not evidence.strip():
        errors.append("evidence is required before closeout")
    if not verification.strip() and not blocker:
        errors.append("verification is required unless the issue is explicitly blocked")
    return errors


def build_worker_prompt(
    *,
    engine: str,
    issue_url: str,
    scope: str,
    non_goals: str,
    verification: str,
    secret_boundary: str,
    expected_evidence: str,
) -> str:
    if engine not in ENGINES:
        raise ValueError(f"engine must be one of: {', '.join(sorted(ENGINES))}")
    parse_issue_url(issue_url)
    contract = load_contract()
    engine_notes = {
        "hermes": "Use Hermes as the coordinator/default worker. Keep todos current and verify with tools.",
        "codex": "Use Codex as a bounded coding worker. Prefer an isolated git worktree for writes. Return diffs/tests/evidence; do not self-close the issue.",
        "claude": "Use Claude Code as a bounded coding/review worker. Prefer print mode for one-shot tasks and restrict tools where possible. Return evidence for Hermes verification.",
    }
    return f"""You are a 440.ai {engine} worker operating under the portable agent-work contract.

Issue URL: {issue_url}

Scope:
{scope.strip()}

Non-goals:
{non_goals.strip() or "- Do not broaden scope beyond the issue and coordinator instructions."}

Secret boundary:
{secret_boundary.strip() or "- Do not request, print, store, or commit raw secrets, passwords, 2FA codes, payment data, or unrestricted customer data."}

Verification plan:
{verification.strip()}

Expected evidence payload:
{expected_evidence.strip() or "- Summarize changed files, commands/tests run, relevant URLs, and any blockers."}

Engine-specific instruction:
{engine_notes[engine]}

If blocked by missing context, permissions, secrets, tooling, environment, or tests, stop and emit a structured blocker report. Do not invent results.

--- PORTABLE CONTRACT ---
{contract}
""".strip() + "\n"


def command_prompt(args: argparse.Namespace) -> int:
    print(
        build_worker_prompt(
            engine=args.engine,
            issue_url=args.issue_url,
            scope=args.scope,
            non_goals=args.non_goals,
            verification=args.verification,
            secret_boundary=args.secret_boundary,
            expected_evidence=args.expected_evidence,
        )
    )
    return 0


def command_preflight(args: argparse.Namespace) -> int:
    issue = load_issue_json(args.issue_json, args.issue_url)
    errors = preflight_errors(issue, allow_active=args.allow_active)
    print(f"Issue: {issue.get('url', args.issue_url)}")
    print(f"Title: {issue.get('title', '<unknown>')}")
    print(f"Labels: {', '.join(sorted(label_names(issue))) or '<none>'}")
    if errors:
        print("Preflight: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("Preflight: ok")
    print("Next: add status: active, set Project Coordination Status = Active, and post a start note.")
    return 0


def command_closeout(args: argparse.Namespace) -> int:
    parse_issue_url(args.issue_url)
    errors = closeout_errors(args.evidence, args.verification, args.blocker)
    if errors:
        print("Closeout: blocked")
        for error in errors:
            print(f"- {error}")
        return 2
    print("Closeout: ok")
    print("Checklist:")
    print("- Evidence attached")
    print("- Verification or blocker documented")
    print("- Follow-up bugs/tooling gaps filed")
    print("- Project status moved to Review, Done, or Blocked")
    print("- status: active can be removed after coordinator verification")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    prompt = sub.add_parser("prompt", help="render a portable worker prompt")
    prompt.add_argument("--engine", required=True, choices=sorted(ENGINES))
    prompt.add_argument("--issue-url", required=True)
    prompt.add_argument("--scope", required=True)
    prompt.add_argument("--non-goals", default="")
    prompt.add_argument("--verification", required=True)
    prompt.add_argument("--secret-boundary", default="")
    prompt.add_argument("--expected-evidence", default="")
    prompt.set_defaults(func=command_prompt)

    preflight = sub.add_parser("preflight", help="check whether a worker can start")
    preflight.add_argument("--issue-url", required=True)
    preflight.add_argument("--issue-json", help="local gh-style issue JSON for offline checks")
    preflight.add_argument("--allow-active", action="store_true", help="allow work on an already-active issue")
    preflight.set_defaults(func=command_preflight)

    closeout = sub.add_parser("closeout", help="check whether a worker can be closed out")
    closeout.add_argument("--issue-url", required=True)
    closeout.add_argument("--evidence", default="")
    closeout.add_argument("--verification", default="")
    closeout.add_argument("--blocker", help="explicit blocker classification if verification cannot run")
    closeout.set_defaults(func=command_closeout)

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
