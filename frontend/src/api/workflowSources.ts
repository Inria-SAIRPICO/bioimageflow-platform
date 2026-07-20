import { api } from '@/api/client'
import type {
  WorkflowSourceApplyRequest,
  WorkflowSourceApplyResponse,
  WorkflowSourcePreview,
  WorkflowSourceUpdatePreviewRequest,
  PythonSourcePreviewRequest,
} from '@/api/types'

function workflowUrl(id: string): string {
  return id.split('/').map(encodeURIComponent).join('/')
}

export async function previewPythonWorkflowSource(
  workflowId: string,
  body: PythonSourcePreviewRequest,
): Promise<WorkflowSourcePreview> {
  const { data } = await api.post<WorkflowSourcePreview>(
    `/api/v1/workflows/${workflowUrl(workflowId)}/python-source/preview`,
    body,
  )
  return data
}

export async function previewWorkflowSourceUpdate(
  workflowId: string,
  body: WorkflowSourceUpdatePreviewRequest,
): Promise<WorkflowSourcePreview> {
  const { data } = await api.post<WorkflowSourcePreview>(
    `/api/v1/workflows/${workflowUrl(workflowId)}/source-update/preview`,
    body,
  )
  return data
}

export async function applyWorkflowSourceOperation(
  workflowId: string,
  body: WorkflowSourceApplyRequest,
): Promise<WorkflowSourceApplyResponse> {
  const { data } = await api.post<WorkflowSourceApplyResponse>(
    `/api/v1/workflows/${workflowUrl(workflowId)}/source-operations/apply`,
    body,
  )
  return data
}
