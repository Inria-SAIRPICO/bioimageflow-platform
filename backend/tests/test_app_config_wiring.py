"""Tests that AppConfig datasets_root / max_upload_size reach the datasets router."""

from __future__ import annotations

from pathlib import Path

from bioimageflow_server.app import create_app
from bioimageflow_server.models.tools import AppConfig
from bioimageflow_server.routers.datasets import (
    get_datasets_root,
    get_max_upload_size,
)


def test_dataset_deps_unwired_by_default():
    app = create_app()
    assert get_datasets_root not in app.dependency_overrides
    assert get_max_upload_size not in app.dependency_overrides


def test_app_config_wires_datasets_root(tmp_path: Path):
    cfg = AppConfig(datasets_root=tmp_path, max_upload_size=1_000_000)
    app = create_app(config=cfg)
    assert app.dependency_overrides[get_datasets_root]() == tmp_path
    assert app.dependency_overrides[get_max_upload_size]() == 1_000_000
