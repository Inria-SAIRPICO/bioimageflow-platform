"""Tests that AppConfig datasets_root / max_upload_size reach the datasets router."""

from __future__ import annotations

from pathlib import Path

from bioimageflow.paths import get_home

from bioimageflow_server.app import create_app
from bioimageflow_server.models.settings import _DEFAULT_MAX_UPLOAD_SIZE
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.routers.datasets import (
    get_datasets_root,
    get_max_upload_size,
)


def test_dataset_deps_fall_back_to_defaults():
    app = create_app()
    assert app.dependency_overrides[get_datasets_root]() == get_home() / "datasets"
    assert app.dependency_overrides[get_max_upload_size]() == _DEFAULT_MAX_UPLOAD_SIZE


def test_app_config_wires_datasets_root(tmp_path: Path):
    cfg = AppConfig(datasets_root=tmp_path, max_upload_size=1_000_000)
    app = create_app(config=cfg)
    assert app.dependency_overrides[get_datasets_root]() == tmp_path
    assert app.dependency_overrides[get_max_upload_size]() == 1_000_000
