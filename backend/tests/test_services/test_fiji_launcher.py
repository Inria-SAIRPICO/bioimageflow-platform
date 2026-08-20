from __future__ import annotations

from pathlib import Path

import pytest

from bioimageflow_server.models.settings import Settings
from bioimageflow_server.services.fiji_launcher import (
    FijiInstallationError,
    FijiLaunchError,
    FijiLauncher,
    FijiNotConfiguredError,
    resolve_fiji_installation,
)


def _executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("launcher")
    path.chmod(0o755)
    return path


def test_resolves_current_linux_launcher(tmp_path: Path) -> None:
    launcher = _executable(tmp_path / "Fiji.app" / "fiji")

    installation = resolve_fiji_installation(
        str(tmp_path / "Fiji.app"), system="Linux", machine="x86_64"
    )

    assert installation.root == tmp_path / "Fiji.app"
    assert installation.command_prefix == (str(launcher),)


def test_resolves_legacy_linux_launcher(tmp_path: Path) -> None:
    launcher = _executable(tmp_path / "Fiji.app" / "ImageJ-linux64")

    installation = resolve_fiji_installation(
        str(tmp_path / "Fiji.app"), system="Linux", machine="amd64"
    )

    assert installation.command_prefix == (str(launcher),)


def test_resolves_windows_arm_launcher(tmp_path: Path) -> None:
    launcher = _executable(tmp_path / "Fiji.app" / "fiji-windows-arm64.exe")

    installation = resolve_fiji_installation(
        str(tmp_path / "Fiji.app"), system="Windows", machine="aarch64"
    )

    assert installation.command_prefix == (str(launcher),)


def test_resolves_macos_bundle_with_open(tmp_path: Path) -> None:
    root = tmp_path / "Fiji.app"
    _executable(root / "Contents" / "MacOS" / "fiji-macos-arm64")

    installation = resolve_fiji_installation(
        str(root), system="Darwin", machine="arm64"
    )

    assert installation.command_prefix == ("/usr/bin/open", "-a", str(root), "--args")


def test_rejects_folder_without_platform_launcher(tmp_path: Path) -> None:
    root = tmp_path / "Fiji.app"
    root.mkdir()

    with pytest.raises(FijiInstallationError, match="Linux Fiji launcher"):
        resolve_fiji_installation(str(root), system="Linux", machine="x86_64")


def test_rejects_unknown_cpu_architecture(tmp_path: Path) -> None:
    root = tmp_path / "Fiji.app"
    root.mkdir()

    with pytest.raises(FijiInstallationError, match="CPU architecture"):
        resolve_fiji_installation(str(root), system="Linux", machine="mips")


def test_open_launches_image_as_separate_argument(tmp_path: Path) -> None:
    root = tmp_path / "Fiji application" / "Fiji.app"
    launcher = _executable(root / "fiji")
    image = tmp_path / "result images" / "mask 1.tif"
    image.parent.mkdir()
    image.write_bytes(b"tif")
    calls: list[tuple[list[str], Path, str]] = []
    service = FijiLauncher(
        settings_provider=lambda: Settings(deployment_mode="desktop", fiji_path=str(root)),
        process_launcher=lambda args, cwd, system: calls.append((args, cwd, system)),
        system_provider=lambda: "Linux",
        machine_provider=lambda: "x86_64",
    )

    service.open(image)

    assert calls == [([str(launcher), str(image)], root, "Linux")]


def test_open_requires_configuration(tmp_path: Path) -> None:
    service = FijiLauncher(
        settings_provider=lambda: Settings(deployment_mode="desktop"),
        system_provider=lambda: "Linux",
        machine_provider=lambda: "x86_64",
    )

    with pytest.raises(FijiNotConfiguredError):
        service.open(tmp_path / "mask.tif")


def test_open_wraps_process_errors(tmp_path: Path) -> None:
    root = tmp_path / "Fiji.app"
    _executable(root / "fiji")
    image = tmp_path / "mask.tif"
    image.write_bytes(b"tif")

    def fail(_args: list[str], _cwd: Path, _system: str) -> object:
        raise OSError("launch denied")

    service = FijiLauncher(
        settings_provider=lambda: Settings(deployment_mode="desktop", fiji_path=str(root)),
        process_launcher=fail,
        system_provider=lambda: "Linux",
        machine_provider=lambda: "x86_64",
    )

    with pytest.raises(FijiLaunchError, match="launch denied"):
        service.open(image)
