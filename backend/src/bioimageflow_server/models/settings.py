"""Application settings models."""

from typing import Literal

from pydantic import BaseModel


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
