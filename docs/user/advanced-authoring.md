# Build Workflows from Python

> **Available in:** Desktop only, for trusted local source.

Use Python authoring when a technical collaborator wants to define a saved workflow with the BioImageFlow Python library and then hand it to canvas users.
This is optional and is separate from [creating a workflow-local tool](create-custom-tools.md).

## Create the source

Place `workflow.py` in the saved workflow's directory.
It must define a no-argument function named `build_workflow` that returns a BioImageFlow `Workflow`.

```python
from bioimageflow import Workflow


def build_workflow():
    return Workflow(
        name="python_definition",
        display_name="Python definition",
        engine="direct",
    )
```

The directory can contain local Python helpers imported by `workflow.py`.
Do not use links or imports that escape the workflow directory.

```{warning}
Building from Python executes local code.
Use this command only for source you trust and have reviewed.
```

## Build the canvas workflow

1. Open the saved workflow in BioImageFlow.
2. Save its current canvas changes.
3. Choose **Workflow → Build from Python source**.
4. Review the replacement described by the confirmation.
5. Confirm to build, validate, and save the returned workflow.

After a successful build, edit the graph on the canvas or rebuild it after changing the Python source.

Python is an authoring source, not a requirement for later execution.
Opening, running, copying, nesting, and exporting use the saved graph and its workflow-local sources without importing `workflow.py` again.
