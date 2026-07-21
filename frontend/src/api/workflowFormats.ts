import { api } from './client'
import type { WorkflowFormatNotice, WorkflowFormatStatus } from './types'

export async function getWorkflowFormatNotices(): Promise<WorkflowFormatNotice[]> {
  const response = await api.get<WorkflowFormatStatus>('/api/v1/workflows/format-status')
  return response.data.notices ?? []
}
