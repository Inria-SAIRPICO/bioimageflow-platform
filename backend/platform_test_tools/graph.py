"""Ordinary executable tool declarations for platform contract tests.

These imported fixtures deliberately have their own finite source package.
They are not pytest test modules and contain no rewritten test callbacks.
"""

from pathlib import Path
from typing import Annotated, Any

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool, RowConsumption
from bioimageflow_core.types import ImageSpec, Semantic


class ProcInputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]
    diameter: float = 30.0


class ProcOutputs(IOModel):
    mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class MockProcessingTool(ProcessingTool):

    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = ProcInputs
    Outputs = ProcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class IncompatibleCoreTool(MockProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(
        name="test-incompatible-core",
        dependencies={"pip": ["bioimageflow-core==0.0.0"]},
    )


class CompatInputs(IOModel):
    mask_input: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class CompatOutputs(IOModel):
    result: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class CompatTool(ProcessingTool):

    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = CompatInputs
    Outputs = CompatOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class IncompatInputs(IOModel):
    img: Annotated[Path, ImageSpec(semantics={Semantic.DISPLACEMENT})]


class IncompatOutputs(IOModel):
    out: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class IncompatTool(ProcessingTool):

    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = IncompatInputs
    Outputs = IncompatOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class IntParamInputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]
    n: int = 1


class IntParamTool(ProcessingTool):

    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = IntParamInputs
    Outputs = ProcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class DFInputs(IOModel):
    threshold: float = 0.5


class MockDataFrameTool(DataFrameTool):
    Inputs = DFInputs


class TemplateOutputs(IOModel):
    result: Path


class TemplateTool(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = IOModel
    Outputs = TemplateOutputs

    def process_row(self, arguments: Any, *, context: Any = None) -> TemplateOutputs:
        output_path = Path(arguments.result)
        output_path.write_text("ok")
        return TemplateOutputs(result=output_path)


class SourceDFInputs(IOModel):
    path: str = "/tmp"


class MockSourceDataFrameTool(DataFrameTool):
    """A source-only DataFrameTool that refuses positional upstream args."""
    accepts_upstream = False
    Inputs = SourceDFInputs


class _SrcInputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]


class _SrcOutputs(IOModel):
    mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class SrcTool(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _SrcInputs
    Outputs = _SrcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class _DstInputs(IOModel):
    mask_input: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class _DstOutputs(IOModel):
    result: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class DstTool(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _DstInputs
    Outputs = _DstOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class _TwoInputDstInputs(IOModel):
    left_mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]
    right_mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class TwoInputDstTool(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _TwoInputDstInputs
    Outputs = _DstOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class _DFInputs(IOModel):
    threshold: float = 0.5


class DFTool(DataFrameTool):
    Inputs = _DFInputs
