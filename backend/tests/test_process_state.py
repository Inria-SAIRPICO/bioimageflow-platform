"""The process witness observes a live child and its actual termination."""

import subprocess
import sys

from tests.fixtures.process_state import process_is_running


def test_child_lifetime_probe_is_non_signalling():
    child = subprocess.Popen(
        [sys.executable, "-c", "import sys; print('ready', flush=True); sys.stdin.read()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "ready"
        assert process_is_running(child.pid)
        assert child.poll() is None
    finally:
        child.communicate(timeout=10)
    assert child.returncode == 0
    assert not process_is_running(child.pid)
