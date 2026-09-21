#!/usr/bin/env python3
"""Download and unpack the pinned code-server release into an environment prefix.

Runs as a Wetlands ``post_install`` step inside the managed environment, so it
may only use the standard library. Every failure mode exits non-zero with a
message on stderr, which Wetlands forwards in the provisioning failure payload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath
from urllib.error import URLError
from urllib.request import urlopen

CHUNK_SIZE = 1024 * 1024
PROGRESS_INTERVAL = 16 * CHUNK_SIZE
STAMP_NAME = ".bioimageflow-install.json"
EXIT_DIGEST_MISMATCH = 2
EXIT_DOWNLOAD_FAILED = 3
EXIT_BAD_PREFIX = 4
EXIT_BAD_ARCHIVE = 5


class ArchiveLayoutError(Exception):
    """Raised when the release archive does not match the expected layout."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and unpack the code editor runtime into an environment prefix.",
    )
    parser.add_argument("--url", required=True, help="release archive URL")
    parser.add_argument("--sha256", required=True, help="expected archive SHA-256, lowercase hex")
    parser.add_argument("--destination", required=True, help="install directory, relative to the prefix")
    parser.add_argument("--installer-revision", required=True, help="installer revision recorded in the stamp")
    parser.add_argument("--timeout", type=float, default=300.0, help="download timeout in seconds")
    return parser.parse_args(argv)


def resolve_destination(raw: str) -> Path | None:
    """Return the absolute install directory, or None outside an environment prefix."""
    destination = Path(raw).expanduser()
    if destination.is_absolute():
        return destination
    for base in (Path(sys.prefix), Path.cwd()):
        if (base / "conda-meta").is_dir():
            return base / destination
    return None


def already_installed(stamp: Path, destination: Path, expected_digest: str) -> bool:
    if not (destination / "package.json").is_file():
        return False
    try:
        payload = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    return str(payload.get("sha256", "")).lower() == expected_digest.lower()


def download(url: str, target: Path, *, timeout: float) -> str:
    """Stream the archive to ``target`` and return the SHA-256 of what was written."""
    digest = hashlib.sha256()
    with urlopen(url, timeout=timeout) as response, target.open("wb") as handle:
        length = response.headers.get("Content-Length")
        total = int(length) if length and length.isdigit() else None
        downloaded = 0
        next_report = PROGRESS_INTERVAL
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
            downloaded += len(chunk)
            if downloaded >= next_report:
                next_report += PROGRESS_INTERVAL
                report_progress(downloaded, total)
    return digest.hexdigest()


def report_progress(downloaded: int, total: int | None) -> None:
    mebibytes = downloaded / CHUNK_SIZE
    if total:
        print(f"Downloaded {mebibytes:.0f}/{total / CHUNK_SIZE:.0f} MiB", file=sys.stderr)
    else:
        print(f"Downloaded {mebibytes:.0f} MiB", file=sys.stderr)


def entrypoint(root: Path) -> Path:
    """Return the executable the platform launches from the unpacked bundle."""
    if sys.platform == "win32":
        return root / "lib" / "node.exe"
    return root / "bin" / "code-server"


def is_safe_relative(relative: str) -> bool:
    if not relative or relative.startswith("/") or os.path.isabs(relative):
        return False
    return not any(part in {"", ".."} for part in PurePosixPath(relative).parts)


def within(root: Path, candidate: Path) -> bool:
    resolved_root = Path(os.path.realpath(root))
    resolved = Path(os.path.realpath(candidate))
    return resolved == resolved_root or resolved_root in resolved.parents


def create_symlink(staging: Path, relative: str, linkname: str) -> None:
    target = staging / relative
    if not within(staging, target.parent / linkname):
        print(f"Skipping symlink leaving the archive root: {relative} -> {linkname}", file=sys.stderr)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(linkname, target)
    except (OSError, NotImplementedError) as exc:
        print(f"Could not create symlink {relative}: {exc}", file=sys.stderr)


def extract(archive: Path, staging: Path) -> None:
    """Extract ``archive`` into ``staging``, stripping the release's root directory."""
    staging.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        roots = {
            name.split("/", 1)[0]
            for name in (member.name.replace("\\", "/") for member in members)
            if name and name != "."
        }
        if len(roots) != 1:
            raise ArchiveLayoutError(
                f"expected a single archive root directory, found {sorted(roots)[:5]}"
            )
        root = roots.pop()
        if root in {"", ".", ".."}:
            raise ArchiveLayoutError(f"invalid archive root directory: {root!r}")
        for member in members:
            name = member.name.replace("\\", "/")
            relative = name.split("/", 1)[1] if "/" in name else ""
            if not relative:
                continue
            if not is_safe_relative(relative):
                raise ArchiveLayoutError(f"unsafe archive member: {member.name}")
            target = staging / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.issym():
                create_symlink(staging, relative, member.linkname)
            elif member.isfile() or member.islnk():
                source = tar.extractfile(member)
                if source is None:
                    raise ArchiveLayoutError(f"unreadable archive member: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with source, target.open("wb") as handle:
                    shutil.copyfileobj(source, handle)
                os.chmod(target, member.mode & 0o777)
            else:
                print(f"Skipping unsupported archive member: {member.name}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    destination = resolve_destination(args.destination)
    if destination is None:
        print(f"not a pixi environment prefix: {args.destination}", file=sys.stderr)
        return EXIT_BAD_PREFIX
    stamp = destination / STAMP_NAME
    if already_installed(stamp, destination, args.sha256):
        print(f"code editor runtime already installed at {destination}")
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive = destination.parent / f".code-server-download-{os.getpid()}"
    staging = destination.parent / f".code-server-staging-{os.getpid()}"
    try:
        print(f"Downloading {args.url}", file=sys.stderr)
        try:
            digest = download(args.url, archive, timeout=args.timeout)
        except (OSError, URLError) as exc:
            print(f"code editor archive download failed: {exc}", file=sys.stderr)
            return EXIT_DOWNLOAD_FAILED
        if digest.lower() != args.sha256.lower():
            print(
                f"code editor archive digest mismatch: expected {args.sha256.lower()} got {digest}",
                file=sys.stderr,
            )
            return EXIT_DIGEST_MISMATCH
        try:
            extract(archive, staging)
        except ArchiveLayoutError as exc:
            print(f"unexpected code editor archive layout: {exc}", file=sys.stderr)
            return EXIT_BAD_ARCHIVE
        executable = entrypoint(staging)
        if not executable.is_file():
            print(
                f"code editor archive is incomplete: missing {executable.relative_to(staging)}",
                file=sys.stderr,
            )
            return EXIT_BAD_ARCHIVE
        shutil.rmtree(destination, ignore_errors=True)
        os.replace(staging, destination)
        (destination / "extensions").mkdir(parents=True, exist_ok=True)
        stamp.write_text(
            json.dumps(
                {
                    "url": args.url,
                    "sha256": args.sha256,
                    "installer_revision": args.installer_revision,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"code editor runtime installed at {destination}")
        return 0
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        archive.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())