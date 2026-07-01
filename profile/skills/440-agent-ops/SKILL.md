---
name: 440-agent-ops
description: "Use for improving and governing the 440 agent operating system: memory, docs, MCP/tool inventory, delegation rules, compression, security, and behavior consistency."
version: 1.0.0
---

# 440 Agent Ops

Use this skill when the task is about the agent system itself: behavior, memory, documentation conventions, MCP/tool coverage, delegation rules, compression, security boundaries, or tool-output hygiene.

## Standing Mission

Keep the agent system constrained, useful, and consistent as it grows.

Be concrete and operational:

- Propose profile/config/skill changes.
- Write standards into the wiki or repo.
- Identify missing MCPs/connectors/tools.
- Create setup requests with exact names and reasons.
- Review whether agents have the access they need.
- Reduce Slack noise and tool-output clutter.

## Memory And Docs

Use three durable layers:

- Hermes memory: stable user/team preferences and operating rules.
- Wiki/docs: standards, decisions, playbooks, and strategy.
- GitHub issues/PRs: executable work and reviewable changes.

Do not store secrets in memory or docs.

## Tool And MCP Review

For each capability area, decide whether it is available, missing, or intentionally out of scope:

- Slack.
- GitHub.
- Render.
- Google Drive/Docs/Sheets/Slides.
- Browser automation.
- Computer use.
- Web search.
- Vercel/product deployment.
- PostHog/product analytics.
- Dedicated MCP gateway for shared/customer-safe tools.
- Engineering delegation to Codex, and later Claude.

When a missing tool blocks useful work, state the exact connector/MCP needed and whether it belongs on this internal Hermes instance or a future dedicated MCP gateway.

## Security And Boundaries

Default posture:

- Internal Hermes can have broad company tools only behind strict Slack/dashboard auth.
- Customer-facing agents must be separate deployments or tenant-scoped services with narrow tools.
- Do not reuse internal Slack/GitHub/Render authority for customer surfaces.
- Treat Render, GitHub, Clerk, provider keys, and browser sessions as production-adjacent.

## Compression And Slack Output

Keep long work off Slack. Prefer subagent summaries and durable artifacts.

Avoid automatic informational notices and interim assistant chatter unless they help the user make a decision. If a config setting creates Slack noise, prefer a checked-in config/profile change over one-off manual commands.
