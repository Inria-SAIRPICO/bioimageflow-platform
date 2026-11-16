"""Ordinary exact-output declarations for static warning authority tests."""

from pathlib import Path

from bioimageflow_core import Arguments, EnvironmentSpec, IOModel, ProcessingTool, RowConsumption, Template
from bioimageflow import DataFrameTool


class NumberInputs(IOModel):
    number: int = 1


class ConflictingOutputs(ProcessingTool):
    display_name = "Output writer"
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="platform-output-planning", dependencies={"python": "3.12"})
    Inputs = NumberInputs

    class Outputs(IOModel):
        left: Path = Template("same.txt")
        right: Path = Template("same.txt")

    def process_row(self, arguments: Arguments) -> Outputs:
        raise AssertionError("Static output inspection must not execute scientific callbacks")


class DistinctOutputs(ConflictingOutputs):
    row_consumption = RowConsumption.MAPPED

    class Outputs(IOModel):
        left: Path = Template("left_{number}.txt")
        right: Path = Template("right_{number}.txt")


class TimestampOutputs(ConflictingOutputs):
    row_consumption = RowConsumption.MAPPED

    class Outputs(IOModel):
        left: Path = Template("same_{timestamp}.txt")
        right: Path = Template("same_{timestamp}.txt")


class UnknownNumbers(DataFrameTool):
    accepts_upstream = False
    Inputs = IOModel

    class Outputs(IOModel):
        number: int

    def transform(self, dataframe, arguments):
        raise AssertionError("Static output inspection must not execute upstream transforms")
