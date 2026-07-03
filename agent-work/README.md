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

## Required loop

1. Confirm the GitHub issue/Project item is the source of truth.
2. Check for `status: active`; do not duplicate active work without coordinator confirmation.
3. Add `status: active` and set Project `Coordination Status = Active` when taking ownership.
4. Give the worker the portable contract, bounded scope, non-goals, secret boundary, and verification path.
5. Treat worker output as self-report until Hermes verifies files, diffs, tests, URLs, or command output.
6. If blocked, classify the blocker and file/update the bug/tooling issue instead of working around it repeatedly.
7. Remove `status: active` only after evidence-backed closeout.

## Example prompt generation

```bash
python scripts/agent_worker_contract.py prompt \
  --engine codex \
  --issue-url https://github.com/440ai/hermes-render/issues/18 \
  --scope "Implement the portable contract templates and local checks" \
  --non-goals "Do not add secrets or broad production credentials" \
  --verification "Run unit tests for the helper and dry-run prompt generation"
```

Use the generated prompt as the task body for Hermes delegation, `codex exec`, or `claude -p`.
