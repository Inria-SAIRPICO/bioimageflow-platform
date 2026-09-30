"""Worker-importable processing recipes using only BioImageFlow Core."""

from bioimageflow_core import EnvironmentSpec, RowConsumption

from tests.fixtures.worker_numbers import WorkerNumbers


class StaleWorkerNumbers(WorkerNumbers):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(
        name="platform-stale-worker-numbers", dependencies={"python": "3.12"},
    )


class IncompatibleWorkerNumbers(WorkerNumbers):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(
        name="platform-incompatible-worker",
        dependencies={"pip": ["bioimageflow-core==0.0.0"]},
    )
