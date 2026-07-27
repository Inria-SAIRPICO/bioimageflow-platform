from __future__ import annotations

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


def test_vscode_desktop_launch_profile_enables_development_mode() -> None:
    launch_path = Path(__file__).resolve().parents[2] / ".vscode" / "launch.json"
    desktop_block = _launch_profile_block(launch_path.read_text(), "Desktop")

    assert '"--desktop"' in desktop_block
    assert '"--dev"' in desktop_block


def test_packaged_launcher_uses_production_desktop_mode() -> None:
    application_path = (
        Path(__file__).resolve().parents[1] / "packaging" / "launcher" / "application.yml"
    )
    application_config = application_path.read_text()

    assert "    - --desktop\n" in application_config
    assert "    - --dev\n" not in application_config
