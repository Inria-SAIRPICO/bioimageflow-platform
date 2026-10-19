from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap


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


def test_runner_children_fail_closed_without_importing_native_keyring(tmp_path: Path) -> None:
    native_trap = tmp_path / "native_keyring_trap.py"
    native_trap.write_text(
        "from pathlib import Path\n"
        "Path(__file__).with_suffix('.accessed').write_text('unexpected backend import')\n"
        "raise AssertionError('Native keyring backend must never be imported')\n",
    )
    child = tmp_path / "keyring_child.py"
    child.write_text(textwrap.dedent("""\
        import sys
        import keyring
        from keyring.backend import KeyringBackend
        from keyring.backends.fail import Keyring
        from keyring.errors import NoKeyringError

        assert sys.argv[1:] == ['run', '--frozen', 'pytest', 'runner-keyring-control']
        assert isinstance(keyring.get_keyring(), Keyring)
        try:
            keyring.get_password('owned-test-service', 'owned-test-user')
        except NoKeyringError:
            pass
        else:
            raise AssertionError('Default credential access must fail closed')

        class MemoryCredentials(KeyringBackend):
            priority = 1

            def __init__(self):
                self.values = {}

            def get_password(self, service, username):
                return self.values.get((service, username))

            def set_password(self, service, username, password):
                self.values[(service, username)] = password

            def delete_password(self, service, username):
                del self.values[(service, username)]

        keyring.set_keyring(MemoryCredentials())
        keyring.set_password('owned-test-service', 'owned-test-user', 'test-provider-value')
        assert keyring.get_password('owned-test-service', 'owned-test-user') == 'test-provider-value'
        keyring.delete_password('owned-test-service', 'owned-test-user')
        assert keyring.get_password('owned-test-service', 'owned-test-user') is None
        print('fail-closed default and explicit memory provider verified')
    """))
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        '#!/bin/sh\nexec "$BIOIMAGEFLOW_RUNNER_TEST_PYTHON" "$BIOIMAGEFLOW_RUNNER_TEST_CHILD" "$@"\n',
    )
    fake_uv.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = str(fake_bin) + os.pathsep + environment.get("PATH", "")
    environment["PYTHONPATH"] = str(tmp_path) + os.pathsep + environment.get("PYTHONPATH", "")
    environment["PYTHON_KEYRING_BACKEND"] = "native_keyring_trap.Keyring"
    environment["BIOIMAGEFLOW_RUNNER_TEST_PYTHON"] = sys.executable
    environment["BIOIMAGEFLOW_RUNNER_TEST_CHILD"] = str(child)
    environment.pop("BIOIMAGEFLOW_TEST_DRY_RUN", None)

    result = subprocess.run(
        [str(SCRIPT), "focus", "backend", "runner-keyring-control"],
        capture_output=True, env=environment, text=True, timeout=10,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "fail-closed default and explicit memory provider verified" in result.stdout
    assert not native_trap.with_suffix(".accessed").exists()
