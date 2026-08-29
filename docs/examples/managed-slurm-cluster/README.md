---
orphan: true
---

# Managed Slurm Cluster Example

Copy these files to a private working directory and replace every `CHANGE_ME` value with facts supplied by your cluster site.

The BioImageFlow Platform profile selects `cluster.py`.
That file defines the required top-level `cluster = RemoteCluster(...)` value, requests one orchestrator job, and refers to `parsl.py` for separate worker allocations.
It resolves `parsl.py` and `setup.sh` relative to its own location, so keep the example files together when the platform starts from another working directory.

If your site does not require Modules or Spack initialization, remove `setup=SetupScript.from_file(HERE / "setup.sh")` from `cluster.py` and delete `setup.sh`.

These files are trusted executable code.
Review them before use and never write passwords, private keys, tokens, or other literal secrets into them.
