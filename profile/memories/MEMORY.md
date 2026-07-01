440.ai GitHub org is `440ai`. Primary production repo in this profile is `/workspace/vercel-nextjs-monorepo`.

440.ai current engineering focus includes org-scoped HubSpot OAuth/sync, in-app AI copilot, DuckDB/MotherDuck analytics exploration, and Hermes as an agent backend.

440.ai Hermes topology separates Kevin's local workstation Hermes, internal Hermes Slack gateway, and customer-facing Hermes agent backend.

The internal Hermes Slack gateway should run from the checked-in profile under `profile/` in `440ai/hermes-agent-gateway-slack` and must keep Slack user/channel restrictions plus authenticated dashboard access in place before production restoration.

Slack Hermes should operate as a chief-of-staff concierge: keep Slack threads clean, delegate noisy detailed work to subagents, and return concise answers, decisions, blockers, and verified results.

PM/research/documentation work is a first-class lane for Slack Hermes and should be handled now; coding, preview QA, auth-bound E2E, and deployment/test execution are a separate engineering lane unless explicitly requested.
