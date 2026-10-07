"""Faithful installed-distribution metadata for temporary tool packages."""

import base64
import csv
import hashlib
import io
from pathlib import Path


def write_package_metadata(package_root: Path, version: str) -> None:
    """Record the exact current package members as one providing distribution."""
    installation = package_root.parent
    package = package_root.name
    distribution = package.replace("_", "-")
    metadata_root = installation / f"{package}-{version}.dist-info"
    metadata_root.mkdir(exist_ok=True)
    (metadata_root / "METADATA").write_text(
        f"Metadata-Version: 2.3\nName: {distribution}\nVersion: {version}\n"
    )
    (metadata_root / "top_level.txt").write_text(f"{package}\n")
    record_path = metadata_root / "RECORD"
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    members = sorted(
        path for root in (package_root, metadata_root) for path in root.rglob("*")
        if path.is_file() and path != record_path and "__pycache__" not in path.parts
    )
    for path in members:
        content = path.read_bytes()
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
        writer.writerow((path.relative_to(installation).as_posix(), f"sha256={digest.decode()}", len(content)))
    writer.writerow((record_path.relative_to(installation).as_posix(), "", ""))
    record_path.write_text(output.getvalue())
