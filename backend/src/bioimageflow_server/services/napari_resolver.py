"""Deterministic package-only napari compatibility and selection."""

from __future__ import annotations

import fnmatch
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from uuid import UUID

from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from bioimageflow_server.models.graph import ViewerSpec
from bioimageflow_server.models.napari_environments import (
    NapariCompatibilityIssue,
    NapariEnvironment,
    NapariEnvironmentCandidate,
    NapariResolveRequest,
    NapariResolveResponse,
)
from bioimageflow_server.models.viewer_preferences import (
    PersistentOutputPreferenceKey,
)
from bioimageflow_server.routers.nodes import _get_dataframe_cell
from bioimageflow_server.services.napari_environments import NapariEnvironmentService
from bioimageflow_server.services.result_store import ResultStoreService
from bioimageflow_server.services.viewer_preferences import (
    ViewerPreferenceStore,
    ensure_workspace_identity,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService


INVENTORY_MAX_AGE = timedelta(hours=24)


class NapariResolverError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


class NapariResolverService:
    def __init__(
        self,
        environments: NapariEnvironmentService,
        preferences: ViewerPreferenceStore,
        result_store: ResultStoreService,
        workflow_store_provider,
    ) -> None:
        self.environments = environments
        self.preferences = preferences
        self.result_store = result_store
        self.workflow_store_provider = workflow_store_provider

    def resolve(self, request: NapariResolveRequest) -> NapariResolveResponse:
        store: WorkflowStoreService = self.workflow_store_provider()
        store.ensure_workflow_generation(
            request.workflow_id, request.identity_generation
        )
        storage_path = store.get_storage_path(request.workflow_id)
        if request.result_identity.node_key != "/".join(request.node_path):
            raise NapariResolverError(
                "result_output_mismatch",
                "Captured result node does not match the structural output path",
            )
        dataframe = self.result_store.load_result_dataframe(
            request.result_identity, storage_path=storage_path
        )
        value = _get_dataframe_cell(dataframe, request.row, request.output_key)
        filename = PurePath(str(value).rstrip("/\\")).name
        library_viewer = self.result_store.result_viewer(
            request.result_identity,
            request.output_key,
            storage_path=storage_path,
        )
        viewer = (
            None
            if library_viewer is None
            else ViewerSpec.model_validate(library_viewer.to_dict())
        )

        workspace_id = ensure_workspace_identity(store.workspace_dir)
        key = PersistentOutputPreferenceKey(
            workspace_id=workspace_id,
            workflow_id=request.workflow_id,
            identity_generation=request.identity_generation,
            node_path=request.node_path,
            output_key=request.output_key,
        )
        favorite = self.preferences.favorite_for(key)
        snapshot = self.environments.snapshot()
        winning_rule = next(
            (
                rule
                for rule in snapshot.filename_rules
                if rule.enabled
                and fnmatch.fnmatchcase(filename.casefold(), rule.pattern.casefold())
            ),
            None,
        )
        preference_order: list[tuple[UUID, str]] = []
        if favorite is not None:
            preference_order.append((favorite, "favorite"))
        if winning_rule is not None:
            preference_order.append((winning_rule.environment_id, "filename_rule"))
        if snapshot.default_environment_id is not None:
            preference_order.append((snapshot.default_environment_id, "global_default"))
        preference_order.extend((item.id, "other") for item in snapshot.environments)
        rank: dict[UUID, str] = {}
        for environment_id, source in preference_order:
            rank.setdefault(environment_id, source)

        by_id = {item.id: item for item in snapshot.environments}
        ordered = [by_id[item] for item in rank if item in by_id]
        candidates = [
            self._candidate(environment, viewer, rank[environment.id])
            for environment in ordered
        ]
        effective = next(
            (candidate for candidate in candidates if candidate.status == "compatible"),
            None,
        )
        reader_id = (
            viewer.napari.reader_id
            if viewer is not None and viewer.napari is not None
            else None
        )
        if (
            reader_id is None
            and effective is not None
            and winning_rule is not None
            and effective.environment_id == winning_rule.environment_id
        ):
            reader_id = winning_rule.reader_id
        return NapariResolveResponse(
            artifact_identity=request.result_identity,
            workflow_id=request.workflow_id,
            identity_generation=request.identity_generation,
            node_path=request.node_path,
            output_key=request.output_key,
            filename=filename,
            viewer=viewer,
            reader_id=reader_id,
            candidates=candidates,
            effective_environment_id=(
                effective.environment_id if effective is not None else None
            ),
            effective_reason=(
                effective.reason
                if effective is not None
                else "No registered environment has verified required packages"
            ),
        )

    def _candidate(
        self,
        environment: NapariEnvironment,
        viewer: ViewerSpec | None,
        preference: str,
    ) -> NapariEnvironmentCandidate:
        issues: list[NapariCompatibilityIssue] = []
        unavailable_states = {
            "setup_needed",
            "creating",
            "failed",
            "cancelled",
            "removing",
            "missing",
            "replaced",
        }
        if environment.state in unavailable_states:
            issues.append(
                NapariCompatibilityIssue(
                    code="unavailable",
                    detail=environment.last_error or f"Environment is {environment.state}",
                )
            )
            status = "unavailable"
        elif viewer is not None and viewer.napari is not None and (
            environment.inventory is None
            or environment.state in {"probe_failed", "drifted"}
            or self._inventory_stale(environment)
        ):
            code = (
                "probe_failed"
                if environment.state == "probe_failed"
                else "inventory_stale"
                if environment.inventory is not None
                else "inventory_missing"
            )
            issues.append(
                NapariCompatibilityIssue(
                    code=code,
                    detail=(
                        environment.last_error
                        or "Installed distribution inventory is not fresh"
                    ),
                )
            )
            status = "unknown"
        else:
            status = "compatible"
            if viewer is not None and viewer.napari is not None:
                issues.extend(self._required_issues(environment, viewer))
                if issues:
                    status = "incompatible"

        missing_recommended = self._missing_recommended(environment, viewer)
        label = {
            "compatible": "Required packages installed",
            "incompatible": "Needs attention",
            "unknown": "Not verified",
            "unavailable": "Unavailable",
        }[status]
        reason = {
            "favorite": "Saved favorite",
            "filename_rule": "First matching filename rule",
            "global_default": "Global default",
            "other": "Registration order fallback",
        }[preference]
        if issues:
            reason = f"{reason}: {issues[0].detail}"
        return NapariEnvironmentCandidate(
            environment_id=environment.id,
            name=environment.name,
            status=status,
            label=label,
            reason=reason,
            issues=issues,
            missing_recommended_packages=missing_recommended,
            preference=preference,
        )

    @staticmethod
    def _inventory_stale(environment: NapariEnvironment) -> bool:
        inventory = environment.inventory
        if inventory is None:
            return True
        probed_at = inventory.probed_at
        if probed_at.tzinfo is None:
            probed_at = probed_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - probed_at > INVENTORY_MAX_AGE

    @staticmethod
    def _installed(environment: NapariEnvironment) -> dict[str, str]:
        if environment.inventory is None:
            return {}
        return {
            canonicalize_name(item.name): item.version
            for item in environment.inventory.distributions
        }

    def _required_issues(
        self, environment: NapariEnvironment, viewer: ViewerSpec
    ) -> list[NapariCompatibilityIssue]:
        requirement = viewer.napari
        assert requirement is not None
        installed = self._installed(environment)
        issues: list[NapariCompatibilityIssue] = []
        for package in requirement.required_packages:
            version = installed.get(package.normalized_name)
            if version is None:
                issues.append(
                    NapariCompatibilityIssue(
                        code="missing_distribution",
                        distribution=package.distribution,
                        required_version=package.version,
                        detail=f"{package.distribution} is not installed",
                    )
                )
            elif package.version is not None and not self._satisfies(
                version, package.version
            ):
                issues.append(
                    NapariCompatibilityIssue(
                        code="version_out_of_range",
                        distribution=package.distribution,
                        required_version=package.version,
                        installed_version=version,
                        detail=(
                            f"{package.distribution} {version} does not satisfy "
                            f"{package.version}"
                        ),
                    )
                )
        if requirement.napari_version is not None:
            napari_version = (
                environment.inventory.napari_version
                if environment.inventory is not None
                else None
            )
            if napari_version is None:
                issues.append(
                    NapariCompatibilityIssue(
                        code="missing_napari",
                        required_version=requirement.napari_version,
                        detail="napari is not installed",
                    )
                )
            elif not self._satisfies(napari_version, requirement.napari_version):
                issues.append(
                    NapariCompatibilityIssue(
                        code="napari_version_out_of_range",
                        distribution="napari",
                        required_version=requirement.napari_version,
                        installed_version=napari_version,
                        detail=(
                            f"napari {napari_version} does not satisfy "
                            f"{requirement.napari_version}"
                        ),
                    )
                )
        return issues

    def _missing_recommended(
        self, environment: NapariEnvironment, viewer: ViewerSpec | None
    ) -> list:
        if viewer is None or viewer.napari is None or environment.inventory is None:
            return []
        installed = self._installed(environment)
        return [
            package
            for package in viewer.napari.recommended_packages
            if (version := installed.get(package.normalized_name)) is None
            or (
                package.version is not None
                and not self._satisfies(version, package.version)
            )
        ]

    @staticmethod
    def _satisfies(version: str, specifier: str) -> bool:
        try:
            return Version(version) in SpecifierSet(specifier)
        except InvalidVersion:
            return False
