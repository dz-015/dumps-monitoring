#!/usr/bin/env bash
# Add cameras from cameras.json to the backend API.
# Skips cameras whose rtsp_url already exists.
# Usage: ./scripts/seed_cameras.sh [API_URL]
# Example: ./scripts/seed_cameras.sh http://localhost:8000

set -euo pipefail

API_URL="${1:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CAMERAS_FILE="$SCRIPT_DIR/cameras.json"

if ! command -v jq &>/dev/null; then
    echo "Error: jq is required. Install: apt install jq"
    exit 1
fi

# Fetch existing cameras
existing=$(curl -s "$API_URL/api/v1/cameras/" | jq -r '.[].rtsp_url')

count=$(jq length "$CAMERAS_FILE")
added=0
skipped=0

echo "Processing $count cameras..."

for i in $(seq 0 $((count - 1))); do
    camera=$(jq -c ".[$i]" "$CAMERAS_FILE")
    name=$(echo "$camera" | jq -r .name)
    url=$(echo "$camera" | jq -r .rtsp_url)

    if echo "$existing" | grep -qF "$url"; then
        echo "  SKIP: $name (already exists)"
        skipped=$((skipped + 1))
        continue
    fi

    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/v1/cameras/" \
        -H "Content-Type: application/json" \
        -d "$camera")

    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | head -1)

    if [ "$http_code" -eq 201 ]; then
        id=$(echo "$body" | jq -r .id)
        echo "  OK: $name (id=$id)"
        added=$((added + 1))
    else
        echo "  FAIL: $name (HTTP $http_code) $body"
    fi
done

echo "Done: $added added, $skipped skipped."

