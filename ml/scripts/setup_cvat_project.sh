#!/usr/bin/env bash
# CVAT project + 5 tasks setup script. Run on 4090 host after `docker compose up -d` is up.
# Usage:  bash setup_cvat_project.sh <admin-username> <admin-email> <admin-password>

set -euo pipefail

ADMIN_USER="${1:-admin}"
ADMIN_EMAIL="${2:-admin@nekobak.ru}"
ADMIN_PASS="${3:-admin12345}"
CVAT_URL="http://localhost:8080"

echo "=== Wait for CVAT to be reachable ==="
for i in {1..60}; do
  if curl -fsS "$CVAT_URL/api/server/about" >/dev/null 2>&1; then
    echo "CVAT API up after ${i} sec"
    break
  fi
  sleep 5
done

echo ""
echo "=== Create superuser (idempotent) ==="
docker exec cvat_server bash -ic "
DJANGO_SUPERUSER_USERNAME='$ADMIN_USER' DJANGO_SUPERUSER_EMAIL='$ADMIN_EMAIL' DJANGO_SUPERUSER_PASSWORD='$ADMIN_PASS' \
python3 ~/manage.py createsuperuser --noinput || echo 'superuser exists'
"

echo ""
echo "=== Get auth token ==="
TOKEN=$(curl -s -X POST "$CVAT_URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\": \"$ADMIN_USER\", \"password\": \"$ADMIN_PASS\"}" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['key'])")
echo "Token: $TOKEN"

echo ""
echo "=== Create project ==="
PROJECT_RESP=$(curl -s -X POST "$CVAT_URL/api/projects" \
  -H "Authorization: Token $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "НЭКОБАК — 3 классов",
    "labels": [
      {"name": "bin_ok", "color": "#22c55e", "attributes": [{"name": "review", "input_type": "checkbox", "values": ["false"], "default_value": "false"}]},
      {"name": "bin_overflow", "color": "#ef4444", "attributes": [{"name": "review", "input_type": "checkbox", "values": ["false"], "default_value": "false"}]},
      {"name": "ground_trash", "color": "#f97316", "attributes": [{"name": "review", "input_type": "checkbox", "values": ["false"], "default_value": "false"}]}
    ]
  }')
PROJECT_ID=$(echo "$PROJECT_RESP" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', 'ERR'))")
echo "Project id: $PROJECT_ID"
echo "Open: $CVAT_URL/projects/$PROJECT_ID"
