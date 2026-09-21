FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x healthcheck.sh

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ./healthcheck.sh || exit 1

ENV SERVICE_PORT=8001
# `exec` replaces the shell with uvicorn (PID 1) so SIGTERM reaches it
# directly for graceful shutdown, while still expanding env vars. TLS/mTLS
# args are only added when TLS_ENABLED=true (see config.py / docker-compose.yml).
CMD ["sh", "-c", "\
    if [ \"${TLS_ENABLED:-false}\" = \"true\" ]; then \
        exec uvicorn app:app --host 0.0.0.0 --port ${SERVICE_PORT} \
            --ssl-certfile \"$TLS_CERT_FILE\" --ssl-keyfile \"$TLS_KEY_FILE\" \
            --ssl-ca-certs \"$TLS_CLIENT_CA_FILE\" --ssl-cert-reqs 2; \
    else \
        exec uvicorn app:app --host 0.0.0.0 --port ${SERVICE_PORT}; \
    fi"]
