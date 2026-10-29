"""Ordinary source declarations for workflow constant compilation tests."""

from pathlib import Path
from typing import Any

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core.tool import IOModel


class ParameterInputs(IOModel):
    amount: float = 2.5
    values: list[Any] = []
    coordinates: tuple[Any, ...] = ()
    path: Path = Path("default.tiff")
    optional: float | None = 4.5
    enabled: bool = False


class ParameterOutputs(IOModel):
    result: int


class WorkflowParameterTool(DataFrameTool):
    accepts_upstream = False
    Inputs = ParameterInputs
    Outputs = ParameterOutputs

    def transform(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Constant compilation must not execute the fixture")
