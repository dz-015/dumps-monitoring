#!/bin/sh
set -eu

# Apply migrations before serving — keeps deployments deterministic.
echo "Running alembic upgrade head…"
alembic upgrade head

# Seed once on first run (idempotent — bails out if any user already exists).
if [ "${RUN_SEED:-1}" = "1" ]; then
    echo "Seeding initial demo data (no-op if already populated)…"
    python -m app.seed
fi

exec "$@"
