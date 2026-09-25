"""Main-process results table for the parameter-space exploration demo."""

from typing import Any

import pandas as pd

from bioimageflow import DataFrameTool
from bioimageflow_core import Category, IOModel


class ParameterSweepResults(DataFrameTool):
    """Combine parameter rows, mask paths, counts, and the mosaic preview path."""

    display_name = "Parameter Sweep Results"
    category = Category.MEASUREMENT

    class Inputs(IOModel):
        pass

    class Outputs(IOModel):
        sensitivity: float
        size: int
        label_count: int
        mosaic_path: str

    def merge_dataframes(self, dfs: list[Any], arguments: Any) -> pd.DataFrame:
        if len(dfs) != 4:
            raise ValueError(
                "ParameterSweepResults expects parameter, detection, count, and mosaic tables."
            )
        parameters = pd.DataFrame(dfs[0]).reset_index(drop=True)
        detections = pd.DataFrame(dfs[1]).reset_index(drop=True)
        counts = pd.DataFrame(dfs[2]).reset_index(drop=True)
        mosaic = pd.DataFrame(dfs[3])
        results = pd.concat(
            [
                parameters,
                detections[
                    [
                        column
                        for column in detections.columns
                        if column not in parameters.columns
                    ]
                ],
                counts[
                    [
                        column
                        for column in counts.columns
                        if column not in parameters.columns
                    ]
                ],
            ],
            axis=1,
        )
        if "mosaic_path" in mosaic.columns and not mosaic.empty:
            results["mosaic_path"] = mosaic["mosaic_path"].iloc[0]
        if "image_count" in mosaic.columns and not mosaic.empty:
            results["image_count"] = int(mosaic["image_count"].iloc[0])
        return results
