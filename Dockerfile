# syntax=docker/dockerfile:1.7
#
# Hermes Agent on Render, pre-baked with Render tooling.
#
# Extends the upstream NousResearch/hermes-agent image with:
#   - A bundle of Render-focused skills mounted via skills.external_dirs
#   - A boot-time patcher that registers the Render MCP server in
#     config.yaml (idempotent; never overwrites user edits)
#
# We deliberately do NOT install the `render` CLI. This image is configured
# around the Render MCP server; installing extra CLIs should be a conscious
# operator choice, not something the agent does as an automatic fallback.
#
# Pin the upstream tag here. Bump and redeploy to upgrade Hermes.
ARG HERMES_IMAGE=docker.io/nousresearch/hermes-agent:v2026.6.19
FROM ${HERMES_IMAGE}

USER root

# Pull the official Render skill bundle from github.com/render-oss/skills
# at a pinned commit. Mounted via skills.external_dirs at boot, so the
# upstream Hermes skills-sync flow never touches these files. To upgrade,
# bump RENDER_SKILLS_REF (a commit SHA, tag, or branch) and rebuild.
ARG RENDER_SKILLS_REPO=render-oss/skills
ARG RENDER_SKILLS_REF=1b8496570748203351f628b2ae738805ac2c23d5
RUN set -eu; \
    tmp="$(mktemp -d)"; \
    url="https://codeload.github.com/${RENDER_SKILLS_REPO}/tar.gz/${RENDER_SKILLS_REF}"; \
    curl -fsSL --retry 3 -o "${tmp}/skills.tar.gz" "${url}"; \
    tar -xzf "${tmp}/skills.tar.gz" -C "${tmp}"; \
    extracted="$(find "${tmp}" -maxdepth 2 -type d -name 'skills' | head -n 1)"; \
    test -n "${extracted}" || { echo "could not find skills/ in tarball" >&2; exit 1; }; \
    install -d -o hermes -g hermes -m 0755 /opt/render-tools/skills-upstream; \
    cp -a "${extracted}/." /opt/render-tools/skills-upstream/; \
    chown -R hermes:hermes /opt/render-tools/skills-upstream; \
    rm -rf "${tmp}"; \
    echo "${RENDER_SKILLS_REPO}@${RENDER_SKILLS_REF}" > /opt/render-tools/skills-upstream/.source

# Local overlay: a Hermes-specific `render-on-hermes` skill that tells
# the agent the MCP server is pre-wired (so skip "install MCP" from
# upstream skills) and that the CLI is deliberately absent (so don't
# try to invoke it). Listed FIRST in skills.external_dirs so same-named
# overlays would shadow upstream entries.
COPY --chown=hermes:hermes skills/ /opt/render-tools/skills-local/

# Internal 440.ai Slack gateway profile. This is copied into the persistent
# HERMES_HOME disk on boot by the Render cont-init hook. The custom dashboard
# auth provider also needs to live in Hermes' runtime plugin path so the
# dashboard can import it before user-managed plugins are loaded from disk.
COPY --chown=hermes:hermes profile/ /opt/hermes-profile/
COPY --chown=root:root profile/plugins/dashboard_auth/allowlisted_oidc/ /opt/hermes/plugins/dashboard_auth/allowlisted_oidc/
COPY --chown=root:root config.yaml /opt/hermes-profile/config.yaml

# Boot-time wrapper: patches /opt/data/config.yaml, then hands off to
# the upstream Hermes s6 startup path. This runs after the upstream
# config seeding hook and before dashboard/gateway services start.
COPY --chown=root:root scripts/bootstrap.sh /etc/cont-init.d/016-render-tools
COPY --chown=root:root scripts/00-internal-profile.sh /etc/cont-init.d/00-internal-profile
COPY --chown=root:root scripts/patch-config.py /opt/render-tools/patch-config.py
COPY --chown=root:root scripts/prepare-internal-profile.sh /opt/render-tools/prepare-internal-profile.sh
RUN test -f /opt/hermes/plugins/dashboard_auth/allowlisted_oidc/plugin.yaml \
    && chmod 0755 /etc/cont-init.d/00-internal-profile \
        /etc/cont-init.d/016-render-tools \
        /opt/render-tools/patch-config.py \
        /opt/render-tools/prepare-internal-profile.sh

# Pre-create the dir the patcher writes to so chown works cleanly on
# first boot. The mounted disk replaces this empty dir at runtime;
# baking it just keeps the image self-contained for any non-disk use.
RUN install -d -o hermes -g hermes -m 0755 /opt/data /workspace

ENV HERMES_HOME=/opt/data \
    HERMES_PROFILE_SOURCE=/opt/hermes-profile \
    HERMES_OVERWRITE_PROFILE=0 \
    HERMES_OVERWRITE_CONFIG=1 \
    HERMES_WORKSPACE_ROOT=/workspace \
    HERMES_WORKSPACE_REPO=https://github.com/440ai/vercel-nextjs-monorepo.git \
    HERMES_WORKSPACE_REF=main \
    HERMES_WORKSPACE_AUTO_UPDATE=1

WORKDIR /workspace
CMD ["gateway", "run", "--accept-hooks"]
