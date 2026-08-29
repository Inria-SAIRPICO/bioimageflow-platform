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
    host="CHANGE_ME_SSH_ALIAS",
    root="/CHANGE_ME/shared/project/user/bioimageflow",
    environment=ClusterEnvironment.from_existing_python(
        "/CHANGE_ME/shared/apps/bioimageflow/bin/python"
    ),
    parsl=ParslConfiguration.from_file(
        HERE / "parsl.py",
        kwargs={
            "account": "CHANGE_ME_PROJECT",
            "partition": "CHANGE_ME_PARTITION",
        },
    ),
    orchestrator=SchedulerJob(
        scheduler="slurm",
        queue="CHANGE_ME_PARTITION",
        project="CHANGE_ME_PROJECT",
        walltime=timedelta(hours=4),
        cpu=4,
    ),
    setup=SetupScript.from_file(HERE / "setup.sh"),
)
