"""Platform policy for human-facing latest workflow outputs."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bioimageflow import Workflow
from bioimageflow.storage import OutputViewCapability, Storage
from bioimageflow.storage import validate_relative_posix_path

logger = logging.getLogger(__name__)

MaterializedOutputMode = Literal["pointer", "symlink"]


def remove_latest_node_outputs(storage_path: Path, node_ids: list[str]) -> None:
    """Remove disposable latest projections for explicitly cleared nodes."""

    root = Path(storage_path)
    for node_id in node_ids:
        parts = validate_relative_posix_path(node_id).split("/")
        pointer = root / "views" / "latest" / Path(*parts[:-1]) / (
            f"{parts[-1]}.bioimageflow-link.json"
        )
        legacy_pointer = root / "latest" / Path(*parts[:-1]) / (
            f"{parts[-1]}.bioimageflow-link.json"
        )
        materialized = root / "outputs" / "latest" / Path(*parts)
        for path in (pointer, legacy_pointer, materialized):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)


@dataclass(frozen=True)
class ResolvedLatestOutputMode:
    """Resolved materialization mode plus a user-facing fallback warning."""

    effective: MaterializedOutputMode
    warning: str | None = None


def probe_latest_output_modes(storage_path: Path) -> dict[str, OutputViewCapability]:
    """Probe the cheap latest-view modes on the actual filesystem."""
    storage = Storage(storage_path)
    return {mode: storage.probe_output_view_mode(mode) for mode in ("pointer", "symlink")}


def resolve_latest_output_mode(
    storage_path: Path,
    *,
    capabilities: dict[str, OutputViewCapability] | None = None,
) -> ResolvedLatestOutputMode:
    """Prefer links and fall back to portable pointers, never copies."""
    capabilities = capabilities or probe_latest_output_modes(storage_path)
    if capabilities["symlink"].supported:
        return ResolvedLatestOutputMode(effective="symlink")
    pointer = capabilities["pointer"]
    if not pointer.supported:
        detail = pointer.detail or "The filesystem rejected portable pointer files."
        raise OSError(f"No latest output view can be created ({pointer.code}). {detail}")
    return ResolvedLatestOutputMode(
        effective="pointer",
        warning=(
            "Symbolic links are unavailable on this filesystem. Latest outputs "
            "will use portable BioImageFlow pointer files until link permissions "
            "are enabled."
        ),
    )


def materialize_latest_outputs(
    workflow: Workflow,
    *,
    storage_path: Path,
) -> ResolvedLatestOutputMode:
    """Publish per-node latest outputs using the platform policy.

    This explicit platform operation is intentionally called outside the library's
    automatic output-view policy. A failed symlink publish receives the same pointer
    fallback as a failed capability probe.
    """
    resolved = resolve_latest_output_mode(storage_path)
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
            effective="pointer",
            warning=(
                "Symbolic-link materialization failed at execution time. Latest outputs "
                "were published as portable BioImageFlow pointer files instead."
            ),
        )
