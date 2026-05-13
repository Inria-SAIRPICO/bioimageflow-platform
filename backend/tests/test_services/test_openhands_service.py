"""Tests for the OpenHands subprocess lifecycle service."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services.openhands import OpenHandsService


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeProcess:
    def __init__(self, *, pid: int = 4321) -> None:
        self.pid = pid
        self.terminated = False
        self.killed = False
        self.wait_calls: list[float | None] = []
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        self.returncode = 0
        return 0


def _service(settings: Settings) -> OpenHandsService:
    return OpenHandsService(settings_provider=lambda: settings)


def test_desktop_default_is_available() -> None:
    service = _service(Settings(deployment_mode="desktop"))

    context = service.context()

    assert context.available is True
    assert context.reason is None


def test_desktop_explicit_false_is_unavailable() -> None:
    service = _service(Settings(deployment_mode="desktop", openhands_enabled=False))

    context = service.context()

    assert context.available is False
    assert context.reason == "disabled"


def test_webapp_requires_unsafe_features() -> None:
    default_webapp = _service(Settings(deployment_mode="webapp"))
    unsafe_webapp = _service(
        Settings(
            deployment_mode="webapp",
            enable_unsafe_webapp_features=True,
        )
    )
    disabled_webapp = _service(
        Settings(
            deployment_mode="webapp",
            enable_unsafe_webapp_features=True,
            openhands_enabled=False,
        )
    )

    assert default_webapp.context().available is False
    assert default_webapp.context().reason == "unsafe_webapp_features_disabled"
    assert unsafe_webapp.context().available is True
    assert disabled_webapp.context().available is False
    assert disabled_webapp.context().reason == "disabled"


async def test_launch_builds_process_runtime_loopback_command_and_scrubbed_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    proc = _FakeProcess()

    def _fake_popen(args: list[str], **kwargs: Any) -> _FakeProcess:
        calls.append({"args": args, "kwargs": kwargs})
        return proc

    settings = Settings(
        deployment_mode="desktop",
        openhands_port=4545,
        openhands_workspace=str(tmp_path),
    )
    service = _service(settings)
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setattr("bioimageflow_server.services.openhands.subprocess.Popen", _fake_popen)
    monkeypatch.setattr(service, "_wait_until_listening", lambda *_args, **_kwargs: None)

    status = await service.launch()

    assert status.running is True
    assert status.pid == 4321
    assert len(calls) == 1
    assert calls[0]["args"] == [
        "openhands",
        "web",
        "--host",
        "127.0.0.1",
        "--port",
        "4545",
    ]
    child_env = calls[0]["kwargs"]["env"]
    assert child_env["RUNTIME"] == "process"
    assert "OPENAI_API_KEY" not in child_env
    assert calls[0]["kwargs"]["cwd"] == str(tmp_path)
    assert calls[0]["kwargs"]["start_new_session"] is True


async def test_shutdown_terminates_only_owned_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _FakeProcess()

    monkeypatch.setattr(
        "bioimageflow_server.services.openhands.subprocess.Popen",
        lambda *_args, **_kwargs: proc,
    )
    settings = Settings(
        deployment_mode="desktop",
        openhands_workspace=str(tmp_path),
    )
    service = _service(settings)
    monkeypatch.setattr(service, "_wait_until_listening", lambda *_args, **_kwargs: None)

    await service.launch()
    status = await service.shutdown()

    assert proc.terminated is True
    assert proc.killed is False
    assert proc.wait_calls == [5.0]
    assert status.running is False
    assert service.status().pid is None


async def test_shutdown_kills_owned_process_after_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _FakeProcess()

    def _timeout_wait(timeout: float | None = None) -> int:
        proc.wait_calls.append(timeout)
        raise subprocess.TimeoutExpired(cmd="openhands", timeout=timeout)

    proc.wait = _timeout_wait  # type: ignore[method-assign]
    monkeypatch.setattr(
        "bioimageflow_server.services.openhands.subprocess.Popen",
        lambda *_args, **_kwargs: proc,
    )
    settings = Settings(
        deployment_mode="desktop",
        openhands_workspace=str(tmp_path),
    )
    service = _service(settings)
    monkeypatch.setattr(service, "_wait_until_listening", lambda *_args, **_kwargs: None)

    await service.launch()
    await service.shutdown()

    assert proc.terminated is True
    assert proc.killed is True
