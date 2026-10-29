#!/usr/bin/env python3
"""Compare backend workflow opening in isolated baseline/candidate processes.

Examples:
  backend/.venv/bin/python scripts/benchmark_workflow_loading.py \
    --workflow-dir 'backend/src/bioimageflow_server/data/demo_workflows/fish-analysis' \
    --tool-store ~/.bioimageflow/tool_packages --output /private/tmp/loading-baseline.json
  backend/.venv/bin/python scripts/benchmark_workflow_loading.py \
    --workflow-dir /path/to/owned/fixture --case populated-cache \
    --baseline-results /path/to/baseline/results --candidate-results /path/to/candidate/results \
    --candidate-python /path/to/candidate/python --output /private/tmp/loading-comparison.json

Only workflow.json, an optional draft and contained tools are copied from the input.
Results are copied only from an explicit bounded fixture; no source workflow is executed.
The tool store is read-only input. Each worker owns its workspace and Wetlands root.
This measures backend service work, not HTTP transport, canvas rendering or actual Run setup.
"""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
STAGES = ("saved_load", "projected_draft", "compile", "validation_plan")
COUNT_NAMES = {
    "packages_distributions": "environment_package_maps",
    "admit_installation": "installation_admissions",
    "admit_import_root": "import_root_admissions",
    "load_versioned_package": "package_load_requests",
    "capture_primary_package": "primary_package_captures",
    "capture_primary_content": "primary_content_captures",
    "validate_source_callables": "source_callable_attestations",
    "capture_tool_executable": "executable_captures",
    "read_bytes": "byte_reads",
}


def runtime_receipt(name: str, module_name: str) -> dict[str, Any]:
    """Identify the selected distribution metadata and optional source checkout."""
    import importlib
    from importlib.metadata import distribution

    installed = distribution(name)
    source = Path(importlib.import_module(module_name).__file__).resolve()
    result: dict[str, Any] = {
        "version": installed.version,
        "module_file": str(source),
        "metadata_sha256": hashlib.sha256((installed.read_text("METADATA") or "").encode()).hexdigest(),
        "record_sha256": hashlib.sha256((installed.read_text("RECORD") or "").encode()).hexdigest(),
    }
    if "site-packages" not in source.parts:
        for parent in source.parents:
            if (parent / ".git").exists():
                result["source_revision"] = subprocess.check_output(
                    ["git", "-C", str(parent), "rev-parse", "HEAD"], text=True,
                ).strip()
                result["source_dirty"] = bool(subprocess.check_output(
                    ["git", "-C", str(parent), "status", "--porcelain"], text=True,
                ).strip())
                break
    return result


def copy_tree(source: Path, target: Path, *, limit: int, copied: list[int]) -> None:
    """Copy ordinary contained fixture files without following links."""
    if source.is_symlink():
        raise ValueError(f"Fixture contains a symbolic link: {source}")
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir()):
            if child.name != "__pycache__":
                copy_tree(child, target / child.name, limit=limit, copied=copied)
    elif source.is_file():
        copied[0] += source.stat().st_size
        if copied[0] > limit:
            raise ValueError(f"Fixture exceeds copy limit of {limit} bytes")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    else:
        raise ValueError(f"Fixture is not an ordinary file or directory: {source}")


def snapshot(source: Path, workspace: Path, results: Path | None, limit: int) -> Path:
    """Make the benchmark's only mutable workflow authority."""
    target = workspace / "workflows" / "benchmark"
    copied = [0]
    copy_tree(source / "workflow.json", target / "workflow.json", limit=limit, copied=copied)
    if (source / "tools").exists():
        copy_tree(source / "tools", target / "tools", limit=limit, copied=copied)
    draft_source = source / ".bioimageflow" / "draft.json"
    if draft_source.exists():
        copy_tree(draft_source, target / ".bioimageflow" / "draft.json", limit=limit, copied=copied)
    if results is not None:
        copy_tree(results, target / "results", limit=limit, copied=copied)
    return target


def operation_counts(operation: Callable[[], Any]) -> tuple[Any, dict[str, int]]:
    profile = cProfile.Profile()
    result = profile.runcall(operation)
    counts: dict[str, int] = {}
    for entry in profile.getstats():
        code = entry.code
        if isinstance(code, str):
            continue
        name = code.co_name
        label = COUNT_NAMES.get(name)
        if name == "_validate" and code.co_filename.endswith("import_context.py"):
            label = "dependency_validations"
        if name in {"process_row", "process_batch", "transform", "merge_dataframes"}:
            label = "scientific_callbacks"
        if label:
            counts[label] = counts.get(label, 0) + entry.callcount
    return result, counts


def worker(config: dict[str, Any], *, count_only: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="bif-loading-worker-") as temporary:
        owned = Path(temporary)
        workspace = owned / "workspace"
        target = snapshot(
            Path(config["workflow_dir"]), workspace,
            Path(config["results"]) if config.get("results") else None,
            config["max_fixture_bytes"],
        )
        os.environ.update({
            "BIOIMAGEFLOW_HOME": str(owned / "home"),
            "BIOIMAGEFLOW_TOOL_STORE": config["tool_store"],
            "BIOIMAGEFLOW_WETLANDS": str(owned / "wetlands"),
            "PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        os.environ.pop("BIOIMAGEFLOW_CORE_SOURCE", None)
        os.environ.pop("BIOIMAGEFLOW_USE_LOCAL_CORE", None)
        sys.dont_write_bytecode = True
        platform_root = Path(config.get("platform_root", ROOT)).resolve()
        if not (platform_root / "backend/src/bioimageflow_server/__init__.py").is_file():
            raise ValueError(f"Not a platform source checkout: {platform_root}")
        sys.path.insert(0, str(platform_root / "backend" / "src"))
        import_started = time.perf_counter()
        from bioimageflow_server.models.graph import GraphState
        from bioimageflow_server.models.workflow_draft import WorkflowDraftResponse
        from bioimageflow_server.services.graph_compiler import GraphCompiler
        from bioimageflow_server.services.graph_validator import GraphValidationService
        from bioimageflow_server.services.tool_registry import ToolRegistryService
        from bioimageflow_server.services.workflow_draft import WorkflowDraftService
        from bioimageflow_server.services.workflow_store import WorkflowStoreService
        imports_seconds = time.perf_counter() - import_started
        document = json.loads((target / "workflow.json").read_text())
        draft_path = target / ".bioimageflow" / "draft.json"
        if draft_path.exists():
            draft = json.loads(draft_path.read_text())
            draft["workflow_id"] = "benchmark"
            draft_origin = "copied"
        else:
            draft = {
                "workflow_id": "benchmark", "base_saved_revision": document["artifact_hash"],
                "draft_revision": 0, "updated_at": "2020-01-01T00:00:00Z",
                "updated_by": "system", "dirty_against_saved": False,
                "graph": document["graph"], "validation": {"valid": True},
            }
            draft_origin = "synthesized"
        draft = WorkflowDraftResponse.model_validate(draft)
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(draft.model_dump_json())
        graph = GraphState.model_validate(draft.graph)
        registry = ToolRegistryService()
        counts: dict[str, dict[str, int]] = {}
        warm_counts: dict[str, dict[str, int]] = {}
        def discovery() -> None:
            registry.scan_tool_store(Path(config["tool_store"]))
        at = time.perf_counter()
        if count_only:
            _, counts["discovery"] = operation_counts(discovery)
        else:
            discovery()
        discovery_seconds = time.perf_counter() - at
        store = WorkflowStoreService(workspace / "workflows", registry)
        drafts = WorkflowDraftService(lambda: store)
        compiler = GraphCompiler(registry)
        validator = GraphValidationService(registry)
        samples = []
        compiled = None
        last_validation = None
        first_projection_seconds = None
        for index in range(2 if count_only else config["warm_operations"] + 1):
            sample: dict[str, Any] = {"temperature": "cold" if index == 0 else "warm"}
            operations = {
                "saved_load": lambda: store.get_workflow("benchmark"),
                "projected_draft": lambda: drafts._read_projected_draft(store, "benchmark"),
                "compile": lambda: compiler.compile(graph, storage_path=target / "results"),
                "validation_plan": lambda: validator.validation_from_compilation(graph, compiled),
            }
            for stage in STAGES:
                at = time.perf_counter()
                if count_only:
                    result, measured_counts = operation_counts(operations[stage])
                    (counts if index == 0 else warm_counts)[stage] = measured_counts
                else:
                    result = operations[stage]()
                sample[stage + "_seconds"] = time.perf_counter() - at
                if stage == "projected_draft" and first_projection_seconds is None:
                    first_projection_seconds = time.perf_counter() - config.get("launch_started", started)
                elif stage == "compile":
                    compiled = result
                elif stage == "validation_plan":
                    last_validation = result
            sample["saved_plus_projected_seconds"] = (
                sample["saved_load_seconds"] + sample["projected_draft_seconds"]
            )
            samples.append(sample)
        # Verify the requested cache scenario separately from phase timings.
        if compiled is None or compiled.workflow is None:
            raise ValueError("Fixture did not compile into a workflow")
        if last_validation.errors:
            raise ValueError(
                "Fixture has definition/cache errors; refusing misleading timings: "
                + repr([error.model_dump(mode="json") for error in last_validation.errors])
            )
        plans = compiled.workflow.plan()
        statuses: dict[str, int] = {}
        for plan in plans.values():
            status = plan.status.value
            statuses[status] = statuses.get(status, 0) + 1
        case = config["case"]
        if case == "populated-cache" and not statuses.get("cached"):
            raise ValueError(f"Populated fixture produced no cache hits: {statuses}")
        if case == "empty-cache" and statuses.get("pending_runtime"):
            raise ValueError("Empty-cache fixture requires usable runtime or DataFrame-only tools")
        if case == "missing-runtime" and plans and not statuses.get("pending_runtime"):
            raise ValueError(f"Missing-runtime fixture has no pending runtime: {statuses}")
        if any(stage.get("scientific_callbacks", 0) for stage in [*counts.values(), *warm_counts.values()]):
            raise AssertionError("Opening/planning invoked a scientific callback")
        return {
            "runtime": {
                name: runtime_receipt(name, module)
                for name, module in (
                    ("bioimageflow", "bioimageflow"),
                    ("bioimageflow-core", "bioimageflow_core"),
                    ("wetlands", "wetlands"),
                )
            },
            "python": sys.version, "draft_origin": draft_origin, "case": case,
            "platform_root": str(platform_root),
            "platform_revision": subprocess.check_output(
                ["git", "-C", str(platform_root), "rev-parse", "HEAD"], text=True).strip(),
            "platform_services_sha256": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted((platform_root / "backend/src/bioimageflow_server/services").glob("*.py"))
            },
            "imports_seconds": imports_seconds, "discovery_seconds": discovery_seconds,
            "process_start_to_first_projection_seconds": first_projection_seconds,
            "samples": [] if count_only else samples, "operation_counts": counts,
            "warm_operation_counts": warm_counts,
            "plan_status_counts": statuses,
            "validation_errors": [error.model_dump(mode="json") for error in last_validation.errors],
        }


def summarize(workers: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for temperature in ("cold", "warm"):
        samples = [sample for item in workers for sample in item["samples"]
                   if sample["temperature"] == temperature]
        result[temperature] = {}
        if not samples:
            continue
        for key in samples[0]:
            if key.endswith("_seconds"):
                values = [sample[key] for sample in samples]
                result[temperature][key] = {
                    "samples": len(values), "median": statistics.median(values),
                    "min": min(values), "max": max(values),
                }
    for key in ("imports_seconds", "discovery_seconds", "process_start_to_first_projection_seconds"):
        values = [item[key] for item in workers]
        result[key] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
    return result


def run_child(python: str, pythonpath: str | None, config: dict[str, Any], counts: bool) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    if pythonpath is not None:
        env["PYTHONPATH"] = pythonpath
    config = {**config, "launch_started": time.perf_counter()}
    result = subprocess.run(
        [python, str(SCRIPT), "--worker", json.dumps(config), *( ["--count-only"] if counts else [])],
        capture_output=True, text=True, env=env,
    )
    if result.returncode:
        raise RuntimeError(
            f"Benchmark worker failed with exit {result.returncode}:\n{result.stderr}\n{result.stdout}"
        )
    return json.loads(result.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workflow-dir", type=Path)
    parser.add_argument("--tool-store", type=Path)
    parser.add_argument("--baseline-python", default=str(ROOT / "backend/.venv/bin/python"))
    parser.add_argument("--candidate-python")
    parser.add_argument("--baseline-pythonpath")
    parser.add_argument("--candidate-pythonpath")
    parser.add_argument("--baseline-platform-root", type=Path, default=ROOT)
    parser.add_argument("--candidate-platform-root", type=Path, default=ROOT)
    parser.add_argument("--case", choices=("missing-runtime", "empty-cache", "populated-cache"), default="missing-runtime")
    parser.add_argument("--baseline-results", type=Path)
    parser.add_argument("--candidate-results", type=Path)
    parser.add_argument("--fresh-processes", type=int, default=5)
    parser.add_argument("--warm-operations", type=int, default=10, help="Total warm operations per variant, distributed across fresh processes")
    parser.add_argument("--max-fixture-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--skip-counts", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--count-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        print(json.dumps(worker(json.loads(args.worker), count_only=args.count_only)))
        return 0
    if args.workflow_dir is None or args.tool_store is None:
        parser.error("--workflow-dir and --tool-store are required")
    if args.fresh_processes < 1 or args.warm_operations < 0:
        parser.error("fresh processes must be positive and warm operations nonnegative")
    if args.case == "populated-cache" and args.baseline_results is None:
        parser.error("--baseline-results is required for populated-cache")
    if args.case != "populated-cache" and (args.baseline_results or args.candidate_results):
        parser.error("result fixtures are only valid for populated-cache")
    if args.candidate_python and args.case == "populated-cache" and args.candidate_results is None:
        parser.error("--candidate-results is required for populated-cache comparison")
    variants = {"baseline": (args.baseline_python, args.baseline_pythonpath, args.baseline_results)}
    if args.candidate_python:
        variants["candidate"] = (args.candidate_python, args.candidate_pythonpath, args.candidate_results)
    workers: dict[str, list[dict[str, Any]]] = {name: [] for name in variants}
    configs = {}
    order = []
    for index in range(args.fresh_processes):
        warm = args.warm_operations // args.fresh_processes + (index < args.warm_operations % args.fresh_processes)
        names = list(variants) if index % 2 == 0 else list(reversed(variants))
        for name in names:
            python, pythonpath, results = variants[name]
            config = {
                "workflow_dir": str(args.workflow_dir.resolve()), "tool_store": str(args.tool_store.resolve()),
                "platform_root": str((args.baseline_platform_root if name == "baseline" else args.candidate_platform_root).resolve()),
                "results": str(results.resolve()) if results else None, "case": args.case,
                "warm_operations": warm, "max_fixture_bytes": args.max_fixture_bytes,
            }
            configs[name] = config
            print(f"{name}: fresh process {index + 1}/{args.fresh_processes}, {warm} warm operations", file=sys.stderr, flush=True)
            workers[name].append(run_child(python, pythonpath, config, False))
            order.append(name)
    count_results = {}
    warm_count_results = {}
    if not args.skip_counts:
        for name, (python, pythonpath, _) in variants.items():
            profile_result = run_child(python, pythonpath, configs[name], True)
            count_results[name] = profile_result["operation_counts"]
            warm_count_results[name] = profile_result["warm_operation_counts"]
    receipt = {
        "schema": "bioimageflow.workflow_loading_benchmark.v1", "platform_revision": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "workflow_source": str(args.workflow_dir.resolve()), "case": args.case,
        "order": order, "workers": workers, "summary": {name: summarize(items) for name, items in workers.items()},
        "operation_counts": count_results, "warm_operation_counts": warm_count_results,
        "unmeasured": ["HTTP transport", "canvas presentation", "actual Run setup and scientific execution"],
        "measurement": "Cold = first operation in a fresh interpreter; warm = subsequent operations in that interpreter. Phase timings are uninstrumented. Counts use separate interpreters. Sources are copied; selected tool store is read-only input. OS filesystem cache is not purged.",
    }
    output = args.output
    if output is None:
        fd, name = tempfile.mkstemp(prefix="bif-loading-", suffix=".json", dir="/private/tmp")
        os.close(fd)
        output = Path(name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Receipt: {output}")
    print(json.dumps(receipt["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
