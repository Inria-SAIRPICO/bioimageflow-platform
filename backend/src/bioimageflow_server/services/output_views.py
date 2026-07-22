"""Platform policy for human-facing latest workflow outputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bioimageflow import Workflow
from bioimageflow.storage import OutputViewCapability, Storage

from bioimageflow_server.models.settings import Settings


logger = logging.getLogger(__name__)

LatestOutputMode = Literal["auto", "pointer", "symlink", "copy"]
MaterializedOutputMode = Literal["pointer", "symlink", "copy"]


@dataclass(frozen=True)
class ResolvedLatestOutputMode:
    """Resolved materialization mode plus a user-facing fallback warning."""

    requested: LatestOutputMode
    effective: MaterializedOutputMode
    warning: str | None = None


def probe_latest_output_modes(storage_path: Path) -> dict[str, OutputViewCapability]:
    """Probe all user-selectable concrete modes on the actual filesystem."""
    storage = Storage(storage_path)
    return {
        mode: storage.probe_output_view_mode(mode)
        for mode in ("pointer", "symlink", "copy")
    }


def resolve_latest_output_mode(
    storage_path: Path,
    requested: LatestOutputMode,
    *,
    capabilities: dict[str, OutputViewCapability] | None = None,
) -> ResolvedLatestOutputMode:
    """Resolve the host preference without ever falling back to copying."""
    capabilities = capabilities or probe_latest_output_modes(storage_path)
    if requested == "auto":
        if capabilities["symlink"].supported:
            return ResolvedLatestOutputMode(requested=requested, effective="symlink")
        pointer = capabilities["pointer"]
        if not pointer.supported:
            detail = pointer.detail or "The filesystem rejected portable pointer files."
            raise OSError(
                f"No latest output view can be created ({pointer.code}). {detail}"
            )
        return ResolvedLatestOutputMode(
            requested=requested,
            effective="pointer",
            warning=(
                "Symbolic links are unavailable on this filesystem. Latest outputs "
                "will use portable BioImageFlow pointer files until link permissions "
                "are enabled."
            ),
        )
    capability = capabilities[requested]
    if capability.supported:
        return ResolvedLatestOutputMode(requested=requested, effective=requested)
    detail = capability.detail or "The filesystem rejected this output mode."
    if requested == "symlink":
        pointer = capabilities["pointer"]
        if not pointer.supported:
            pointer_detail = pointer.detail or "Portable pointer files are also unavailable."
            raise OSError(
                f"Symbolic links are unavailable ({capability.code}), and the pointer "
                f"fallback is unavailable ({pointer.code}). {pointer_detail}"
            )
        return ResolvedLatestOutputMode(
            requested=requested,
            effective="pointer",
            warning=(
                f"Symbolic links are unavailable ({capability.code}). {detail} "
                "Latest outputs will use portable BioImageFlow pointer files."
            ),
        )
    raise OSError(f"Latest output mode '{requested}' is unavailable ({capability.code}). {detail}")


def materialize_latest_outputs(
    workflow: Workflow,
    settings: Settings,
    *,
    storage_path: Path,
) -> ResolvedLatestOutputMode:
    """Publish per-node latest outputs using the host's selected policy.

    This explicit platform operation is intentionally called outside the library's
    automatic output-view policy. A failed symlink publish receives the same pointer
    fallback as a failed capability probe; copy failures remain failures.
    """
    resolved = resolve_latest_output_mode(storage_path, settings.latest_output_mode)
    try:
        workflow.export_outputs(mode=resolved.effective, scope="latest")
        return resolved
    except Exception:
        if resolved.effective != "symlink":
            raise
        logger.warning(
            "Symlink latest-output materialization failed; retrying with portable pointers",
            exc_info=True,
        )
        workflow.export_outputs(mode="pointer", scope="latest")
        return ResolvedLatestOutputMode(
            requested=resolved.requested,
            effective="pointer",
            warning=(
                "Symbolic-link materialization failed at execution time. Latest outputs "
                "were published as portable BioImageFlow pointer files instead."
            ),
        )
