FROM python:3.12-slim AS runtime

# System packages: just curl for healthchecks. Slim base intentionally.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user — defence in depth in case anything escapes the app.
RUN useradd --create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Layer cache: install deps before copying source.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code + entrypoint script.
COPY --chown=app:app . .
# /app/data is the mountpoint for the backend_db volume — it must exist and be
# writable by `app` BEFORE the volume is mounted, or Docker creates it root-owned
# and SQLite cannot create the database file on first boot.
RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/uploads /app/data \
    && chown -R app:app /app

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
