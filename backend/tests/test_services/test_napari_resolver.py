from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
from bioimageflow_core import ViewerSpec as LibraryViewerSpec

from bioimageflow_server.models.napari_environments import (
    InstalledDistribution,
    NapariEnvironment,
    NapariEnvironmentInventory,
    NapariEnvironmentList,
    NapariFilenameRule,
    NapariLaunchContext,
    NapariResolveRequest,
)
from bioimageflow_server.models.results import ResultArtifactIdentity
from bioimageflow_server.models.viewer_preferences import PersistentOutputPreferenceKey
from bioimageflow_server.services.napari_resolver import NapariResolverService
from bioimageflow_server.services.viewer_preferences import (
    ViewerPreferenceStore,
    ensure_workspace_identity,
)


def _environment(name, order, packages, *, probed_at=None) -> NapariEnvironment:
    return NapariEnvironment(
        id=uuid4(),
        registration_order=order,
        name=name,
        ownership="external",
        kind="venv",
        root=f"/{name}",
        interpreter=f"/{name}/python",
        interpreter_identity=f"/{name}/python",
        interpreter_fingerprint="a" * 64,
        launch=NapariLaunchContext(strategy="interpreter"),
        inventory=NapariEnvironmentInventory(
            python_version="3.13",
            napari_version="0.7.1",
            distributions=[
                InstalledDistribution(name=package, version=version)
                for package, version in packages.items()
            ],
            fingerprint="b" * 64,
            probed_at=probed_at or datetime.now(UTC),
        ),
    )


def test_resolution_falls_through_incompatible_favorite_to_filename_rule(tmp_path) -> None:
    incompatible = _environment("favorite", 0, {"napari": "0.7.1"})
    compatible = _environment(
        "rule", 1, {"napari": "0.7.1", "Example_Reader": "2.4"}
    )
    rule = NapariFilenameRule(
        id=uuid4(),
        pattern="*.tif",
        environment_id=compatible.id,
        reader_id="rule.reader",
    )
    environments = SimpleNamespace(
        snapshot=lambda: NapariEnvironmentList(
            revision=1,
            environments=[incompatible, compatible],
            default_environment_id=incompatible.id,
            filename_rules=[rule],
        )
    )
    workflow_store = SimpleNamespace(
        workspace_dir=tmp_path / "workspace",
        ensure_workflow_generation=lambda workflow_id, generation: None,
        get_storage_path=lambda workflow_id: tmp_path / "results",
    )
    preferences = ViewerPreferenceStore(tmp_path / "viewer-preferences.json")
    workspace_id = ensure_workspace_identity(workflow_store.workspace_dir)
    favorite_key = PersistentOutputPreferenceKey(
        workspace_id=workspace_id,
        workflow_id="wf",
        identity_generation=3,
        node_path=("n1",),
        output_key="image",
    )
    preferences.set(favorite_key, incompatible.id, expected_revision=0)
    identity = ResultArtifactIdentity(
        run_id="run_old",
        node_key="n1",
        result_key="rk_old",
        record_id="rec_old",
    )
    viewer = LibraryViewerSpec.from_dict(
        {
            "napari": {
                "required_packages": [
                    {
                        "distribution": "example-reader",
                        "normalized_name": "example-reader",
                        "version": ">=2,<3",
                    }
                ],
                "recommended_packages": [],
                "napari_version": ">=0.7",
                "reader_id": "artifact.reader",
            }
        }
    )
    result_store = SimpleNamespace(
        load_result_dataframe=lambda identity, storage_path: pd.DataFrame(
            {"image": ["sample.tif"]}
        ),
        result_viewer=lambda identity, output, storage_path: viewer,
    )
    resolver = NapariResolverService(
        environments, preferences, result_store, lambda: workflow_store
    )

    response = resolver.resolve(
        NapariResolveRequest(
            workflow_id="wf",
            identity_generation=3,
            node_path=("n1",),
            output_key="image",
            result_identity=identity,
            row=0,
        )
    )

    assert response.effective_environment_id == compatible.id
    assert [candidate.status for candidate in response.candidates] == [
        "incompatible",
        "compatible",
    ]
    assert response.candidates[1].label == "Required packages installed"
    assert response.reader_id == "artifact.reader"
    assert [candidate.reader_id for candidate in response.candidates] == [
        "artifact.reader",
        "artifact.reader",
    ]
    assert response.preference_key == favorite_key


def test_filename_rule_reader_is_scoped_to_its_candidate(tmp_path) -> None:
    rule_environment = _environment("rule", 0, {"napari": "0.7.1"})
    fallback = _environment("fallback", 1, {"napari": "0.7.1", "reader": "1.0"})
    rule = NapariFilenameRule(
        id=uuid4(),
        pattern="*.tif",
        environment_id=rule_environment.id,
        reader_id="rule.reader",
    )
    environments = SimpleNamespace(
        snapshot=lambda: NapariEnvironmentList(
            revision=1,
            environments=[rule_environment, fallback],
            default_environment_id=None,
            filename_rules=[rule],
        )
    )
    workflow_store = SimpleNamespace(
        workspace_dir=tmp_path / "workspace",
        ensure_workflow_generation=lambda workflow_id, generation: None,
        get_storage_path=lambda workflow_id: tmp_path / "results",
    )
    viewer = LibraryViewerSpec.from_dict(
        {
            "napari": {
                "required_packages": [
                    {
                        "distribution": "reader",
                        "normalized_name": "reader",
                        "version": None,
                    }
                ],
                "recommended_packages": [],
                "napari_version": None,
                "reader_id": None,
            }
        }
    )
    resolver = NapariResolverService(
        environments,
        ViewerPreferenceStore(tmp_path / "viewer-preferences.json"),
        SimpleNamespace(
            load_result_dataframe=lambda identity, storage_path: pd.DataFrame(
                {"image": ["sample.tif"]}
            ),
            result_viewer=lambda identity, output, storage_path: viewer,
        ),
        lambda: workflow_store,
    )
    identity = ResultArtifactIdentity(
        run_id="run_old",
        node_key="n1",
        result_key="rk_old",
        record_id="rec_old",
    )

    response = resolver.resolve(
        NapariResolveRequest(
            workflow_id="wf",
            identity_generation=3,
            node_path=("n1",),
            output_key="image",
            result_identity=identity,
            row=0,
        )
    )

    assert response.effective_environment_id == fallback.id
    assert [candidate.reader_id for candidate in response.candidates] == [
        "rule.reader",
        None,
    ]
    assert response.reader_id is None


def test_stale_inventory_is_unknown_not_incompatible(tmp_path) -> None:
    stale = _environment(
        "stale",
        0,
        {"napari": "0.7.1", "reader": "1.0"},
        probed_at=datetime.now(UTC) - timedelta(days=2),
    )
    resolver = NapariResolverService(
        SimpleNamespace(),
        ViewerPreferenceStore(tmp_path / "viewer-preferences.json"),
        SimpleNamespace(),
        lambda: None,
    )
    viewer = LibraryViewerSpec.from_dict(
        {
            "napari": {
                "required_packages": [
                    {
                        "distribution": "reader",
                        "normalized_name": "reader",
                        "version": None,
                    }
                ],
                "recommended_packages": [],
                "napari_version": None,
                "reader_id": None,
            }
        }
    )
    candidate = resolver._candidate(
        stale,
        __import__("bioimageflow_server.models.graph", fromlist=["ViewerSpec"])
        .ViewerSpec.model_validate(viewer.to_dict()),
        "other",
    )
    assert candidate.status == "unknown"
    assert candidate.label == "Not verified"
