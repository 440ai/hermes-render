---
name: 440-agent-ops-escalation
description: "Use whenever an agent hits missing access, broken tooling, MCP/connector gaps, environment bugs, unclear ownership, repeated failure, or a tempting workaround. Raise an agent-ops GitHub issue instead of hiding the system problem."
version: 1.0.0
---

# 440 Agent Ops Escalation

Use this skill when any role cannot complete work correctly because the agent system is missing something or something has gone wrong.

## Trigger Conditions

Escalate when any of these are true:

- Missing access, login, permission, repo, channel, credential, or account.
- Missing MCP, connector, browser/computer-use capability, API key, or tool.
- Tool exists but fails, times out, returns incomplete data, or behaves inconsistently.
- Tests, deploys, previews, shells, or browser automation fail because of environment setup.
- The correct durable home for information is unclear.
- A task needs a new repeatable workflow, profile rule, skill, MCP gateway tool, or runbook.
- A workaround would hide the underlying system problem.

## Required Behavior

- Do not silently drop the task.
- Do not pretend a narrower check proves the broader outcome.
- Do not create a workaround that masks the missing capability or bug.
- Try one reasonable verification or fallback if it can clarify the failure.
- If the proper fix is outside the current role's authority, create or update a GitHub issue for Agent Ops.

## Issue Home

Default issue repo: `440ai/hermes-render`.

Use GitHub issues for task/project notes, setup requests, tool gaps, and bug reports. Use repo docs only for stable architecture, runbooks, and static reference material.

## Issue Shape

```text
Title: [agent-ops] <short blocker or capability gap>

Needed outcome:
Role/task blocked:
What failed:
Evidence:
Impact:
Proper fix:
Workaround avoided:
Owner/next step:
```

## Slack Report

Keep Slack concise:

```text
Blocked: <one sentence>

Raised:
- <GitHub issue link>

Next:
- <what Agent Ops or the user needs to provide/decide>
```

If GitHub issue creation itself fails, report that explicitly and include the issue body for a human to file.
