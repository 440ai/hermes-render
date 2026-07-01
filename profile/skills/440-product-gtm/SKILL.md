---
name: 440-product-gtm
description: "Use for 440.ai product-management and go-to-market work: customer synthesis, specs, decision records, competitor research, positioning, and content briefs."
version: 1.0.0
---

# 440 Product And GTM

Use this skill for product-management, customer-discovery, research, positioning, and go-to-market work.

Role profiles:

- Product Manager: `/opt/data/roles/product-manager.md`
- GTM: `/opt/data/roles/gtm.md`

## Product Management

Create durable artifacts that help decide what to build:

- Customer/problem summaries.
- Product briefs.
- Decision records.
- Issue/spec drafts.
- Acceptance criteria.
- Dedupe and readiness checks.
- Engineering handoffs.

Separate "what should be true for the user/customer" from "how engineering should implement it." If implementation is needed, hand off to the engineering lane with clear acceptance criteria and verification.

## Go To Market

Create durable artifacts that help decide what to say and where to sell:

- Competitor and category research.
- Positioning and messaging briefs.
- Audience hypotheses.
- Campaign/ad/content drafts.
- Sales research summaries.
- Landing-page copy briefs.

Mark assumptions clearly. Cite source links or internal source paths when claims matter.

Use `440-agent-ops-escalation` when PM/GTM work is blocked by missing source access, missing research/browser/docs tools, broken analytics connectors, or unclear durable-home conventions.

## Delegation

Use subagents for noisy research and review:

- One subagent for external/web research when sources matter.
- One subagent for internal docs/wiki/repo context.
- One subagent to critique the draft against the intended audience or decision.

Return a concise synthesis to Slack. Put long-form notes in the wiki or a linked artifact.
