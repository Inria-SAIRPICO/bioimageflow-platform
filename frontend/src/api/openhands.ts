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
  revision?: number | null
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

export type OpenHandsApprovalStatus = 'pending' | 'approved' | 'rejected'
export type OpenHandsApprovalType = 'package_install'

export interface OpenHandsApproval {
  id: string
  type: OpenHandsApprovalType
  package_name: string
  package_version?: string | null
  command?: string | null
  status: OpenHandsApprovalStatus
}

export interface OpenHandsAgentConfig {
  installed: boolean
  configured: boolean
  provider: string
  model: string
  api_key_ref: string
  command: string
  message?: string | null
}

export type OpenHandsAgentConfigUpdate = Pick<
  OpenHandsAgentConfig,
  'provider' | 'model' | 'api_key_ref' | 'command'
>

export interface OpenHandsAgentStatus {
  available: boolean
  status: OpenHandsAgentStatusValue
  iframe_url: string | null
  external_url: string | null
  message: string | null
  installed?: boolean
  configured?: boolean
  config?: Partial<OpenHandsAgentConfig> | null
  context?: OpenHandsAgentContextPayload | null
  proposals?: OpenHandsProposal[]
  approvals?: OpenHandsApproval[]
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

export interface OpenHandsApprovalActionResponse {
  approved?: boolean
  rejected?: boolean
  approval?: OpenHandsApproval | null
  message?: string | null
}

export interface OpenHandsUndoResponse {
  draft_id?: string | null
  revision?: number | null
  graph?: GraphState
  draft?: OpenHandsWorkflowDraft | null
  message?: string | null
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
    installed: data.available,
    configured: data.available,
    proposals: [],
    approvals: [],
  }
}

export async function getOpenHandsStatus(): Promise<OpenHandsAgentStatus> {
  const { data } = await api.get<BackendOpenHandsStatus | OpenHandsAgentStatus>(
    '/api/v1/openhands/status',
  )
  if ('status' in data) return data
  return mapBackendStatus(data)
}

export async function startOpenHandsAgent(): Promise<OpenHandsAgentStatus> {
  const { data } = await api.post<BackendOpenHandsStatus | OpenHandsAgentStatus>(
    '/api/v1/openhands/launch',
  )
  if ('status' in data) return data
  return mapBackendStatus(data)
}

export async function shutdownOpenHandsAgent(): Promise<OpenHandsAgentStatus> {
  const { data } = await api.post<BackendOpenHandsStatus | OpenHandsAgentStatus>(
    '/api/v1/openhands/shutdown',
  )
  if ('status' in data) return data
  return mapBackendStatus(data)
}

export async function getOpenHandsConfig(): Promise<OpenHandsAgentConfig> {
  const { data } = await api.get<OpenHandsAgentConfig>('/api/v1/openhands/config')
  return data
}

export async function installOpenHandsAgent(): Promise<OpenHandsAgentConfig> {
  const { data } = await api.post<OpenHandsAgentConfig>('/api/v1/openhands/install')
  return data
}

export async function saveOpenHandsConfig(
  payload: OpenHandsAgentConfigUpdate,
): Promise<OpenHandsAgentConfig> {
  const { data } = await api.post<OpenHandsAgentConfig>(
    '/api/v1/openhands/config',
    payload,
  )
  return data
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

export async function approveOpenHandsApproval(
  approvalId: string,
): Promise<OpenHandsApprovalActionResponse> {
  const { data } = await api.post<OpenHandsApprovalActionResponse>(
    `/api/v1/openhands/approvals/${encodeURIComponent(approvalId)}/approve`,
  )
  return data
}

export async function rejectOpenHandsApproval(
  approvalId: string,
): Promise<OpenHandsApprovalActionResponse> {
  const { data } = await api.post<OpenHandsApprovalActionResponse>(
    `/api/v1/openhands/approvals/${encodeURIComponent(approvalId)}/reject`,
  )
  return data
}

export async function undoOpenHandsChange(draftId: string): Promise<OpenHandsUndoResponse> {
  const { data } = await api.post<OpenHandsUndoResponse>('/api/v1/openhands/undo', {
    draft_id: draftId,
  })
  return data
}
