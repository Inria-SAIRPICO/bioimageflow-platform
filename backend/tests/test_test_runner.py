from __future__ import annotations

import os
from pathlib import Path
import subprocess


SCRIPT = Path(__file__).parents[2] / "scripts" / "test"


def _run_test_runner(*arguments: str) -> str:
    environment = os.environ.copy()
    environment["BIOIMAGEFLOW_TEST_DRY_RUN"] = "1"
    result = subprocess.run(
        [str(SCRIPT), *arguments],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    return result.stdout


def test_focused_e2e_defaults_to_fail_fast_chromium() -> None:
    output = _run_test_runner("focus", "e2e", "tests/e2e/hot-reload.spec.ts")

    assert "--project=chromium" in output
    assert "--max-failures=1" in output
    assert "tests/e2e/hot-reload.spec.ts" in output


def test_focused_e2e_honors_an_explicit_firefox_project() -> None:
    output = _run_test_runner(
        "focus",
        "e2e",
        "--project=firefox",
        "tests/e2e/hot-reload.spec.ts",
    )

    assert "--project=firefox" in output
    assert "--project=chromium" not in output
    assert "--max-failures=1" in output


def test_focused_e2e_preserves_an_explicit_failure_limit() -> None:
    output = _run_test_runner(
        "focus",
        "e2e",
        "--project",
        "firefox",
        "--max-failures=3",
    )

    dry_run = next(line for line in output.splitlines() if line.startswith("E2E dry run:"))
    assert "--project firefox" in output
    assert "--project=chromium" not in output
    assert dry_run.count("--max-failures") == 1
    assert "--max-failures=3" in dry_run


def test_cross_browser_smoke_routes_each_browser_once() -> None:
    output = _run_test_runner("check", "cross-browser-smoke")

    assert output.count("--project=chromium") == 1
    assert output.count("--project=firefox") == 1
    assert output.count("--grep @critical") == 2


def test_browser_firefox_check_does_not_launch_chromium() -> None:
    output = _run_test_runner("check", "browser-firefox")

    assert "--project=firefox" in output
    assert "--project=chromium" not in output


def test_runner_reports_total_elapsed_time() -> None:
    output = _run_test_runner("focus", "e2e", "--project=firefox")

    assert "TOTAL: scripts/test focus e2e --project=firefox" in output


def test_timed_phase_preserves_fail_fast_behavior() -> None:
    environment = os.environ.copy()
    environment["BIOIMAGEFLOW_TEST_PHASE_FAILURE"] = "1"
    result = subprocess.run(
        [str(SCRIPT), "check", "browser"],
        capture_output=True,
        env=environment,
        text=True,
        timeout=5,
    )

    assert result.returncode == 1
    assert result.stderr.count("Forced E2E phase failure.") == 1
    assert "ERROR: E2E continued after failure." not in result.stderr
    assert "TOTAL: scripts/test check browser" in result.stdout


def test_backend_coverage_database_is_transient() -> None:
    runner = SCRIPT.read_text()

    assert 'export COVERAGE_FILE="$backend_dir/.pytest_cache/.coverage"' in runner
    assert 'rm -f -- "$COVERAGE_FILE"' in runner
