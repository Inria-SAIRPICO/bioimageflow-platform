#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT="$FRONTEND_DIR/src/api/types.ts"
SCHEMA_URL="${OPENAPI_URL:-http://localhost:8000/openapi.json}"

echo "Fetching OpenAPI schema from $SCHEMA_URL ..."
curl -sf "$SCHEMA_URL" | npx openapi-typescript --stdin \
  --root-types --root-types-no-schema-prefix \
  -o "$OUTPUT"

# Append manual aliases. ``Settings`` is the schema-less alias for
# ``SettingsResponse`` (the GET/PATCH wrapper); ``OMEROInstance`` keeps the
# historical UPPER-case spelling that consumers expect.
cat >> "$OUTPUT" <<'EOF'

// --- Manual aliases (re-applied after every `generate-types` run) ---
export type Settings = SettingsResponse;
export type OMEROInstance = OmeroInstance;
EOF

echo "Types generated at $OUTPUT"
