"""Worker fixture: importable using only the worker's core dependency."""

import os
from pathlib import Path

from bioimageflow_core import Arguments, EnvironmentSpec, IOModel, ProcessingTool, RowConsumption, Template


class WorkerNumbers(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(
        name="platform-worker-numbers", dependencies={"python": "3.12"},
    )

    class Inputs(IOModel):
        value: int
        multiplier: int = 3

    class Outputs(IOModel):
        multiplied: int
        process_id: int
        report: Path = Template("number_{row_index}.txt")

    def process_row(self, arguments: Arguments) -> Outputs:
        multiplied = arguments.value * arguments.multiplier
        report = Path(arguments.report)
        report.write_text(f"{arguments.value} * {arguments.multiplier} = {multiplied}\n")
        return self.Outputs(
            multiplied=multiplied,
            process_id=os.getpid(),
            report=report,
        )
