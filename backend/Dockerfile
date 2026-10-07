FROM python:3.12-slim

# git: the Knowledge Source is a dedicated clone kept fresh with `git pull` (ADR-0002)
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'

WORKDIR /app
COPY pyproject.toml ./
COPY ticket_sprite ./ticket_sprite
RUN pip install --no-cache-dir .

ENV KNOWLEDGE_ROOT=/data/knowledge UPLOAD_DIR=/data/uploads
EXPOSE 8000
CMD ["uvicorn", "ticket_sprite.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
