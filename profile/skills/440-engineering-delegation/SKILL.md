---
name: 440-engineering-delegation
description: "Use when Slack Hermes receives engineering work. Route implementation, testing, browser QA, and deploys to Codex first, then verify before reporting."
version: 1.0.0
---

# 440 Engineering Delegation

Use this skill when a Slack request involves code, tests, previews, browser QA, auth/debugging, deployments, production infrastructure, or GitHub PRs.

## Default Delegate

Default engineering delegate: Codex.

Claude can be added later for second-opinion review, product copy, or implementation alternatives. Until then, do not invent a Claude handoff path unless the tool is actually available.

## Parent Hermes Responsibilities

The Slack-facing parent Hermes owns:

- Intake and scoping.
- Decision questions back to the user.
- Engineering work-order quality.
- Verification of returned evidence.
- Final Slack reporting.

The parent does not dump terminal output or implementation chatter into Slack.

## Codex Work Order

When handing work to Codex, include:

```text
Objective:
Repo/path:
Relevant files/links:
Constraints:
User-facing behavior:
Tests/checks expected:
Screenshots/browser checks expected:
Commit/PR expectations:
Return format:
```

## Verification Gate

Before reporting done in Slack, verify the strongest available evidence:

- Git status, branch, commit, PR, or issue handles.
- Test command output.
- Browser/preview screenshots or E2E checks for UI work.
- Render/Vercel deploy status and health endpoints for deploy work.
- Logs when debugging production behavior.

If evidence is missing or too narrow, say that explicitly and keep the task open.
