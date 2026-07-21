#!/usr/bin/env bash

set -euo pipefail

export GIT_TERMINAL_PROMPT=0

repo_root="${GITHUB_WORKSPACE:-${CI_PROJECT_DIR:-$(git rev-parse --show-toplevel)}}"

: "${BIOIMAGEFLOW_SOURCE_REVISION:?BIOIMAGEFLOW_SOURCE_REVISION must be a full commit SHA}"
: "${LAUNCHER_SOURCE_REVISION:?LAUNCHER_SOURCE_REVISION must be a full commit SHA}"
: "${WETLANDS_SOURCE_REVISION:?WETLANDS_SOURCE_REVISION must be a full commit SHA}"

bioimageflow_url="${BIOIMAGEFLOW_SOURCE_URL:-https://github.com/Inria-SAIRPICO/bioimageflow.git}"
launcher_url="${LAUNCHER_SOURCE_URL:-https://github.com/arthursw/launcher.git}"
wetlands_url="${WETLANDS_SOURCE_URL:-https://github.com/arthursw/wetlands.git}"

require_full_sha() {
  local name="$1"
  local revision="$2"

  if [[ ! "$revision" =~ ^[0-9a-f]{40}$ ]]; then
    printf '%s must be a lowercase 40-character commit SHA, got: %s\n' "$name" "$revision" >&2
    return 1
  fi
}

checkout_exact_revision() {
  local name="$1"
  local url="$2"
  local revision="$3"
  local destination="$4"
  local temporary_checkout
  local fetched_revision

  require_full_sha "${name}_SOURCE_REVISION" "$revision"

  if [[ -d "$destination/.git" ]]; then
    fetched_revision="$(git -C "$destination" rev-parse HEAD)"
    if [[ "$fetched_revision" == "$revision" ]] && [[ -z "$(git -C "$destination" status --porcelain)" ]]; then
      printf 'Reusing %s at %s\n' "$name" "$revision"
      return
    fi
    printf '%s already exists at %s but is not the requested clean revision %s\n' \
      "$name" "$destination" "$revision" >&2
    return 1
  fi

  if [[ -e "$destination" || -L "$destination" ]]; then
    printf 'Refusing to replace existing non-repository path: %s\n' "$destination" >&2
    return 1
  fi

  mkdir -p "$(dirname "$destination")"
  temporary_checkout="${destination}.clone-${GITHUB_RUN_ID:-${CI_JOB_ID:-$$}}"
  if [[ -e "$temporary_checkout" || -L "$temporary_checkout" ]]; then
    printf 'Temporary checkout path already exists: %s\n' "$temporary_checkout" >&2
    return 1
  fi

  cleanup_temporary_checkout() {
    rm -rf "$temporary_checkout"
  }
  trap cleanup_temporary_checkout RETURN

  git init --quiet "$temporary_checkout"
  git -C "$temporary_checkout" remote add origin "$url"
  if ! git -C "$temporary_checkout" fetch --quiet --depth 1 origin "$revision"; then
    printf '%s revision %s could not be fetched from its configured remote. Publish the pinned revision or update the pin to a reachable commit.\n' \
      "$name" "$revision" >&2
    return 1
  fi

  fetched_revision="$(git -C "$temporary_checkout" rev-parse FETCH_HEAD)"
  if [[ "$fetched_revision" != "$revision" ]]; then
    printf '%s fetched %s instead of requested revision %s\n' \
      "$name" "$fetched_revision" "$revision" >&2
    return 1
  fi

  git -C "$temporary_checkout" checkout --quiet --detach "$revision"
  mv "$temporary_checkout" "$destination"
  trap - RETURN
  printf 'Checked out %s at %s\n' "$name" "$revision"
}

checkout_exact_revision \
  BIOIMAGEFLOW \
  "$bioimageflow_url" \
  "$BIOIMAGEFLOW_SOURCE_REVISION" \
  "$repo_root/bioimageflow"

checkout_exact_revision \
  LAUNCHER \
  "$launcher_url" \
  "$LAUNCHER_SOURCE_REVISION" \
  "$repo_root/../launcher"

checkout_exact_revision \
  WETLANDS \
  "$wetlands_url" \
  "$WETLANDS_SOURCE_REVISION" \
  "$repo_root/../wetlands"
