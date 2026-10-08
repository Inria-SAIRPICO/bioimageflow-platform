"""Finite ordinary Core-only declarations for manual environment lifecycle proofs."""

import os
from pathlib import Path

from bioimageflow_core import Arguments, EnvironmentSpec, IOModel, ProcessingTool, RowConsumption, Template


class LifecycleSelected(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(
        name="platform-tool-selected",
        dependencies={"python": "3.12", "pip": ["bioimageflow-core>=0.5,<0.6"]},
        allow_flexible_versions=True,
    )

    class Inputs(IOModel):
        value: int

    class Outputs(IOModel):
        multiplied: int
        process_id: int
        report: Path = Template("number_{row_index}.txt")

    def process_row(self, arguments: Arguments) -> Outputs:
        multiplied = arguments.value * 3
        report = Path(arguments.report)
        report.write_text(f"{arguments.value} * 3 = {multiplied}\n")
        return self.Outputs(multiplied=multiplied, process_id=os.getpid(), report=report)


class LifecycleSibling(LifecycleSelected):
    row_consumption = RowConsumption.MAPPED


class LifecycleOther(LifecycleSelected):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name="platform-tool-other", dependencies={"python": "3.12"})
