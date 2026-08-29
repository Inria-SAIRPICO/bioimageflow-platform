"""Trusted BioImageFlow Platform target for one managed Slurm cluster."""

from datetime import timedelta

from bioimageflow.cluster import (
    ClusterEnvironment,
    ParslConfiguration,
    RemoteCluster,
    SchedulerJob,
    SetupScript,
)


cluster = RemoteCluster(
    host="CHANGE_ME_SSH_ALIAS",
    root="/CHANGE_ME/shared/project/user/bioimageflow",
    environment=ClusterEnvironment.from_existing_python(
        "/CHANGE_ME/shared/apps/bioimageflow/bin/python"
    ),
    parsl=ParslConfiguration.from_file(
        "parsl.py",
        kwargs={"account": "CHANGE_ME_PROJECT"},
    ),
    orchestrator=SchedulerJob(
        scheduler="slurm",
        queue="CHANGE_ME_PARTITION",
        project="CHANGE_ME_PROJECT",
        walltime=timedelta(hours=4),
        cpu=4,
    ),
    setup=SetupScript.from_file("setup.sh"),
)
