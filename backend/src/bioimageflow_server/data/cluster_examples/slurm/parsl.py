"""Example Parsl worker configuration; replace site facts before use."""

from parsl import Config
from parsl.executors import HighThroughputExecutor
from parsl.providers import SlurmProvider

from bioimageflow.parsl import ParslFactoryResult, WorkerSlot


def build(runtime, *, account: str, partition: str) -> ParslFactoryResult:
    executor = HighThroughputExecutor(
        label="cpu-workers",
        cores_per_worker=1,
        max_workers_per_node=32,
        provider=SlurmProvider(
            account=account,
            partition=partition,
            nodes_per_block=1,
            cores_per_node=32,
            init_blocks=0,
            min_blocks=0,
            max_blocks=4,
            walltime="02:00:00",
            worker_init=runtime.worker_init,
        ),
    )
    binding = runtime.executor_binding(slot=WorkerSlot(cpu=1, memory="4 GB"))
    return ParslFactoryResult(
        config=Config(executors=[executor], retries=0),
        executor_bindings={"cpu-workers": binding},
    )
