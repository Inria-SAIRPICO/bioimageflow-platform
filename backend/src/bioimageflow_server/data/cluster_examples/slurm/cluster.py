"""Example site-owned managed Slurm cluster configuration."""

from datetime import timedelta
from pathlib import Path

from bioimageflow.cluster import (
    ClusterEnvironment,
    ParslConfiguration,
    RemoteCluster,
    SchedulerJob,
    SetupScript,
)


HERE = Path(__file__).resolve().parent


cluster = RemoteCluster(
    host="my-hpc",
    root="/cluster/project/ACCOUNT/bioimageflow",
    environment=ClusterEnvironment.from_existing_python(
        "/shared/apps/bioimageflow/2026.08/bin/python"
    ),
    parsl=ParslConfiguration.from_file(
        HERE / "parsl.py",
        kwargs={"account": "ACCOUNT", "partition": "compute"},
    ),
    orchestrator=SchedulerJob(
        scheduler="slurm",
        queue="compute",
        project="ACCOUNT",
        walltime=timedelta(hours=4),
        cpu=4,
    ),
    setup=SetupScript.from_file(HERE / "setup.sh"),
)
