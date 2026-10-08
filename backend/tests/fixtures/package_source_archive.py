"""Create a finite local source archive for real package-installer browser tests."""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import zipfile


PACKAGE = "e2e_local_package_tools"
VERSIONS = ("1.0", "1.0.0")

TOOL_SOURCE = '''"""Ordinary Core-only declarations; package tests do not execute this tool."""

from bioimageflow_core import Arguments, EnvironmentSpec, IOModel, ProcessingTool, RowConsumption

__version__ = {version!r}


class LocalPackageNumbers(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(
        name="e2e-local-package-numbers",
        dependencies={{"python": "3.12", "pip": ["bioimageflow-core>=0.5,<0.6"]}},
        allow_flexible_versions=True,
    )

    class Inputs(IOModel):
        value: int

    class Outputs(IOModel):
        number: int

    def process_row(self, arguments: Arguments) -> Outputs:
        return self.Outputs(number=arguments.value)
'''

BUILD_BACKEND = '''"""Self-contained PEP 517 backend producing one ordinary pure-Python wheel."""

import base64
import csv
import hashlib
import io
from pathlib import Path
import zipfile

PACKAGE = "e2e_local_package_tools"
VERSION = {version!r}


def get_requires_for_build_wheel(config_settings=None):
    return []


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    metadata_root = f"{{PACKAGE}}-{{VERSION}}.dist-info"
    members = {{
        f"{{PACKAGE}}/__init__.py": (
            Path(__file__).parent / PACKAGE / "__init__.py"
        ).read_bytes(),
        f"{{metadata_root}}/METADATA": (
            "Metadata-Version: 2.3\\n"
            "Name: e2e-local-package-tools\\n"
            f"Version: {{VERSION}}\\n"
            "Summary: Local package lifecycle fixture\\n"
        ).encode("utf-8"),
        f"{{metadata_root}}/WHEEL": (
            "Wheel-Version: 1.0\\n"
            "Generator: platform-local-fixture\\n"
            "Root-Is-Purelib: true\\n"
            "Tag: py3-none-any\\n"
        ).encode("utf-8"),
        f"{{metadata_root}}/top_level.txt": f"{{PACKAGE}}\\n".encode("utf-8"),
    }}
    record_path = f"{{metadata_root}}/RECORD"
    record = io.StringIO(newline="")
    writer = csv.writer(record)
    for name, content in sorted(members.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
        writer.writerow((name, f"sha256={{digest.decode('ascii')}}", len(content)))
    writer.writerow((record_path, "", ""))
    members[record_path] = record.getvalue().encode("utf-8")
    filename = f"{{PACKAGE}}-{{VERSION}}-py3-none-any.whl"
    with zipfile.ZipFile(Path(wheel_directory) / filename, "w", zipfile.ZIP_DEFLATED) as wheel:
        for name, content in sorted(members.items()):
            wheel.writestr(name, content)
    return filename
'''


def write_package_source_archive(output: Path, version: str) -> None:
    """Write only a new caller-owned ZIP in an already established directory."""
    if version not in VERSIONS:
        raise ValueError(f"Version must be one of {VERSIONS!r}")
    if not output.is_absolute() or output.suffix.lower() != ".zip":
        raise ValueError("Output must be an absolute .zip path")
    if not output.parent.is_dir():
        raise ValueError("Output parent must already exist")
    content = BytesIO()
    with zipfile.ZipFile(content, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "pyproject.toml",
            '[build-system]\nrequires = []\nbuild-backend = "build_backend"\nbackend-path = ["."]\n',
        )
        archive.writestr("build_backend.py", BUILD_BACKEND.format(version=version))
        archive.writestr(f"{PACKAGE}/__init__.py", TOOL_SOURCE.format(version=version))
    with output.open("xb") as handle:
        handle.write(content.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", choices=VERSIONS, required=True)
    arguments = parser.parse_args()
    write_package_source_archive(arguments.output, arguments.version)


if __name__ == "__main__":
    main()
