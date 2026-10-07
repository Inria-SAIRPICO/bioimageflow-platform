"""Core-only processing declarations for development graph admission."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from bioimageflow_core import IOModel
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import ProcessingTool, RowConsumption
from bioimageflow_core.types import ImageSpec


class GaussianBlurInputs(IOModel):
    input_image: Annotated[Path, ImageSpec()]
    sigma: float = 1.0


class GaussianBlurOutputs(IOModel):
    output_image: Annotated[Path, ImageSpec()]


class GaussianBlur(ProcessingTool):
    """Tiny executable image-processing fixture for E2E graph validation."""

    row_consumption = RowConsumption.MAPPED

    environment = EnvironmentSpec(name="bioimageflow-e2e", dependencies={})
    Inputs = GaussianBlurInputs
    Outputs = GaussianBlurOutputs

    def process_row(self, arguments: Any, *, context: Any = None) -> Any:
        return GaussianBlurOutputs(output_image=Path("output.tif"))
