import { api } from './client'
import type { WorkflowFormatNotice, WorkflowFormatStatus } from './types'

export async function getWorkflowFormatStatus(): Promise<WorkflowFormatStatus> {
  const response = await api.get<WorkflowFormatStatus>('/api/v1/workflows/format-status')
  return response.data
}

export async function getWorkflowFormatNotices(): Promise<WorkflowFormatNotice[]> {
  return (await getWorkflowFormatStatus()).notices ?? []
}

export async function applyWorkflowFormatMigrations(
  pendingPlanId: string,
): Promise<WorkflowFormatStatus> {
  const response = await api.post<WorkflowFormatStatus>(
    '/api/v1/workflows/format-migrations/apply',
    { pending_plan_id: pendingPlanId },
  )
  return response.data
}
