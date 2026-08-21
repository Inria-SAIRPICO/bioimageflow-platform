from __future__ import annotations

import json
from pathlib import Path


def _launch_profile_block(text: str, name: str) -> str:
    marker = f'"name": "{name}"'
    start = text.index(marker)
    next_profile = text.find('"name":', start + len(marker))
    return text[start:] if next_profile == -1 else text[start:next_profile]


def test_vscode_python_launch_profiles_enable_local_core_dependency() -> None:
    launch_path = Path(__file__).resolve().parents[2] / ".vscode" / "launch.json"
    text = launch_path.read_text()

    for name in ("Desktop", "Backend", "Backend-worktree"):
        block = _launch_profile_block(text, name)
        assert '"BIOIMAGEFLOW_USE_LOCAL_CORE": "1"' in block


def test_vscode_uses_backend_virtual_environment_for_python_analysis() -> None:
    settings_path = Path(__file__).resolve().parents[2] / ".vscode" / "settings.json"
    settings = json.loads(settings_path.read_text())

    assert settings["python.defaultInterpreterPath"] == "${workspaceFolder}/backend/.venv"


def test_vscode_desktop_launch_profile_enables_development_mode() -> None:
    launch_path = Path(__file__).resolve().parents[2] / ".vscode" / "launch.json"
    desktop_block = _launch_profile_block(launch_path.read_text(), "Desktop")

    assert '"--desktop"' in desktop_block
    assert '"--dev"' in desktop_block


def test_vscode_desktop_launch_profile_starts_vite_on_expected_port() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    launch_path = repository_root / ".vscode" / "launch.json"
    desktop_block = _launch_profile_block(launch_path.read_text(), "Desktop")
    tasks = json.loads((repository_root / ".vscode" / "tasks.json").read_text())
    frontend_task = next(
        task for task in tasks["tasks"] if task["label"] == "Frontend: dev"
    )

    assert '"preLaunchTask": "Frontend: dev"' in desktop_block
    assert frontend_task["options"]["cwd"] == "${workspaceFolder}/frontend"
    assert frontend_task["isBackground"] is True
    assert "--strictPort" in frontend_task["args"]
    assert "--clearScreen=false" in frontend_task["args"]
    assert frontend_task["problemMatcher"]["base"] == "$tsc-watch"
    assert frontend_task["problemMatcher"]["background"]["endsPattern"] == "ready in"


def test_vite_backend_proxy_uses_ipv4_loopback() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    vite_config = (repository_root / "frontend" / "vite.config.ts").read_text()

    assert "const backendHttpUrl = `http://127.0.0.1:${backendPort}`" in vite_config


def test_packaged_launcher_uses_production_desktop_mode() -> None:
    application_path = (
        Path(__file__).resolve().parents[1] / "packaging" / "launcher" / "application.yml"
    )
    application_config = application_path.read_text()

    assert "    - --desktop\n" in application_config
    assert "    - --dev\n" not in application_config
