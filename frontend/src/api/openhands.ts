import { api } from '@/api/client'
import type { GraphState } from '@/api/types'

export type OpenHandsAgentStatusValue =
  | 'unavailable'
  | 'stopped'
  | 'starting'
  | 'running'
  | 'stopping'
  | 'error'

export type OpenHandsProposalStatus = 'pending' | 'applied' | 'rejected'

export interface OpenHandsWorkflowDraft {
  draft_id?: string | null
  graph: GraphState
  workflow_name?: string | null
  workflow_display_name?: string | null
}

export interface OpenHandsAgentContextPayload {
  workflow_name: string | null
  workflow_display_name: string | null
  selected_node_ids: string[]
  dirty: boolean
  draft: OpenHandsWorkflowDraft
}

export interface OpenHandsProposal {
  id: string
  title: string
  summary: string
  status: OpenHandsProposalStatus
  draft_id?: string | null
  draft?: OpenHandsWorkflowDraft | null
}

export interface OpenHandsAgentStatus {
  available: boolean
  status: OpenHandsAgentStatusValue
  iframe_url: string | null
  external_url: string | null
  message: string | null
  context?: OpenHandsAgentContextPayload | null
  proposals?: OpenHandsProposal[]
}

export interface OpenHandsContextResponse {
  accepted: boolean
  context?: OpenHandsAgentContextPayload | null
  message?: string | null
}

export interface OpenHandsProposalActionResponse {
  applied?: boolean
  rejected?: boolean
  proposal?: OpenHandsProposal | null
  draft?: OpenHandsWorkflowDraft | null
  draft_id?: string
  revision?: number
  graph?: GraphState
  validation?: unknown
}

interface BackendOpenHandsStatus {
  available: boolean
  running: boolean
  pid?: number | null
  url?: string | null
  reason?: string | null
}

function mapBackendStatus(data: BackendOpenHandsStatus): OpenHandsAgentStatus {
  return {
    available: data.available,
    status: !data.available ? 'unavailable' : data.running ? 'running' : 'stopped',
    iframe_url: data.url ?? null,
    external_url: data.url ?? null,
    message: data.reason ?? null,
    proposals: [],
  }
}

export async function getOpenHandsStatus(): Promise<OpenHandsAgentStatus> {
  const { data } = await api.get<BackendOpenHandsStatus>('/api/v1/openhands/status')
  return mapBackendStatus(data)
}

export async function startOpenHandsAgent(): Promise<OpenHandsAgentStatus> {
  const { data } = await api.post<BackendOpenHandsStatus>('/api/v1/openhands/launch')
  return mapBackendStatus(data)
}

export async function shutdownOpenHandsAgent(): Promise<OpenHandsAgentStatus> {
  const { data } = await api.post<BackendOpenHandsStatus>('/api/v1/openhands/shutdown')
  return mapBackendStatus(data)
}

export async function sendOpenHandsContext(
  payload: OpenHandsAgentContextPayload,
): Promise<OpenHandsContextResponse> {
  const { data } = await api.post<OpenHandsContextResponse>(
    '/api/v1/openhands/context',
    payload,
  )
  return data
}

export async function applyOpenHandsProposal(
  draftId: string,
  proposalId: string,
): Promise<OpenHandsProposalActionResponse> {
  const { data } = await api.post<OpenHandsProposalActionResponse>(
    `/api/v1/workflow-drafts/${encodeURIComponent(draftId)}/agent-proposals/${encodeURIComponent(proposalId)}/apply`,
  )
  return data
}

export async function rejectOpenHandsProposal(
  draftId: string,
  proposalId: string,
): Promise<OpenHandsProposalActionResponse> {
  const { data } = await api.post<OpenHandsProposalActionResponse>(
    `/api/v1/workflow-drafts/${encodeURIComponent(draftId)}/agent-proposals/${encodeURIComponent(proposalId)}/reject`,
  )
  return data
}
