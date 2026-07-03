# Agent work enforcement

This directory is the portable contract layer for 440.ai agent work across Hermes, Codex, and Claude Code.

Use it when launching or closing any non-trivial agent task.

## Source of truth

- Operating design: <https://github.com/440ai/hermes-render/issues/17>
- First implementation slice: <https://github.com/440ai/hermes-render/issues/18>
- Operating board: <https://github.com/orgs/440ai/projects/3>

## Files

- [`agent-contract.md`](agent-contract.md) — the common contract to inject into worker prompts.
- [`templates/`](templates/) — GitHub comment templates for start, blockers, permission/tooling requests, bug/root-cause reports, and done handoffs.
- [`../scripts/agent_worker_contract.py`](../scripts/agent_worker_contract.py) — local prompt/preflight/closeout helper for Hermes, Codex, and Claude Code workers.
- [`../scripts/agent_worker_launch.py`](../scripts/agent_worker_launch.py) — enforced launch wrapper that runs preflight, saves prompt/output artifacts, and dry-runs or executes a bounded worker launch.

## Required loop

1. Confirm the GitHub issue/Project item is the source of truth.
2. Check for `status: active`; do not duplicate active work without coordinator confirmation.
3. Add `status: active` and set Project `Coordination Status = Active` when taking ownership.
4. Give the worker the portable contract, bounded scope, non-goals, secret boundary, and verification path.
5. Treat worker output as self-report until Hermes verifies files, diffs, tests, URLs, or command output.
6. If blocked, classify the blocker and file/update the bug/tooling issue instead of working around it repeatedly.
7. Remove `status: active` only after evidence-backed closeout.

## Enforced launch wrapper

Prefer the wrapper over hand-copying prompts. It runs preflight first, requires
the permission/tool boundary, writes a prompt artifact, and defaults to dry-run:

```bash
python scripts/agent_worker_launch.py \
  --engine codex \
  --issue-url https://github.com/440ai/hermes-render/issues/18 \
  --scope "Implement the portable contract templates and local checks" \
  --non-goals "Do not add secrets or broad production credentials" \
  --permission-boundary "Read-only unless coordinator explicitly grants workspace-write" \
  --verification "Run unit tests for the helper and dry-run launch wrapper" \
  --expected-evidence "Prompt path, output path, changed files, and test output"
```

Add `--execute` only after reviewing the dry-run command. Codex defaults to a
read-only sandbox. Claude Code can be checked without launching model work:

```bash
python scripts/agent_worker_launch.py \
  --engine claude \
  --issue-url https://github.com/440ai/hermes-render/issues/18 \
  --scope "Read-only review" \
  --non-goals "Do not modify files" \
  --permission-boundary "Claude allowed tools: Read" \
  --verification "Hermes verifies Claude output before acting" \
  --expected-evidence "Review findings with file references" \
  --check-claude-auth
```

If Claude is not authenticated, the wrapper writes a structured
`needs-permission` blocker instead of launching.

## Manual prompt generation

```bash
python scripts/agent_worker_contract.py prompt \
  --engine codex \
  --issue-url https://github.com/440ai/hermes-render/issues/18 \
  --scope "Implement the portable contract templates and local checks" \
  --non-goals "Do not add secrets or broad production credentials" \
  --verification "Run unit tests for the helper and dry-run prompt generation"
```

Manual prompt generation is still available for inspection and tests. For real
worker launches, use `agent_worker_launch.py` so preflight and artifacts are not
skipped.
