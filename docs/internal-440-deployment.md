# 440 Internal Hermes on Render

This repo deploys the internal 440.ai Hermes instance on Render. It is for the 440 team, not for customer-facing product traffic.

## Boundaries

- Internal Slack Hermes: company assistant, Slack gateway, Render MCP, GitHub/repo operations, internal memories.
- Customer Hermes: separate future backend with tenant-scoped tools only.
- Kevin local Hermes: personal workstation state only.

Do not reuse this instance for customers. Do not put customer CRM data, internal Slack history, broad GitHub credentials, or Render account authority behind a customer-facing chat surface.

## Render Service

- Service name: `hermes-internal`
- Runtime: Docker web service
- Plan: `standard`
- Disk: `/opt/data`, 5 GB
- Dashboard URL: `https://ha.440.ai`
- Health check: `/api/status`

The Docker image keeps the upstream Hermes s6 entrypoint. A 440 startup hook patches the seeded config with:

- Render MCP server at `https://mcp.render.com/mcp`
- Render skill bundles under `/opt/render-tools`
- allowlisted Clerk/OIDC dashboard auth defaults

## Required First Deploy Env

Set these in Render before adding model/provider keys:

```text
HERMES_DASHBOARD_ALLOWLISTED_OIDC_CLIENT_ID
HERMES_DASHBOARD_ALLOWLISTED_OIDC_CLIENT_SECRET
```

The Blueprint already sets:

```text
HERMES_DASHBOARD=1
HERMES_DASHBOARD_HOST=0.0.0.0
HERMES_DASHBOARD_PORT=10000
HERMES_DASHBOARD_PUBLIC_URL=https://ha.440.ai
HERMES_DASHBOARD_OIDC_ISSUER=https://clerk.440.ai
HERMES_DASHBOARD_ALLOWLISTED_OIDC_SCOPES=profile email
HERMES_DASHBOARD_ALLOWED_EMAILS=hello@kevinwalsh.co,k@440.ai,scott@440.ai,sjtousley@gmail.com
```

The Clerk OAuth/OIDC app must allow:

```text
https://ha.440.ai/auth/callback
```

## Verification

1. Check that the dashboard requires auth:

   ```bash
   curl -s https://ha.440.ai/api/status | jq '.auth_required, .auth_providers'
   ```

2. Confirm an allowlisted 440 user can sign in through Clerk.
3. Confirm a non-team user cannot sign in or cannot reach dashboard pages.
4. Add provider/model keys only after auth is verified.
5. Add Slack tokens and allowlists:

   ```text
   SLACK_BOT_TOKEN
   SLACK_APP_TOKEN
   SLACK_ALLOWED_USERS
   SLACK_ALLOWED_CHANNELS
   ```

6. DM the Hermes Slack app with `help`.
7. Mention Hermes in the internal channel with `help`.
8. Ask Hermes from the dashboard chat to list Render services and confirm it calls the Render MCP tool.

## Secrets

Keep all secrets in Render env vars or the authenticated Hermes dashboard. Do not commit `.env`, OAuth token files, session dumps, or copied API keys.
