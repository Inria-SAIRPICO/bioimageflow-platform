#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT="$FRONTEND_DIR/src/api/types.ts"
SCHEMA_URL="${OPENAPI_URL:-http://localhost:8000/openapi.json}"

echo "Fetching OpenAPI schema from $SCHEMA_URL ..."
curl -sf "$SCHEMA_URL" | npx openapi-typescript --stdin -o "$OUTPUT"

echo "Types generated at $OUTPUT"
