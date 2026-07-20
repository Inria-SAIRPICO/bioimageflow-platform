import { api } from '@/api/client'
import type { DemoWorkflowsStatus } from '@/api/types'

export type { DemoWorkflowStatus, DemoWorkflowsStatus } from '@/api/types'

export async function getDemoWorkflowsStatus(): Promise<DemoWorkflowsStatus> {
  return (await api.get<DemoWorkflowsStatus>('/api/v1/demo-workflows')).data
}

export async function installDemoWorkflows(): Promise<DemoWorkflowsStatus> {
  return (await api.post<DemoWorkflowsStatus>('/api/v1/demo-workflows/install')).data
}
