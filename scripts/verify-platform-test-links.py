#!/usr/bin/env python3
"""Check local Markdown links in the active campaign working set."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_DIR = ROOT / "docs/developer"
ACTIVE_FILES = sorted((*CAMPAIGN_DIR.glob("platform-test-*.md"), *CAMPAIGN_DIR.glob("coverage-*.md")))
LINK = re.compile(r"(?<!!)\[[^\]]+\]\((?P<target>[^\s)]+)(?:\s+\"[^\"]*\")?\)")


def main() -> int:
    failures: list[str] = []
    checked = 0
    for source in ACTIVE_FILES:
        for line_number, line in enumerate(source.read_text().splitlines(), 1):
            for match in LINK.finditer(line):
                target = unquote(match.group("target"))
                parts = urlsplit(target)
                if parts.scheme or parts.netloc or not parts.path:
                    continue
                checked += 1
                resolved = (source.parent / parts.path).resolve()
                if not resolved.is_file():
                    failures.append(f"{source.relative_to(ROOT)}:{line_number}: missing local link {target}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Verified {checked} local links in {len(ACTIVE_FILES)} active campaign files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
