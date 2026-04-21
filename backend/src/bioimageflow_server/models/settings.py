"""Application settings models."""

from __future__ import annotations

import posixpath
from typing import Literal

from pydantic import BaseModel


_DEFAULT_MAX_UPLOAD_SIZE = 2 * 1024**3  # 2 GB (v1 §2.4.10)


class OMEROInstance(BaseModel):
    """OMERO server connection configuration."""

    name: str | None = None
    host: str
    port: int = 4064
    username: str


class Settings(BaseModel):
    """Application settings from GET/PATCH /settings."""

    deployment_mode: Literal["desktop", "webapp"]
    external_editor: str | None = None
    napari_env_path: str | None = None
    omero_instances: list[OMEROInstance] = []
    output_data_folder: str
    tool_store_path: str = "~/.bioimageflow/tool_packages/"
    update_mode: Literal["auto", "manual"] | str = "auto"
    execution_engine: Literal["sequential", "parsl"] = "sequential"
    cache_max_executions: int | None = None
    cache_max_age: str | None = None
    keyboard_shortcuts: dict[str, str] = {}
    dev_mode: bool = True
    datasets_root: str | None = None
    max_upload_size: int = _DEFAULT_MAX_UPLOAD_SIZE

    def resolved_datasets_root(self) -> str:
        """Return `datasets_root` if set, else `<output_data_folder>/datasets`."""
        if self.datasets_root:
            return self.datasets_root
        return posixpath.join(self.output_data_folder, "datasets")
