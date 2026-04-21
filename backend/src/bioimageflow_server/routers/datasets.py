"""Datasets router — server-side dataset storage (v1 §2.4.10)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/datasets", tags=["datasets"])


# ---------------------------------------------------------------------------
# Dependency stubs – overridden via app.dependency_overrides in create_app()
# ---------------------------------------------------------------------------


def get_datasets_root() -> Path | None:  # pragma: no cover
    return None


def get_max_upload_size() -> int | None:  # pragma: no cover
    return None
