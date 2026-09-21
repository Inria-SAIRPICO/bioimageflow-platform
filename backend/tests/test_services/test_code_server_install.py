"""Tests for the packaged code-server runtime installer."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from bioimageflow_server.data import code_server_install as install
from bioimageflow_server.services.editor import default_code_server_installer_path

RELEASE_ROOT = "code-server-4.137.0-linux-amd64"


def write_release(tmp_path: Path, name: str = "release.tar.gz") -> Path:
    """Build a release-shaped archive with the bundle's single root directory."""
    root = tmp_path / "build" / RELEASE_ROOT
    (root / "bin").mkdir(parents=True)
    (root / "lib").mkdir()
    (root / "package.json").write_text('{"name": "code-server"}\n', encoding="utf-8")
    script = root / "bin" / "code-server"
    script.write_text("#!/bin/sh\nexec node\n", encoding="utf-8")
    script.chmod(0o755)
    (root / "lib" / "node.exe").write_text("node", encoding="utf-8")
    archive = tmp_path / name
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return archive


def installer_args(tmp_path: Path, archive: Path, destination: Path) -> list[str]:
    return [
        "--url",
        archive.as_uri(),
        "--sha256",
        hashlib.sha256(archive.read_bytes()).hexdigest(),
        "--destination",
        str(destination),
        "--installer-revision",
        "1",
    ]


def run_installer(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(default_code_server_installer_path()), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_release_archive_is_verified_and_unpacked(tmp_path: Path) -> None:
    archive = write_release(tmp_path)
    destination = tmp_path / "prefix" / "share" / "code-server"

    result = run_installer(*installer_args(tmp_path, archive, destination))

    assert result.returncode == 0, result.stderr
    assert (destination / "package.json").is_file()
    assert (destination / "bin" / "code-server").is_file()
    assert (destination / "extensions").is_dir()
    stamp = json.loads((destination / ".bioimageflow-install.json").read_text(encoding="utf-8"))
    assert stamp == {
        "url": archive.as_uri(),
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "installer_revision": "1",
    }
    if os.name == "posix":
        assert (destination / "bin" / "code-server").stat().st_mode & 0o111


def test_second_run_reuses_the_installed_runtime(tmp_path: Path) -> None:
    archive = write_release(tmp_path)
    destination = tmp_path / "prefix" / "share" / "code-server"
    args = installer_args(tmp_path, archive, destination)
    assert run_installer(*args).returncode == 0
    marker = destination / "installed-extension"
    marker.write_text("keep", encoding="utf-8")

    result = run_installer(*args)

    assert result.returncode == 0, result.stderr
    assert "already installed" in result.stdout
    assert marker.is_file()


def test_digest_mismatch_leaves_no_destination(tmp_path: Path) -> None:
    archive = write_release(tmp_path)
    destination = tmp_path / "prefix" / "share" / "code-server"
    args = installer_args(tmp_path, archive, destination)
    args[args.index("--sha256") + 1] = "0" * 64

    result = run_installer(*args)

    assert result.returncode == 2
    assert "code editor archive digest mismatch" in result.stderr
    assert not destination.exists()


def test_missing_archive_reports_download_failure(tmp_path: Path) -> None:
    destination = tmp_path / "prefix" / "share" / "code-server"
    args = installer_args(tmp_path, write_release(tmp_path), destination)
    args[args.index("--url") + 1] = (tmp_path / "absent.tar.gz").as_uri()

    result = run_installer(*args)

    assert result.returncode == 3
    assert "code editor archive download failed" in result.stderr
    assert not destination.exists()


def test_archive_member_escaping_the_root_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "escaping.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo(f"{RELEASE_ROOT}/../evil")
        payload = b"evil"
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    destination = tmp_path / "prefix" / "share" / "code-server"

    result = run_installer(*installer_args(tmp_path, archive, destination))

    assert result.returncode == 5
    assert "unexpected code editor archive layout" in result.stderr
    assert not destination.exists()
    assert not (destination.parent / "evil").exists()
    assert not list(destination.parent.glob(".code-server-staging-*"))


def test_archive_without_launch_entrypoint_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "build" / RELEASE_ROOT
    root.mkdir(parents=True)
    (root / "package.json").write_text('{"name": "code-server"}\n', encoding="utf-8")
    archive = tmp_path / "truncated.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    destination = tmp_path / "prefix" / "share" / "code-server"

    result = run_installer(*installer_args(tmp_path, archive, destination))

    assert result.returncode == 5
    assert "code editor archive is incomplete" in result.stderr
    assert not destination.exists()


def test_relative_destination_requires_an_environment_prefix(tmp_path: Path) -> None:
    args = installer_args(tmp_path, write_release(tmp_path), tmp_path / "unused")
    args[args.index("--destination") + 1] = "share/code-server"

    result = run_installer(*args, cwd=tmp_path)

    assert result.returncode == 4
    assert "not a pixi environment prefix" in result.stderr
    assert not (tmp_path / "share").exists()


def test_relative_destination_stays_inside_the_environment_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "prefix"
    (prefix / "conda-meta").mkdir(parents=True)
    monkeypatch.setattr(sys, "prefix", str(prefix))

    assert install.resolve_destination("share/code-server") == prefix / "share" / "code-server"

    empty_prefix = tmp_path / "empty-prefix"
    empty_prefix.mkdir()
    monkeypatch.setattr(sys, "prefix", str(empty_prefix))
    monkeypatch.chdir(prefix)

    assert install.resolve_destination("share/code-server") == prefix / "share" / "code-server"