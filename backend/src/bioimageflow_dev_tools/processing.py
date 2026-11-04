"""Core-only processing declarations for development graph admission."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from bioimageflow_core import IOModel
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import ProcessingTool, RowConsumption, Template
from bioimageflow_core.types import ImageSpec


class GaussianBlurInputs(IOModel):
    input_image: Annotated[Path, ImageSpec()]
    sigma: float = 1.0


class GaussianBlurOutputs(IOModel):
    output_image: Annotated[Path, ImageSpec()] = Template("{node_name}_{row_index}{ext}")


class GaussianBlur(ProcessingTool):
    """Tiny executable image-processing fixture for E2E graph validation."""

    row_consumption = RowConsumption.MAPPED

    environment = EnvironmentSpec(name="bioimageflow-e2e", dependencies={})
    Inputs = GaussianBlurInputs
    Outputs = GaussianBlurOutputs

    def process_row(self, arguments: Any, *, context: Any = None) -> Any:
        return GaussianBlurOutputs(output_image=Path(arguments.output_image))


class WriteNumberFile(ProcessingTool):
    """Write one small file per number to exercise real output collisions."""

    display_name = "Write Number File"
    documentation = "Write a number into its declared output file."
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(
        name="bioimageflow-e2e-output-files", dependencies={"python": "3.12"},
    )

    class Inputs(IOModel):
        number: int

    class Outputs(IOModel):
        report: Path = Template("result.txt")

    def process_row(self, arguments: Any, *, context: Any = None) -> Any:
        report = Path(arguments.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(str(arguments.number))
        return self.Outputs(report=report)
