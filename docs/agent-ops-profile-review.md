# Agent Ops Profile Review

This note captures the initial 440.ai Slack Hermes profile setup decisions.

## Runtime Role

Slack Hermes is the parent concierge for internal 440 work. It should keep Slack clean and use subagents for noisy investigation, drafting, research, engineering execution, QA, and tool-heavy work.

Slack should contain:

- Answers and concise synthesis.
- Decisions or approvals needed from humans.
- Material blockers.
- Verified final outcomes with links or handles.

Slack should not contain:

- Skill-read notices.
- File-search narration.
- Subagent scratch work.
- Raw tool output unless requested.
- Routine command logs.

## Work Lanes

- Chief-of-staff: notes, daily writeups, wiki updates, task lists, follow-ups, decision logs.
- Product management: customer/problem synthesis, product briefs, prioritization, specs, acceptance criteria, GitHub issue drafts.
- Go-to-market: competitor research, positioning, audience hypotheses, ad/content drafts, campaign briefs.
- Engineering: code, tests, browser QA, preview verification, deploys, production debugging. Default delegate is Codex; add Claude later.
- Agent-ops: memory, docs, MCP/tool inventory, delegation rules, compression, security, behavior consistency.

## Tool And MCP Review

Currently baked into this Render Hermes deployment:

- Render MCP through `mcp_servers.render`.
- Render skill bundle plus the local `render-on-hermes` overlay.
- Slack gateway through env-configured Socket Mode tokens and channel/user allowlists.
- Terminal backend `local` with `/workspace` as the root.
- Boot-cloned repos for product app, wiki, and old gateway context.
- Clerk/OIDC dashboard auth with Hermes-side allowed-email checks.

Recommended next tool work:

- Add a dedicated MCP gateway for reusable shared tools before customer-facing agents exist.
- Add or verify GitHub MCP access for issues, PRs, comments, and repo search instead of relying only on shell/git.
- Add Google Drive/Docs/Sheets tooling for chief-of-staff notes and durable docs.
- Add browser automation and computer-use tooling for web research, screenshots, and auth-bound QA.
- Add Vercel tooling for product preview/deploy checks.
- Add PostHog/product analytics tooling when product usage data matters.
- Keep customer-facing agents on separate deployments or tenant-scoped tools; do not reuse this internal broad-authority instance.

## Terminal Backend

Keep `terminal.backend: local` and `terminal.cwd: /workspace` for now. The boot hook clones the expected repos into `/workspace`, which keeps file and shell tools predictable.

Do not use the Slack-facing parent as the main implementation surface for engineering. Route engineering work to Codex and have the parent verify returned evidence before reporting completion.

## Delegation

Current config:

- `max_concurrent_children: 4`
- `max_spawn_depth: 2`
- `orchestrator_enabled: true`
- `subagent_auto_approve: false`

This is appropriate for an internal startup assistant: enough concurrency for research/review split work, but not enough fanout to lose control. Keep the parent Hermes responsible for Slack communication and verification.

## Compression And Output

The profile now bakes in:

- `compression.codex_gpt55_autoraise: false`
- `display.tool_progress: off`
- `display.tool_progress_command: false`
- `display.interim_assistant_messages: false`

This matches the Slack concierge goal: no automatic context-window notices or progress spam in user threads.

## Security

Launch gates:

- Dashboard must remain behind Clerk/OIDC plus the allowed-email policy.
- Slack must require both allowed users and allowed channels.
- Secrets stay in Render env vars or the authenticated Hermes dashboard, not repo files or memory.
- `RENDER_MCP_API_KEY` should be a deliberate Render API key for Hermes. Prefer a least-privileged Render user/key when Render supports the needed role boundary.
