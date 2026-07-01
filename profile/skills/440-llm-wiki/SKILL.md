---
name: 440-llm-wiki
description: Use the 440 LLM wiki as the Git-backed corporate memory for Hermes and future agents. Use when a task needs durable company context, wiki updates, memory hygiene, source-backed internal knowledge, or a distinction between task issues and stable memory.
---

# 440 LLM Wiki

The 440 LLM wiki is the agent-maintained corporate memory vault.

## Location

- Runtime workspace: `/workspace/llm-wiki`
- GitHub repo: `440ai/llm-wiki`
- Canonical branch: `main`
- Legacy `440ai/wiki` content was imported into `90-sources/440ai-wiki/`; use `440ai/llm-wiki` going forward.

If `/workspace/llm-wiki` is missing, stale, or inaccessible, escalate to Agent Ops and file/update an issue in `440ai/hermes-render`.

## When To Read

Read the LLM wiki when a task depends on:

- Durable company memory.
- Product, GTM, customer, or operating context.
- Prior decisions or rationale.
- Agent workflow conventions.
- Sensitive-memory handling rules.

Start with:

1. `/workspace/llm-wiki/AGENTS.md`
2. `/workspace/llm-wiki/WIKI_SCHEMA.md`
3. `/workspace/llm-wiki/index.md`

Search before creating or updating notes.

## When To Write

Write to the LLM wiki only for durable, source-backed memory that future agents should reuse.

Do not use the LLM wiki for:

- Active project/task tracking.
- Bug reports.
- Follow-up lists.
- Deployment TODOs.
- Short-lived notes.

Those belong in GitHub issues, usually in `440ai/hermes-render` unless another repo clearly owns the work.

## Write Rules

- Preserve provenance with links to issues, PRs, repo paths, docs, Slack permalinks, browser sources, or meeting artifacts.
- Mark uncertainty directly.
- Use the schema in `WIKI_SCHEMA.md`.
- Keep notes small and link related notes.
- Avoid direct commits for meaningful changes unless explicitly instructed; prefer branch and PR.

## Security Rules

Never store:

- API keys, OAuth material, tokens, cookies, private keys, or credentials.
- Raw private Slack exports.
- Raw customer CRM exports.
- Payment details or personal contact/payment identifiers.
- Unreviewed claims about customers, employees, finances, or security posture.

Use sanitized summaries and source links when the source is authorized.

Ask Security to review restricted or customer-adjacent memory before broad reuse.

## Escalation

Escalate to Agent Ops when:

- The wiki repo, branch, or working copy is missing.
- A needed source cannot be accessed.
- Ownership or sensitivity is unclear.
- Existing notes conflict and no authoritative source resolves the conflict.
- A repeatable memory workflow or tool is missing.
