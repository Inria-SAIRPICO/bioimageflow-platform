from __future__ import annotations

from pathlib import Path


def test_vscode_python_launch_profiles_enable_local_core_dependency() -> None:
    launch_path = Path(__file__).resolve().parents[2] / ".vscode" / "launch.json"
    text = launch_path.read_text()

    for name in ("Desktop", "Backend", "Backend-worktree"):
        marker = f'"name": "{name}"'
        start = text.index(marker)
        next_profile = text.find('"name":', start + len(marker))
        block = text[start:] if next_profile == -1 else text[start:next_profile]

        assert '"BIOIMAGEFLOW_USE_LOCAL_CORE": "1"' in block
