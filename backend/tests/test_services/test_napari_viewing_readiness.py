from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from bioimageflow_server.models.graph import ViewerSpec
from bioimageflow_server.models.napari_environments import (
    InstalledDistribution,
    NapariEnvironment,
    NapariEnvironmentInventory,
    NapariEnvironmentList,
    NapariLaunchContext,
)
from bioimageflow_server.models.workflow import (
    ViewingRequirementEntry,
    ViewingRequirementsManifest,
)
from bioimageflow_server.services.napari_resolver import NapariResolverService


def _environment(
    name: str,
    order: int,
    packages: dict[str, str],
    *,
    state: str = "ready",
    probed_at: datetime | None = None,
) -> NapariEnvironment:
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
            python_version="3.12",
            napari_version=packages.get("napari"),
            distributions=[
                InstalledDistribution(name=package, version=version)
                for package, version in packages.items()
            ],
            fingerprint="b" * 64,
            probed_at=probed_at or datetime.now(UTC),
        ),
        state=state,  # type: ignore[arg-type]
    )


def _viewer(
    *,
    required: list[tuple[str, str | None]] | None = None,
    recommended: list[tuple[str, str | None]] | None = None,
    napari_version: str | None = None,
    reader_id: str | None = None,
) -> ViewerSpec:
    def package(name: str, version: str | None) -> dict[str, str | None]:
        return {
            "distribution": name,
            "normalized_name": name.casefold().replace("_", "-"),
            "version": version,
        }

    return ViewerSpec.model_validate(
        {
            "napari": {
                "required_packages": [package(*item) for item in required or []],
                "recommended_packages": [package(*item) for item in recommended or []],
                "napari_version": napari_version,
                "reader_id": reader_id,
            }
        }
    )


class _PassiveEnvironments:
    def __init__(self, environments: list[NapariEnvironment]) -> None:
        self.environments = environments
        self.snapshot_calls = 0
        self.probe_calls = 0
        self.install_calls = 0
        self.launch_calls = 0

    def snapshot(self) -> NapariEnvironmentList:
        self.snapshot_calls += 1
        return NapariEnvironmentList(
            revision=1,
            environments=self.environments,
            default_environment_id=None,
        )

    def probe(self, *_args: object, **_kwargs: object) -> None:
        self.probe_calls += 1

    def create_managed(self, *_args: object, **_kwargs: object) -> None:
        self.install_calls += 1

    def launch(self, *_args: object, **_kwargs: object) -> None:
        self.launch_calls += 1


def _resolver(environments: _PassiveEnvironments) -> NapariResolverService:
    return NapariResolverService(
        environments,  # type: ignore[arg-type]
        cast(Any, SimpleNamespace()),
        cast(Any, SimpleNamespace()),
        lambda: (_ for _ in ()).throw(AssertionError("workflow state was read")),
    )


def test_required_packages_must_coexist_in_one_environment() -> None:
    environments = _PassiveEnvironments(
        [
            _environment("reader-only", 0, {"reader": "1.5"}),
            _environment("codec-only", 1, {"codec": "2.5"}),
        ]
    )
    manifest = ViewingRequirementsManifest(
        outputs={
            "nested/node:image": ViewingRequirementEntry(
                status="known",
                viewer=_viewer(required=[("reader", ">=1"), ("codec", ">=2")]),
            )
        }
    )

    response = _resolver(environments).viewing_readiness(manifest)

    assert response.outputs[0].status == "not_covered"
    assert [candidate.status for candidate in response.outputs[0].candidates] == [
        "incompatible",
        "incompatible",
    ]
    assert response.summary.outputs_needing_setup == 1
    assert response.summary.message == "1 output needs viewer setup"


def test_conflicting_outputs_are_grouped_and_covered_independently() -> None:
    old = _environment("old", 0, {"segment-reader": "1.9"})
    new = _environment("new", 1, {"segment-reader": "2.4"})
    manifest = ViewingRequirementsManifest(
        outputs={
            "old-node:mask": ViewingRequirementEntry(
                status="known",
                viewer=_viewer(required=[("segment-reader", "<2")]),
            ),
            "new-node:mask": ViewingRequirementEntry(
                status="known",
                viewer=_viewer(required=[("segment-reader", ">=2")]),
            ),
        }
    )

    response = _resolver(_PassiveEnvironments([old, new])).viewing_readiness(manifest)

    assert [output.status for output in response.outputs] == ["covered", "covered"]
    assert [output.effective_environment_id for output in response.outputs] == [
        old.id,
        new.id,
    ]
    assert len(response.groups) == 2
    assert response.summary.outputs_needing_setup == 0


def test_recommended_missing_does_not_remove_coverage_and_reader_is_ignored() -> None:
    environment = _environment("viewer", 0, {"required-reader": "1.2"})
    manifest = ViewingRequirementsManifest(
        outputs={
            "node:image": ViewingRequirementEntry(
                status="known",
                viewer=_viewer(
                    required=[("required-reader", ">=1")],
                    recommended=[("editor-widget", ">=4")],
                    reader_id="special.reader",
                ),
            )
        }
    )

    response = _resolver(_PassiveEnvironments([environment])).viewing_readiness(manifest)

    output = response.outputs[0]
    assert output.status == "covered"
    assert output.candidates[0].status == "compatible"
    assert output.candidates[0].reader_id == "special.reader"
    assert [item.distribution for item in output.candidates[0].missing_recommended_packages] == [
        "editor-widget"
    ]


def test_no_declaration_is_covered_but_unknown_and_stale_are_not() -> None:
    stale = _environment(
        "stale",
        0,
        {"reader": "1.0"},
        probed_at=datetime.now(UTC) - timedelta(days=2),
    )
    manifest = ViewingRequirementsManifest(
        complete=False,
        outputs={
            "plain:image": ViewingRequirementEntry(status="known"),
            "unresolved:image": ViewingRequirementEntry(
                status="unknown", reason="tool metadata unavailable"
            ),
            "declared:image": ViewingRequirementEntry(
                status="known", viewer=_viewer(required=[("reader", ">=1")])
            ),
        },
    )

    response = _resolver(_PassiveEnvironments([stale])).viewing_readiness(manifest)

    plain, unresolved, declared = response.outputs
    assert plain.status == "covered"
    assert plain.reason == "no_declared_napari_requirements"
    assert unresolved.status == "unknown"
    assert unresolved.manifest_reason == "tool metadata unavailable"
    assert unresolved.candidates[0].status == "unknown"
    assert unresolved.candidates[0].issues[0].code == "requirements_unknown"
    assert declared.status == "unknown"
    assert declared.candidates[0].issues[0].code == "inventory_stale"
    assert response.summary.model_dump() == {
        "total_outputs": 3,
        "covered_outputs": 1,
        "not_covered_outputs": 0,
        "unknown_outputs": 2,
        "outputs_needing_setup": 2,
        "message": "2 outputs need viewer setup",
    }


def test_reader_only_and_recommended_only_are_covered_with_stale_inventory() -> None:
    stale = _environment(
        "stale",
        0,
        {},
        probed_at=datetime.now(UTC) - timedelta(days=2),
    )
    manifest = ViewingRequirementsManifest(
        outputs={
            "reader-only:file": ViewingRequirementEntry(
                status="known", viewer=_viewer(reader_id="reader.only")
            ),
            "recommended-only:file": ViewingRequirementEntry(
                status="known",
                viewer=_viewer(recommended=[("optional-widget", ">=1")]),
            ),
        }
    )

    response = _resolver(_PassiveEnvironments([stale])).viewing_readiness(manifest)

    assert [output.status for output in response.outputs] == ["covered", "covered"]
    assert [output.candidates[0].status for output in response.outputs] == [
        "compatible",
        "compatible",
    ]
    assert response.outputs[0].candidates[0].reader_id == "reader.only"
    assert response.outputs[1].candidates[0].missing_recommended_packages == []


def test_napari_constraint_and_unavailable_environment_have_distinct_issues() -> None:
    incompatible = _environment("old", 0, {"napari": "0.6.6"})
    unavailable = _environment(
        "missing", 1, {"napari": "0.9.1"}, state="missing"
    )
    manifest = ViewingRequirementsManifest(
        outputs={
            "node:image": ViewingRequirementEntry(
                status="known", viewer=_viewer(napari_version=">=0.9")
            )
        }
    )

    response = _resolver(
        _PassiveEnvironments([incompatible, unavailable])
    ).viewing_readiness(manifest)

    output = response.outputs[0]
    assert output.status == "not_covered"
    assert [candidate.status for candidate in output.candidates] == [
        "incompatible",
        "unavailable",
    ]
    assert [candidate.issues[0].code for candidate in output.candidates] == [
        "napari_version_out_of_range",
        "unavailable",
    ]


def test_normalized_requirement_sets_share_stable_group_and_prefill() -> None:
    manifest = ViewingRequirementsManifest(
        outputs={
            "a:image": ViewingRequirementEntry(
                status="known",
                viewer=_viewer(
                    required=[("Example_Reader", ">=1,<2")],
                    reader_id="reader.a",
                ),
            ),
            "b:image": ViewingRequirementEntry(
                status="known",
                viewer=_viewer(
                    required=[("example-reader", "<2,>=1")],
                    reader_id="reader.b",
                ),
            ),
        }
    )
    environments = _PassiveEnvironments([])

    first = _resolver(environments).viewing_readiness(manifest)
    second = _resolver(environments).viewing_readiness(manifest)

    assert len(first.groups) == 1
    assert first.groups[0].members == ["a:image", "b:image"]
    assert first.groups[0].id == second.groups[0].id
    assert first.outputs[0].group_id == first.outputs[1].group_id
    assert first.groups[0].managed_create_prefill.model_dump() == {
        "requested_packages": ["example-reader<2,>=1"],
        "recommended_packages": [],
        "napari_version_constraint": None,
        "package_source": "unverified",
        "requires_source_confirmation": True,
    }
    assert environments.snapshot_calls == 2
    assert environments.probe_calls == 0
    assert environments.install_calls == 0
    assert environments.launch_calls == 0
