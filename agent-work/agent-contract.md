# 440.ai portable agent work contract

This contract applies to Hermes, Codex, Claude Code, and any subagent/worker operating on 440.ai work.

Hermes is the default coordinator and verification owner. Codex and Claude Code are specialized worker engines whose outputs are self-reports until verified by Hermes or a human coordinator.

## 1. Source of truth

Every non-trivial task must have one authoritative GitHub issue and, when available, a `440 Mission Control` Project item.

Required metadata:

- Mission: Agent Ops, Dev Ops, Product, GTM, or Executive.
- Owner/Profile: `executive`, `agent-ops`, `dev-ops`, `product`, or `gtm`.
- Scope and non-goals.
- Desired outcome.
- Source links: issue, repo, PR, Slack permalink, deploy, logs, meeting note, or runbook.
- Verification plan.
- Done criteria.

Do not create repo-local task boards for operational tracking.

## 2. Start-work lock

Before starting:

1. Read the issue and latest comments.
2. Check whether the issue already has `status: active`.
3. If `status: active` is already present, stop and ask the coordinator before duplicating work.
4. If taking ownership, add `status: active` and set Project `Coordination Status = Active` when possible.
5. Post a short start note with scope, non-goals, secret boundary, verification plan, and expected evidence.

## 3. Worker prompt requirements

A worker prompt must include:

- Issue URL.
- Bounded scope.
- Non-goals.
- Secret boundary.
- Allowed tools/permission level.
- Expected evidence payload.
- Verification plan.
- Instruction to stop with a structured blocker report if access/tooling/context is missing.

The worker must not broaden scope, invent results, ask for secrets in chat, or claim success without evidence.

## 4. Secret boundary

Agents must never request or store raw passwords, API keys, 2FA codes, payment data, or production customer secrets in chat, issue comments, commits, or logs.

Use managed platform auth flows, secret stores, environment variables, or user-completed auth steps instead.

Evidence must redact secrets and sensitive raw customer data.

## 5. Blocker taxonomy

Classify blockers explicitly:

- `needs-human-decision`: product/process choice or ambiguous owner.
- `needs-permission`: OAuth scope, GitHub/Slack/Vercel/Render access, or platform role.
- `needs-secret`: secret/token required; the agent must not receive it in chat.
- `needs-tooling`: CLI, MCP, plugin, profile, wrapper, or automation missing/broken.
- `needs-environment`: service, dependency, database, fixture, deploy, or local runtime unavailable.
- `needs-context`: missing source link, unclear history, or insufficient project instructions.
- `external-blocked`: vendor outage, rate limit, or external dependency.
- `test-blocked`: verification path unavailable; explain concrete blocker and substitute evidence.

A blocker report must include what was tried, exact non-secret evidence, why it blocks the outcome, the smallest human/tooling action needed, and safe alternatives.

## 6. Bug discipline

Treat repeated problems as bugs in one of:

- product/system behavior;
- process/design;
- permissions/access;
- tooling/automation;
- documentation/context;
- test coverage/verification.

For repeated failures, flaky workflows, missing auth scopes, unclear handoffs, brittle scripts, or bad docs, file/update an issue with:

- expected behavior;
- actual behavior;
- reproduction steps or command;
- evidence, with secrets redacted;
- root-cause hypothesis;
- proposed fix;
- verification/regression check.

Do not repeatedly coach around the same failure. Fix the system, wrapper, runbook, profile, or test.

## 7. Engine roles

### Hermes

Use as coordinator/default worker for:

- mission routing and Project updates;
- Slack/company context;
- memory/skills/runbook maintenance;
- permission/tooling triage;
- verification of worker claims;
- durable background jobs and profile-owned work.

### Codex

Use as specialized coding worker for:

- isolated implementation in a git worktree;
- refactors and batch issue fixing;
- PR review or codebase edits where Codex is the best fit.

Default constraints:

- require an issue URL;
- prefer clean worktree isolation for writes;
- no production secrets;
- Hermes verifies diffs/tests before PR or issue claims.

### Claude Code

Use as specialized coding/review worker for:

- deep codebase reasoning;
- multi-file refactors;
- security/code review;
- iterative tmux coding sessions when useful.

Default constraints:

- prefer `claude -p` for bounded one-shot work;
- use allowed-tool restrictions when possible;
- inject this contract into prompts/context;
- Hermes verifies output and cleans up sessions.

## 8. Closeout gate

Before removing `status: active`, verify:

- outcome is complete or blocker is explicitly classified;
- evidence is attached;
- tests/checks ran, or `test-blocked` explains why not;
- follow-up bugs/tooling gaps are filed;
- Project status is moved to Review, Blocked, or Done;
- no secrets or sensitive raw data were exposed;
- handoff is short and actionable.
