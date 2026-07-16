import { api } from '@/api/client'
import type { GraphState, ValidationResult } from '@/api/types'

export type DraftWriter = 'frontend' | 'agent' | 'system'

export interface WorkflowDraftResponse {
  draft_version: 1
  workflow_id: string
  base_saved_revision: string
  draft_revision: number
  updated_at: string
  updated_by: DraftWriter
  dirty_against_saved: boolean
  graph: GraphState
  validation: ValidationResult
}

export interface WorkflowDraftConflictResponse {
  error: 'draft_revision_conflict'
  detail: string
  expected_revision: number
  current_revision: number
  current_updated_by: DraftWriter
  current_updated_at: string
}

function workflowUrl(id: string): string {
  return id.split('/').map(encodeURIComponent).join('/')
}

export async function fetchWorkflowDraft(workflowId: string): Promise<WorkflowDraftResponse> {
  const { data } = await api.get<WorkflowDraftResponse>(
    `/api/v1/workflow-drafts/${workflowUrl(workflowId)}`,
  )
  return data
}

export async function putWorkflowDraft(
  workflowId: string,
  body: {
    graph: GraphState
    expected_revision: number
    updated_by?: DraftWriter
    validate?: boolean
  },
): Promise<WorkflowDraftResponse> {
  const { data } = await api.put<WorkflowDraftResponse>(
    `/api/v1/workflow-drafts/${workflowUrl(workflowId)}`,
    body,
  )
  return data
}

export async function resetWorkflowDraftToSaved(
  workflowId: string,
  expectedRevision: number,
): Promise<WorkflowDraftResponse> {
  const { data } = await api.post<WorkflowDraftResponse>(
    `/api/v1/workflow-drafts/${workflowUrl(workflowId)}/reset-to-saved`,
    { expected_revision: expectedRevision, updated_by: 'frontend' },
  )
  return data
}
