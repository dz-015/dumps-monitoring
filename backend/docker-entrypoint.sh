#!/bin/sh
set -eu

# Apply migrations before serving — keeps deployments deterministic.
echo "Running alembic upgrade head…"
alembic upgrade head

# Seed once on first run (idempotent — bails out if any user already exists).
# Opt-in: RUN_SEED=1 creates demo accounts, so it must never be the default.
if [ "${RUN_SEED:-0}" = "1" ]; then
    echo "Seeding initial demo data (no-op if already populated)…"
    python -m app.seed
fi

exec "$@"
