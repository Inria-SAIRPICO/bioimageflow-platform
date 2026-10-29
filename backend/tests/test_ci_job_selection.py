from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import yaml


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
        firefox_smoke=False,
    )


def test_backend_selects_backend_and_browser() -> None:
    assert MODULE.select_jobs(["backend/src/service.py"]) == MODULE.Selection(
        backend=True,
        frontend=False,
        documentation=False,
        chromium=True,
        firefox_smoke=True,
    )


def test_frontend_and_docs_select_their_jobs_and_browser() -> None:
    assert MODULE.select_jobs(["frontend/src/App.vue", "docs/user/index.md"]) == MODULE.Selection(
        backend=False,
        frontend=True,
        documentation=True,
        chromium=True,
        firefox_smoke=True,
    )


def test_backend_tests_do_not_select_firefox_smoke() -> None:
    assert MODULE.select_jobs(["backend/tests/test_service.py"]) == MODULE.Selection(
        backend=True,
        frontend=False,
        documentation=False,
        chromium=True,
        firefox_smoke=False,
    )


def test_shared_configuration_selects_everything() -> None:
    assert MODULE.select_jobs(["scripts/test"]) == MODULE.Selection.all()


def test_empty_change_set_fails_safe_to_everything() -> None:
    assert MODULE.select_jobs([]) == MODULE.Selection.all()


def _workflow(name: str) -> dict:
    path = SCRIPT.parents[2] / ".github" / "workflows" / name
    # BaseLoader preserves GitHub's YAML `on` key as a string.
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


def test_distributed_workflow_is_manual_only_and_independent_of_required_ci() -> None:
    optional = _workflow("distributed.yml")
    assert set(optional["on"]) == {"workflow_dispatch"}
    assert optional["env"]["BIOIMAGEFLOW_TEST_SUITE"] == "distributed"
    assert set(optional["jobs"]) == {"backend", "frontend", "browser"}
    assert optional["jobs"]["browser"]["strategy"]["matrix"]["browser"] == [
        "chromium", "firefox",
    ]

    for name in ("ci.yml", "weekly.yml"):
        required = _workflow(name)
        assert required["env"]["BIOIMAGEFLOW_TEST_SUITE"] == "local"
        assert all("uses" not in job for job in required["jobs"].values())
        assert all(
            "distributed" not in job.get("needs", [])
            for job in required["jobs"].values()
        )


def test_weekly_validation_keeps_its_monday_schedule_outside_pr_ci() -> None:
    weekly = _workflow("weekly.yml")
    assert weekly["on"]["schedule"] == [{"cron": "0 4 * * 1"}]
    assert "schedule" not in _workflow("ci.yml")["on"]
    assert set(weekly["jobs"]["required"]["needs"]) == {
        "backend", "frontend", "common-tools", "chromium", "firefox",
    }
