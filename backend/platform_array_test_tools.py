"""Ordinary Core-only source declaration for the managed array lifetime check."""

import os

from bioimageflow_core import Arguments, EnvironmentSpec, IOModel, ProcessingTool, RowConsumption, SharedArray
from bioimageflow_core.shm import create_shared_output


class ManagedArray(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(
        name="platform-managed-array-lifetime", dependencies={"python": "3.12"},
    )

    class Inputs(IOModel):
        value: int

    class Outputs(IOModel):
        image: SharedArray
        value: int
        worker_pid: int

    def process_row(self, arguments: Arguments) -> Outputs:
        import numpy as np

        pixels = np.full((8, 8), arguments.value, dtype=np.uint16)
        with create_shared_output(pixels) as image:
            return self.Outputs(image=image, value=arguments.value, worker_pid=os.getpid())
