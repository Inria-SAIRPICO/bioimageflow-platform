#!/usr/bin/env python3
"""Select conservative platform CI jobs from changed repository paths."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Sequence


@dataclass(frozen=True)
class Selection:
    backend: bool
    frontend: bool
    documentation: bool
    chromium: bool

    @classmethod
    def all(cls) -> Selection:
        return cls(backend=True, frontend=True, documentation=True, chromium=True)


def select_jobs(paths: Sequence[str]) -> Selection:
    if not paths:
        return Selection.all()

    backend = False
    frontend = False
    documentation = False
    shared = False
    for raw_path in paths:
        path = PurePosixPath(raw_path)
        if not path.parts:
            shared = True
        elif path.parts[0] == "backend":
            backend = True
        elif path.parts[0] == "frontend":
            frontend = True
        elif path.parts[0] == "docs" or path.as_posix() == "README.md":
            documentation = True
        else:
            shared = True

    if shared:
        return Selection.all()
    return Selection(
        backend=backend,
        frontend=frontend,
        documentation=documentation,
        chromium=backend or frontend,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--all", action="store_true", dest="select_all")
    args = parser.parse_args(argv)
    selection = Selection.all() if args.select_all else select_jobs(args.paths)
    for name in ("backend", "frontend", "documentation", "chromium"):
        print(f"{name}={str(getattr(selection, name)).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
