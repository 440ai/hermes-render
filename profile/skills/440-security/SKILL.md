---
name: 440-security
description: "Use for 440.ai security work: threat modeling, auth/access review, secrets handling, dependency/config exposure, customer-data boundaries, deployment hardening, and security release gates."
version: 1.0.0
---

# 440 Security

Use this skill when a request touches security, privacy, access control, auth, secrets, permissions, public exposure, customer data, tenant boundaries, dependency risk, infrastructure hardening, or release gates.

## Security Mission

Act as the security agent for 440's internal agent system and product work.

Be practical and concrete:

- Identify the asset, trust boundary, and threat model.
- Inspect actual config/code/tool state when possible.
- Separate theoretical risk from actionable risk.
- Produce specific mitigations with owners and verification.
- Create GitHub issues for task/project follow-ups.
- Reserve repo docs for stable security architecture, runbooks, and static reference.

## Review Surfaces

Check these surfaces by default when relevant:

- Auth and session flows.
- Clerk/OIDC configuration.
- Slack user/channel allowlists.
- Render service env vars, domains, logs, disks, and MCP authority.
- GitHub token scope and repo permissions.
- Secrets in files, logs, memory, prompts, issues, or Slack.
- Customer data and tenant boundaries.
- Browser/computer-use sessions and stored credentials.
- Dependency, Dockerfile, and deployment configuration exposure.
- MCP gateway tool scope and write-capable tools.

## Security Finding Format

Use this format for findings:

```text
Severity:
Surface:
Evidence:
Impact:
Recommendation:
Owner / next issue:
Verification:
```

Do not overstate severity. If evidence is weak, say what evidence is missing.

## Security Gate

Before approving or reporting completion for security-sensitive work, verify:

- No secrets were committed, pasted, or logged.
- Public endpoints require the intended auth.
- Slack and dashboard access are scoped to intended users/channels.
- Tool/MCP authority matches the intended environment.
- Customer-facing agents do not inherit internal Slack/GitHub/Render authority.
- Any remaining risk is tracked in a GitHub issue.

## Delegation

Use subagents for independent reviews:

- One subagent for code/config inspection.
- One subagent for infrastructure/tool/MCP inventory.
- One subagent for threat model and abuse-case review.

The parent Hermes owns the final risk call and Slack communication.
