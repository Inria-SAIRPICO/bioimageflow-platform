"""Integration checks for BioImageFlow output template overrides."""

from pathlib import Path
from typing import Any

from bioimageflow import Workflow
from bioimageflow.engine import DefaultEngine
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool


class _TemplateOutputs(IOModel):
    result: Path


class _TemplateTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = IOModel
    Outputs = _TemplateOutputs

    def process_row(self, arguments: Any, *, context: Any = None) -> _TemplateOutputs:
        output_path = Path(arguments.result)
        output_path.write_text("ok")
        return _TemplateOutputs(result=output_path)


def _workflow_dict(template: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "template_test",
        "display_name": "Template test",
        "interface": {
            "inputs": [],
            "outputs": [
                {
                    "id": "output-result",
                    "name": "result",
                    "schema": {"type": "Path"},
                    "source": {"node": "write", "column": "result"},
                }
            ],
        },
        "nodes": [
            {
                "name": "write",
                "type": "tool",
                "tool_module": __name__,
                "tool_class": "_TemplateTool",
                "tool_package": None,
                "tool_package_version": None,
                "constants": {},
                "output_templates": {"result": template},
            },
        ],
        "edges": [],
        "config": {
            "storage_path": "./bif_data",
            "engine": "direct",
            "execution": "parallel",
        },
    }


def test_workflow_from_dict_uses_node_output_template(tmp_path: Path) -> None:
    workflow = Workflow.from_dict(
        _workflow_dict("custom_{row_index}.txt"),
        storage_path_override=tmp_path,
    )

    df = workflow.compute(engine=DefaultEngine())
    output_path = Path(df.at["0", "result"])

    assert output_path.name == "custom_0.txt"
    assert output_path.parent.name == "assets"
    assert output_path.exists()
    assert workflow.to_dict()["nodes"][0]["output_templates"] == {
        "result": "custom_{row_index}.txt",
    }


def test_output_template_changes_execution_signature(tmp_path: Path) -> None:
    workflow_a = Workflow.from_dict(
        _workflow_dict("first_{row_index}.txt"),
        storage_path_override=tmp_path,
    )
    df_a = workflow_a.compute(engine=DefaultEngine())

    workflow_b = Workflow.from_dict(
        _workflow_dict("second_{row_index}.txt"),
        storage_path_override=tmp_path,
    )
    df_b = workflow_b.compute(engine=DefaultEngine())

    first_path = Path(df_a.at["0", "result"])
    second_path = Path(df_b.at["0", "result"])
    assert first_path.name == "first_0.txt"
    assert second_path.name == "second_0.txt"
    assert first_path.parent.parent != second_path.parent.parent
