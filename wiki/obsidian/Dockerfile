FROM lscr.io/linuxserver/obsidian:latest

USER root

RUN if command -v apt-get >/dev/null 2>&1; then \
      apt-get update && \
      apt-get install -y --no-install-recommends git ca-certificates openssh-client && \
      rm -rf /var/lib/apt/lists/*; \
    elif command -v apk >/dev/null 2>&1; then \
      apk add --no-cache git ca-certificates openssh-client; \
    fi

COPY init-llm-wiki.sh /custom-cont-init.d/10-init-llm-wiki
RUN chmod +x /custom-cont-init.d/10-init-llm-wiki
