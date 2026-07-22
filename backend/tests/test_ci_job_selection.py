from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCRIPT = Path(__file__).parents[2] / "scripts" / "ci" / "select_ci_jobs.py"
SPEC = importlib.util.spec_from_file_location("select_ci_jobs", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_docs_only_selects_documentation() -> None:
    assert MODULE.select_jobs(["docs/testing.md", "README.md"]) == MODULE.Selection(
        backend=False,
        frontend=False,
        documentation=True,
        chromium=False,
    )


def test_backend_selects_backend_and_browser() -> None:
    assert MODULE.select_jobs(["backend/src/service.py"]) == MODULE.Selection(
        backend=True,
        frontend=False,
        documentation=False,
        chromium=True,
    )


def test_frontend_and_docs_select_their_jobs_and_browser() -> None:
    assert MODULE.select_jobs(["frontend/src/App.vue", "docs/user/index.md"]) == MODULE.Selection(
        backend=False,
        frontend=True,
        documentation=True,
        chromium=True,
    )


def test_shared_configuration_selects_everything() -> None:
    assert MODULE.select_jobs(["scripts/test"]) == MODULE.Selection.all()


def test_empty_change_set_fails_safe_to_everything() -> None:
    assert MODULE.select_jobs([]) == MODULE.Selection.all()
