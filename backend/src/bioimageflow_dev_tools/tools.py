"""Development scientific declarations, separate from router and bundled assets."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel
from bioimageflow_core.types import ImageSpec
from PIL import Image


class SeedNumberInputs(IOModel):
    pass


class SeedNumberOutputs(IOModel):
    number: int
    label: str


class SeedNumbers(DataFrameTool):
    """Small deterministic source tool used by hermetic E2E execution tests."""

    display_name = "Seed Numbers"
    documentation = "Create a deterministic three-row dataframe for development tests."
    tags = ["source", "e2e"]
    accepts_upstream = False
    Inputs = SeedNumberInputs
    Outputs = SeedNumberOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        import pandas as pd

        return pd.DataFrame(
            {
                "number": [1, 2, 3],
                "label": ["one", "two", "three"],
            },
        )


class ResultTableFixtureOutputs(IOModel):
    source_row: int
    label: str
    score: int


class ResultTableFixture(DataFrameTool):
    """Larger deterministic source used to exercise Node Data projections."""

    display_name = "Result Table Fixture"
    documentation = "Create deterministic rows for Node Data browser tests."
    tags = ["source", "e2e"]
    accepts_upstream = False
    Inputs = SeedNumberInputs
    Outputs = ResultTableFixtureOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        source_rows = list(range(60))
        return pd.DataFrame(
            {
                "source_row": source_rows,
                "label": [
                    f"{'keep' if row % 2 == 0 else 'drop'}-{row:02d}"
                    for row in source_rows
                ],
                "score": [(row * 17) % 61 for row in source_rows],
            },
        )


class ImageResultFixtureOutputs(IOModel):
    mask: Annotated[Path, ImageSpec()]
    report: Path


class ImageResultFixture(DataFrameTool):
    """Typed output schema used by the result image and file GUI journey."""

    display_name = "Image Result Fixture"
    documentation = "Expose deterministic image and file results for development tests."
    tags = ["image", "result", "e2e"]
    accepts_upstream = False
    Inputs = SeedNumberInputs
    Outputs = ImageResultFixtureOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        import os
        import tempfile

        output_dir = Path(tempfile.gettempdir()) / f"bioimageflow-e2e-image-result-{os.getpid()}"
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / "mask.png"
        Image.fromarray(np.arange(64, dtype=np.uint8).reshape(8, 8)).save(image_path)
        report_path = output_dir / "measurements.txt"
        report_path.write_bytes(b"cell_count=7\nmean_intensity=31.5\n")
        return pd.DataFrame({
            "mask": [str(image_path)],
            "report": [str(report_path)],
        })


class IncrementNumberInputs(IOModel):
    number: int


class IncrementNumberOutputs(IOModel):
    number_plus_one: int


class IncrementNumbers(DataFrameTool):
    """Deterministic transform tool used by graph-validation E2E tests."""

    display_name = "Increment Numbers"
    documentation = "Add one to an upstream number column for development tests."
    tags = ["transform", "e2e"]
    Inputs = IncrementNumberInputs
    Outputs = IncrementNumberOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        result = df.copy()
        result["number_plus_one"] = result["number"] + 1
        return result


class ControlledDirectInputs(IOModel):
    fail: bool = False


class ControlledDirectOutputs(IOModel):
    number_plus_one: int


class ControlledDirectNumbers(DataFrameTool):
    """Fail on demand inside a real Direct DataFrame transformation."""

    display_name = "Controlled Direct Numbers"
    documentation = "Increment upstream numbers, or raise a controlled execution error."
    tags = ["transform", "e2e"]
    Inputs = ControlledDirectInputs
    Outputs = ControlledDirectOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        if arguments.fail:
            raise RuntimeError("Controlled Direct failure")
        result = df.copy()
        result["number_plus_one"] = result["number"] + 1
        return result


class IncrementAgainInputs(IOModel):
    number_plus_one: int


class IncrementAgainOutputs(IOModel):
    number_plus_two: int


class IncrementAgainNumbers(DataFrameTool):
    """Second deterministic transform for recursive E2E execution tests."""

    display_name = "Increment Again"
    documentation = "Add one to an upstream number_plus_one column for development tests."
    tags = ["transform", "e2e"]
    Inputs = IncrementAgainInputs
    Outputs = IncrementAgainOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        result = df.copy()
        result["number_plus_two"] = result["number_plus_one"] + 1
        return result
