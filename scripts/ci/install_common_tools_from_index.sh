#!/usr/bin/env bash

set -euo pipefail

repo_root="${CI_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

: "${BIOIMAGEFLOW_COMMON_TOOLS_VERSION:?BIOIMAGEFLOW_COMMON_TOOLS_VERSION must be set}"
: "${BIOIMAGEFLOW_TOOL_STORE:?BIOIMAGEFLOW_TOOL_STORE must be set}"

if [[ ! "$BIOIMAGEFLOW_COMMON_TOOLS_VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z._+-]*$ ]]; then
  printf 'Invalid BIOIMAGEFLOW_COMMON_TOOLS_VERSION: %s\n' \
    "$BIOIMAGEFLOW_COMMON_TOOLS_VERSION" >&2
  exit 1
fi

target="$BIOIMAGEFLOW_TOOL_STORE/bioimageflow_common_tools/$BIOIMAGEFLOW_COMMON_TOOLS_VERSION"
if [[ -e "$target" || -L "$target" ]]; then
  printf 'Refusing to reuse an existing common-tools certification target: %s\n' "$target" >&2
  exit 1
fi

mkdir -p "$target"
uv --no-cache pip install \
  --python "$repo_root/backend/.venv/bin/python" \
  --target "$target" \
  "bioimageflow-common-tools==$BIOIMAGEFLOW_COMMON_TOOLS_VERSION"

if [[ ! -f "$target/bioimageflow_common_tools/__init__.py" ]]; then
  printf 'Package-index install did not create bioimageflow_common_tools in %s\n' "$target" >&2
  exit 1
fi

printf 'Installed bioimageflow-common-tools %s from the package index\n' \
  "$BIOIMAGEFLOW_COMMON_TOOLS_VERSION"
