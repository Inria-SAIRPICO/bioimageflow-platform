"""Filesystem operations router."""

from __future__ import annotations

import os
import platform
import subprocess

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

router = APIRouter()


class RevealRequest(BaseModel):
    """Request body for the reveal endpoint."""

    path: str


def reveal_in_file_browser(path: str) -> None:
    """Open the given path in the system file browser.

    On macOS: ``open -R <path>``
    On Linux: ``xdg-open <parent>``
    On Windows: ``explorer /select,<path>``
    """
    path = os.path.abspath(path)
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", "-R", path])
    elif system == "Linux":
        target = os.path.dirname(path) if os.path.isfile(path) else path
        subprocess.Popen(["xdg-open", target])
    elif system == "Windows":
        subprocess.Popen(["explorer", "/select,", path])
    else:
        raise OSError(f"Unsupported platform: {system}")


@router.post("/fs/reveal")
async def reveal_path(body: RevealRequest) -> dict[str, str]:
    """Open the given path in the system file browser."""
    try:
        reveal_in_file_browser(body.path)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok"}
