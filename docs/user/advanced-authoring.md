# Advanced Python Authoring

A trusted desktop workflow can use `workflow.py` as an authoring source.
This is useful when a technical collaborator wants to define a graph with the BioImageFlow Python library and hand the materialized result to GUI users.

Python authoring is optional and is separate from workflow-local tool implementation.

## Authoring contract

Place `workflow.py` in the saved workflow's directory.
It must export a no-argument function named `build_workflow` and return a standalone BioImageFlow `Workflow`.

For example:

```python
from bioimageflow import Workflow


def build_workflow():
    return Workflow(
        name="python_definition",
        display_name="Python definition",
        engine="direct",
    )
```

The authoring directory may contain local Python helper files imported by `workflow.py`.
Do not use symlinks or references that escape the workflow directory.

## Build the GUI workflow

1. Open the saved workflow in BioImageFlow.
2. Ensure its current GUI changes are saved.
3. Choose **Workflow → Build from Python source**.
4. Review the replacement and any destructive effects in the confirmation.
5. Confirm to materialize and save the returned workflow.

BioImageFlow invokes `build_workflow` once in a fresh import context, converts the result into the same graph edited by the canvas, validates it, and stages its runtime source bundle.
It records a hash covering the allowed Python files so a changed helper or source causes the apply step to conflict instead of saving stale output.

After a successful build, edit the graph normally or rebuild it after changing the Python source.

## Execution and sharing

Python is an authoring input, not the saved execution model.
Run, reopen, nest, copy, and export operations use the materialized graph and its staged runtime sources; they do not import `workflow.py` again.

The build command accepts only the addressed workflow's own authoring source.
It does not accept arbitrary file paths or module names, and it is unavailable outside trusted desktop mode.
