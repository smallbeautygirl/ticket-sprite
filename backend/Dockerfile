# Claude Code CLI for single-user mode (LLM_MODE=claude_code). The npm package's
# postinstall drops a self-contained native binary; only that binary is kept.
FROM node:22-slim AS claude
ARG CLAUDE_CODE_VERSION=2.1.278
RUN npm install -g --no-audit --no-fund "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"

FROM python:3.12-slim

# git: the Knowledge Source is a dedicated clone kept fresh with `git pull` (ADR-0002)
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'

COPY --from=claude /usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe /usr/local/bin/claude
# Single-user mode runs as the owner's uid with HOME here and their ~/.claude mounted in
RUN mkdir -p /home/owner && chmod 1777 /home/owner

WORKDIR /app
COPY pyproject.toml ./
COPY ticket_sprite ./ticket_sprite
RUN pip install --no-cache-dir .

ENV KNOWLEDGE_ROOT=/data/knowledge UPLOAD_DIR=/data/uploads
EXPOSE 8000
CMD ["uvicorn", "ticket_sprite.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
