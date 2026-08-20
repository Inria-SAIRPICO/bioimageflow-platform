"""Resolve a user-installed Fiji application and open image files with it."""

from __future__ import annotations

import os
import platform
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bioimageflow_server.models.settings import Settings


class FijiError(Exception):
    """Base class for Fiji integration failures."""


class FijiNotConfiguredError(FijiError):
    """Raised when no Fiji installation has been configured."""


class FijiInstallationError(FijiError):
    """Raised when the configured Fiji installation cannot be used."""


class FijiLaunchError(FijiError):
    """Raised when the Fiji process cannot be launched."""


@dataclass(frozen=True)
class FijiInstallation:
    root: Path
    command_prefix: tuple[str, ...]


SettingsProvider = Callable[[], Settings]
SystemProvider = Callable[[], str]
MachineProvider = Callable[[], str]
ProcessLauncher = Callable[[list[str], Path, str], object]


def _architecture(machine: str) -> str:
    normalized = machine.lower().replace("_", "-")
    if normalized in {"arm64", "aarch64"}:
        return "arm64"
    if normalized in {"amd64", "x86-64", "x86_64"}:
        return "x64"
    raise FijiInstallationError(f"Fiji is not supported on this CPU architecture: {machine}")


def _first_executable(root: Path, relative_paths: tuple[str, ...]) -> Path | None:
    for relative in relative_paths:
        candidate = root / relative
        if candidate.is_file() and (os.name == "nt" or os.access(candidate, os.X_OK)):
            return candidate
    return None


def resolve_fiji_installation(
    path: str,
    *,
    system: str | None = None,
    machine: str | None = None,
) -> FijiInstallation:
    """Validate a Fiji application directory and return its launch prefix."""
    root = Path(path).expanduser().resolve(strict=False)
    if not root.is_absolute() or not root.is_dir():
        raise FijiInstallationError("Choose the Fiji.app folder you downloaded and unpacked.")

    current_system = system or platform.system()
    architecture = _architecture(machine or platform.machine())

    if current_system == "Darwin":
        launcher = _first_executable(
            root,
            (
                f"Contents/MacOS/fiji-macos-{architecture}",
                "Contents/MacOS/fiji-macosx",
                "Contents/MacOS/ImageJ-macosx",
            ),
        )
        if launcher is None:
            raise FijiInstallationError("The selected folder does not contain a macOS Fiji application.")
        return FijiInstallation(root=root, command_prefix=("/usr/bin/open", "-a", str(root), "--args"))

    if current_system == "Linux":
        launcher = _first_executable(
            root,
            (
                "fiji",
                f"fiji-linux-{architecture}",
                "ImageJ-linux64" if architecture == "x64" else "ImageJ-linux-arm64",
            ),
        )
        if launcher is None:
            raise FijiInstallationError("The selected folder does not contain a Linux Fiji launcher.")
        return FijiInstallation(root=root, command_prefix=(str(launcher),))

    if current_system == "Windows":
        launcher = _first_executable(
            root,
            (
                f"fiji-windows-{architecture}.exe",
                "ImageJ-win64.exe" if architecture == "x64" else "ImageJ-win-arm64.exe",
            ),
        )
        if launcher is None:
            raise FijiInstallationError("The selected folder does not contain a Windows Fiji launcher.")
        return FijiInstallation(root=root, command_prefix=(str(launcher),))

    raise FijiInstallationError(f"Fiji is not supported on this operating system: {current_system}")


def _default_process_launcher(args: list[str], cwd: Path, system: str) -> subprocess.Popen[Any]:
    kwargs: dict[str, Any] = {"cwd": cwd}
    if system == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(args, **kwargs)


class FijiLauncher:
    """Launch the user-owned Fiji application without supervising its lifecycle."""

    def __init__(
        self,
        *,
        settings_provider: SettingsProvider,
        process_launcher: ProcessLauncher = _default_process_launcher,
        system_provider: SystemProvider = platform.system,
        machine_provider: MachineProvider = platform.machine,
    ) -> None:
        self._settings_provider = settings_provider
        self._process_launcher = process_launcher
        self._system_provider = system_provider
        self._machine_provider = machine_provider

    def validate_installation(self, path: str) -> Path:
        installation = resolve_fiji_installation(
            path,
            system=self._system_provider(),
            machine=self._machine_provider(),
        )
        return installation.root

    def open(self, image_path: Path) -> None:
        settings = self._settings_provider()
        if settings.deployment_mode != "desktop":
            raise FijiInstallationError("Fiji is available only in the desktop application.")
        if not settings.fiji_path:
            raise FijiNotConfiguredError("Configure Fiji in Preferences before opening an image.")
        if not image_path.is_file():
            raise FileNotFoundError(str(image_path))

        system = self._system_provider()
        installation = resolve_fiji_installation(
            settings.fiji_path,
            system=system,
            machine=self._machine_provider(),
        )
        args = [*installation.command_prefix, str(image_path)]
        try:
            self._process_launcher(args, installation.root, system)
        except OSError as exc:
            raise FijiLaunchError(str(exc)) from exc
