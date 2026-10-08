"""Ordinary Core-only source for the managed output-template browser proof."""

from pathlib import Path

from bioimageflow_core import Arguments, EnvironmentSpec, IOModel, ProcessingTool, RowConsumption, Template


class TemplateReport(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(
        name="platform-template-report",
        dependencies={"python": "3.12", "pip": ["bioimageflow-core>=0.5,<0.6"]},
        allow_flexible_versions=True,
    )

    class Inputs(IOModel):
        pass

    class Outputs(IOModel):
        result: Path = Template("initial_{row_index}.txt")

    def process_row(self, arguments: Arguments) -> Outputs:
        result = Path(arguments.result)
        result.write_text("ok")
        return self.Outputs(result=result)
