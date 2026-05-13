"""Workflow draft router."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from bioimageflow_server.models.settings import Settings
from bioimageflow_server.models.validation import ValidationResult
from bioimageflow_server.models.workflow_draft import (
    WorkflowDraftCreate,
    WorkflowDraftParameterPatch,
    WorkflowDraftResponse,
    WorkflowDraftState,
    WorkflowDraftUpdate,
)
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.session_manager import SessionManager
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_context import resolve_workflow_storage_path
from bioimageflow_server.services.workflow_drafts import (
    StaleWorkflowDraftError,
    WorkflowDraftManager,
    WorkflowDraftNotFoundError,
)
from bioimageflow_server.services.workflow_store import WorkflowStoreService

router = APIRouter(prefix="/workflow-drafts", tags=["workflow-drafts"])


def get_workflow_draft_manager() -> WorkflowDraftManager:  # pragma: no cover
    raise RuntimeError("workflow_draft_manager dependency not configured")


def get_tool_registry() -> ToolRegistryService:  # pragma: no cover
    raise RuntimeError("tool_registry dependency not configured")


def get_session_manager() -> SessionManager:  # pragma: no cover
    raise RuntimeError("session_manager dependency not configured")


def get_storage_path() -> Path | None:
    return None


def get_dev_mode() -> bool:
    return True


def get_workflow_store() -> WorkflowStoreService | None:
    return None


def get_settings() -> Settings | None:
    return None


def _raise_stale(exc: StaleWorkflowDraftError) -> None:
    raise HTTPException(
        status_code=409,
        detail={
            "error": "conflict",
            "detail": "Stale draft base_revision",
            "field": "base_revision",
            "current_revision": exc.current_revision,
        },
    ) from exc


def _validation_for(
    state: WorkflowDraftState,
    registry: ToolRegistryService,
    session_manager: SessionManager,
    *,
    storage_path: Path | None,
    workflow_store: WorkflowStoreService | None,
    dev_mode: bool,
    settings: Settings | None,
) -> ValidationResult:
    try:
        validation_storage_path = resolve_workflow_storage_path(
            state.workflow_name,
            workflow_store,
            storage_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{state.workflow_name}' not found",
        ) from exc
    return validate_graph(
        state.graph,
        registry,
        session_manager,
        storage_path=validation_storage_path,
        dev_mode=dev_mode,
        settings=settings,
    )


def _response(
    state: WorkflowDraftState,
    validation: ValidationResult,
) -> WorkflowDraftResponse:
    return WorkflowDraftResponse(**state.model_dump(), validation=validation)


@router.post("", response_model=WorkflowDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_draft(
    body: WorkflowDraftCreate,
    manager: WorkflowDraftManager = Depends(get_workflow_draft_manager),
    registry: ToolRegistryService = Depends(get_tool_registry),
    session_manager: SessionManager = Depends(get_session_manager),
    storage_path: Path | None = Depends(get_storage_path),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
    dev_mode: bool = Depends(get_dev_mode),
    settings: Settings | None = Depends(get_settings),
) -> WorkflowDraftResponse:
    state = manager.create(body.graph, workflow_name=body.workflow_name)
    validation = _validation_for(
        state,
        registry,
        session_manager,
        storage_path=storage_path,
        workflow_store=workflow_store,
        dev_mode=dev_mode,
        settings=settings,
    )
    return _response(state, validation)


@router.get("/{draft_id}", response_model=WorkflowDraftState)
async def get_workflow_draft(
    draft_id: str,
    manager: WorkflowDraftManager = Depends(get_workflow_draft_manager),
) -> WorkflowDraftState:
    try:
        return manager.get(draft_id)
    except WorkflowDraftNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow draft not found") from exc


@router.put("/{draft_id}", response_model=WorkflowDraftResponse)
async def update_workflow_draft(
    draft_id: str,
    body: WorkflowDraftUpdate,
    manager: WorkflowDraftManager = Depends(get_workflow_draft_manager),
    registry: ToolRegistryService = Depends(get_tool_registry),
    session_manager: SessionManager = Depends(get_session_manager),
    storage_path: Path | None = Depends(get_storage_path),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
    dev_mode: bool = Depends(get_dev_mode),
    settings: Settings | None = Depends(get_settings),
) -> WorkflowDraftResponse:
    try:
        state = manager.update(
            draft_id,
            body.graph,
            base_revision=body.base_revision,
            client_seq=body.client_seq,
        )
    except WorkflowDraftNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow draft not found") from exc
    except StaleWorkflowDraftError as exc:
        _raise_stale(exc)
    validation = _validation_for(
        state,
        registry,
        session_manager,
        storage_path=storage_path,
        workflow_store=workflow_store,
        dev_mode=dev_mode,
        settings=settings,
    )
    return _response(state, validation)


@router.patch("/{draft_id}/nodes/{node_id}/parameters", response_model=WorkflowDraftResponse)
async def patch_workflow_draft_parameters(
    draft_id: str,
    node_id: str,
    body: WorkflowDraftParameterPatch,
    manager: WorkflowDraftManager = Depends(get_workflow_draft_manager),
    registry: ToolRegistryService = Depends(get_tool_registry),
    session_manager: SessionManager = Depends(get_session_manager),
    storage_path: Path | None = Depends(get_storage_path),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
    dev_mode: bool = Depends(get_dev_mode),
    settings: Settings | None = Depends(get_settings),
) -> WorkflowDraftResponse:
    try:
        state = manager.patch_parameters(
            draft_id,
            node_id,
            body.parameters,
            base_revision=body.base_revision,
            client_seq=body.client_seq,
        )
    except WorkflowDraftNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow draft not found") from exc
    except StaleWorkflowDraftError as exc:
        _raise_stale(exc)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Draft node not found") from exc
    validation = _validation_for(
        state,
        registry,
        session_manager,
        storage_path=storage_path,
        workflow_store=workflow_store,
        dev_mode=dev_mode,
        settings=settings,
    )
    return _response(state, validation)


@router.post("/{draft_id}/validate", response_model=WorkflowDraftResponse)
async def validate_workflow_draft(
    draft_id: str,
    manager: WorkflowDraftManager = Depends(get_workflow_draft_manager),
    registry: ToolRegistryService = Depends(get_tool_registry),
    session_manager: SessionManager = Depends(get_session_manager),
    storage_path: Path | None = Depends(get_storage_path),
    workflow_store: WorkflowStoreService | None = Depends(get_workflow_store),
    dev_mode: bool = Depends(get_dev_mode),
    settings: Settings | None = Depends(get_settings),
) -> WorkflowDraftResponse:
    try:
        state = manager.get(draft_id)
    except WorkflowDraftNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow draft not found") from exc
    validation = _validation_for(
        state,
        registry,
        session_manager,
        storage_path=storage_path,
        workflow_store=workflow_store,
        dev_mode=dev_mode,
        settings=settings,
    )
    return _response(state, validation)
