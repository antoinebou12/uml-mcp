# Default image command: FastAPI + Swagger/ReDoc + Streamable HTTP MCP at /mcp (agent-friendly).
# Stdio MCP: docker run ... python server.py --transport stdio
# Smithery overrides the container command with python server.py (see smithery.yaml).
# Enterprise SSO (Entra ID / OAuth 2.1): set MCP_AUTH_* env vars, see docs/enterprise/README.md.
# Runtime image tracks latest supported CPython (3.14). CI tests 3.12 and 3.14.
FROM python:3.14-slim

LABEL org.opencontainers.image.title="uml-mcp" \
      org.opencontainers.image.description="UML/diagram MCP server (Kroki) with optional Entra ID / OAuth 2.1 SSO" \
      org.opencontainers.image.source="https://github.com/antoinebou12/uml-mcp" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FASTMCP_STATELESS_HTTP=true

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    graphviz \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Installs derive from the lockfile to avoid requirements drift (layer cached on lock changes only).
COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv \
    && uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/requirements.lock.txt \
    && uv pip install --system --no-compile --no-cache-dir -r /tmp/requirements.lock.txt \
    && rm -f /tmp/requirements.lock.txt

COPY . .

# Non-root runtime user (Kubernetes runAsNonRoot / Helm chart uses the same UID).
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/output \
    && chown -R 10001:10001 /app/output
USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# --proxy-headers: honour X-Forwarded-* from the ingress (set FORWARDED_ALLOW_IPS).
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
