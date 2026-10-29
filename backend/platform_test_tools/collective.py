"""A real collective declaration for column-edge presentation checks."""

from typing import Annotated

from bioimageflow_core import Connectable, GUIMeta, IOModel
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import ProcessingTool, RowConsumption


class CollectiveNumbers(ProcessingTool):
    """Consume aligned numbers together rather than independently."""

    display_name = "Collective Numbers"
    row_consumption = RowConsumption.COLLECTIVE
    environment = EnvironmentSpec(name="bioimageflow-e2e", dependencies={})

    class Inputs(IOModel):
        number: Annotated[int, GUIMeta(connectable=Connectable.BY_DEFAULT)]

    class Outputs(IOModel):
        total: int

    def process_batch(self, arguments_list, *, context=None):
        return [self.Outputs(total=sum(arguments.number for arguments in arguments_list))]
