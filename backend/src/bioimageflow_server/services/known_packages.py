"""Known-packages list service (spec v3 §2.5).

Resolves the list of BioImageFlow tool packages the server is aware of.
Precedence:

1. User file at ``~/.bioimageflow/known_packages.txt`` (if present).
2. Bundled default at ``bioimageflow_server/data/default_known_packages.txt``.

Lines starting with ``#`` are comments; blank lines are skipped; trailing
inline ``# ...`` comments are stripped.
"""

from __future__ import annotations

import logging
from importlib import resources
from pathlib import Path

logger = logging.getLogger(__name__)


class KnownPackagesService:
    def __init__(self, user_path: Path, bundled_path: Path) -> None:
        self._user_path = user_path
        self._bundled_path = bundled_path

    @classmethod
    def default(cls) -> "KnownPackagesService":
        from bioimageflow.paths import get_home

        user_path = get_home() / "known_packages.txt"
        bundled_path = Path(
            str(
                resources.files("bioimageflow_server.data").joinpath(
                    "default_known_packages.txt"
                )
            )
        )
        return cls(user_path=user_path, bundled_path=bundled_path)

    def list_known_packages(self) -> list[str]:
        if self._user_path.is_file():
            try:
                return _parse(self._user_path.read_text(encoding="utf-8"))
            except OSError:
                logger.warning(
                    "Could not read user known_packages file at %s", self._user_path
                )
        if self._bundled_path.is_file():
            try:
                return _parse(self._bundled_path.read_text(encoding="utf-8"))
            except OSError:
                logger.warning(
                    "Could not read bundled known_packages file at %s",
                    self._bundled_path,
                )
        logger.warning(
            "No known_packages file available (user=%s, bundled=%s); returning empty list",
            self._user_path,
            self._bundled_path,
        )
        return []


def _parse(text: str) -> list[str]:
    names: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "#" in line:
            line = line.split("#", 1)[0].strip()
        if line:
            names.append(line)
    return names
