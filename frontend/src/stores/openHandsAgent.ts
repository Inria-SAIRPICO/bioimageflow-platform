import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  approveOpenHandsApproval,
  applyOpenHandsProposal,
  getOpenHandsConfig,
  getOpenHandsStatus,
  installOpenHandsAgent,
  rejectOpenHandsProposal,
  rejectOpenHandsApproval,
  sendOpenHandsContext,
  saveOpenHandsConfig,
  shutdownOpenHandsAgent,
  startOpenHandsAgent,
  undoOpenHandsChange,
  type OpenHandsAgentConfig,
  type OpenHandsAgentConfigUpdate,
  type OpenHandsAgentContextPayload,
  type OpenHandsAgentStatus,
  type OpenHandsAgentStatusValue,
  type OpenHandsApproval,
  type OpenHandsProposal,
  type OpenHandsProposalActionResponse,
  type OpenHandsUndoResponse,
} from '@/api/openhands'
import { useUIStore } from '@/stores/ui'

function messageFromError(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function actionDraft(response: OpenHandsProposalActionResponse) {
  const draft = response.draft ?? response.proposal?.draft ?? (
    response.graph
      ? { graph: response.graph, draft_id: response.draft_id, revision: response.revision }
      : null
  )
  if (!draft) return null
  return {
    ...draft,
    validation: draft.validation ?? response.validation ?? null,
  }
}

function undoDraft(response: OpenHandsUndoResponse) {
  const draft = response.draft ?? (
    response.graph
      ? { graph: response.graph, draft_id: response.draft_id, revision: response.revision }
      : null
  )
  if (!draft) return null
  return {
    ...draft,
    validation: draft.validation ?? response.validation ?? null,
  }
}

const emptyConfig: OpenHandsAgentConfig = {
  installed: false,
  configured: false,
  provider: '',
  model: '',
  api_key_ref: '',
  command: '',
}

export const useOpenHandsAgentStore = defineStore('openHandsAgent', () => {
  const status = ref<OpenHandsAgentStatusValue>('unavailable')
  const available = ref(false)
  const installed = ref(false)
  const configured = ref(false)
  const configDraft = ref<OpenHandsAgentConfigUpdate>({
    provider: '',
    model: '',
    api_key_ref: '',
    command: '',
  })
  const iframeUrl = ref<string | null>(null)
  const externalUrl = ref<string | null>(null)
  const message = ref<string | null>(null)
  const context = ref<OpenHandsAgentContextPayload | null>(null)
  const proposals = ref<OpenHandsProposal[]>([])
  const approvals = ref<OpenHandsApproval[]>([])
  const undoAvailable = ref(false)
  const isLoadingStatus = ref(false)
  const isStarting = ref(false)
  const isShuttingDown = ref(false)
  const isSendingContext = ref(false)
  const isReviewingProposal = ref(false)
  const isLoadingConfig = ref(false)
  const isInstalling = ref(false)
  const isSavingConfig = ref(false)
  const isReviewingApproval = ref(false)
  const isUndoing = ref(false)
  const configDirty = ref(false)
  const iframeBlocked = ref(false)

  const isRunning = computed(() => status.value === 'running')
  const hasCompleteConfig = computed(() => (
    Boolean(configDraft.value.provider.trim())
    && Boolean(configDraft.value.model.trim())
    && Boolean(configDraft.value.api_key_ref.trim())
    && Boolean(configDraft.value.command.trim())
  ))
  const canStart = computed(() => (
    installed.value
    && (configured.value || hasCompleteConfig.value)
    && !isStarting.value
    && status.value !== 'running'
  ))
  const canShutdown = computed(() => available.value && !isShuttingDown.value && status.value === 'running')
  const canReviewProposal = computed(() => (
    !isReviewingProposal.value && !useUIStore().isExecutionLocked
  ))
  const canUndo = computed(() => (
    undoAvailable.value && !isUndoing.value && !useUIStore().isExecutionLocked
  ))

  function applyConfig(next: Partial<OpenHandsAgentConfig> | null | undefined): void {
    if (!next) return
    installed.value = Boolean(next.installed)
    configured.value = Boolean(next.configured)
    configDraft.value = {
      provider: next.provider ?? configDraft.value.provider,
      model: next.model ?? configDraft.value.model,
      api_key_ref: next.api_key_ref ?? configDraft.value.api_key_ref,
      command: next.command ?? configDraft.value.command,
    }
    configDirty.value = false
    if (next.message !== undefined) {
      message.value = next.message
    }
  }

  function applyStatus(next: OpenHandsAgentStatus): void {
    available.value = next.available
    status.value = next.status
    iframeUrl.value = next.iframe_url
    externalUrl.value = next.external_url
    message.value = next.message
    if (next.installed !== undefined || next.configured !== undefined || next.config) {
      applyConfig({
        installed: next.installed ?? next.config?.installed ?? installed.value,
        configured: next.configured ?? next.config?.configured ?? configured.value,
        provider: next.config?.provider ?? configDraft.value.provider,
        model: next.config?.model ?? configDraft.value.model,
        api_key_ref: next.config?.api_key_ref ?? configDraft.value.api_key_ref,
        command: next.config?.command ?? configDraft.value.command,
      })
    }
    context.value = next.context ?? context.value
    proposals.value = next.proposals ?? proposals.value
    approvals.value = (next.approvals ?? approvals.value).filter(
      (approval) => approval.status === 'pending',
    )
    iframeBlocked.value = false
  }

  async function refreshStatus(): Promise<void> {
    isLoadingStatus.value = true
    try {
      applyStatus(await getOpenHandsStatus())
      await refreshConfig()
    } catch (err: unknown) {
      available.value = false
      status.value = 'unavailable'
      message.value = messageFromError(err)
    } finally {
      isLoadingStatus.value = false
    }
  }

  async function refreshConfig(): Promise<void> {
    isLoadingConfig.value = true
    try {
      applyConfig(await getOpenHandsConfig())
    } catch (err: unknown) {
      applyConfig(emptyConfig)
      message.value = messageFromError(err)
    } finally {
      isLoadingConfig.value = false
    }
  }

  function updateConfigDraft<K extends keyof OpenHandsAgentConfigUpdate>(
    key: K,
    value: OpenHandsAgentConfigUpdate[K],
  ): void {
    configDraft.value = { ...configDraft.value, [key]: value }
    configured.value = false
    configDirty.value = true
  }

  async function install(): Promise<void> {
    isInstalling.value = true
    try {
      applyConfig(await installOpenHandsAgent())
    } catch (err: unknown) {
      message.value = messageFromError(err)
    } finally {
      isInstalling.value = false
    }
  }

  async function saveConfig(): Promise<boolean> {
    isSavingConfig.value = true
    try {
      applyConfig(await saveOpenHandsConfig(configDraft.value))
      return true
    } catch (err: unknown) {
      message.value = messageFromError(err)
      return false
    } finally {
      isSavingConfig.value = false
    }
  }

  async function start(): Promise<void> {
    if (!canStart.value) return
    isStarting.value = true
    try {
      if ((!configured.value || configDirty.value) && hasCompleteConfig.value) {
        const saved = await saveConfig()
        if (!saved) return
      }
      applyStatus(await startOpenHandsAgent())
    } catch (err: unknown) {
      status.value = 'error'
      message.value = messageFromError(err)
    } finally {
      isStarting.value = false
    }
  }

  async function retry(): Promise<void> {
    await start()
  }

  async function shutdown(): Promise<void> {
    isShuttingDown.value = true
    try {
      applyStatus(await shutdownOpenHandsAgent())
    } catch (err: unknown) {
      status.value = 'error'
      message.value = messageFromError(err)
    } finally {
      isShuttingDown.value = false
    }
  }

  async function sendCurrentContext(payload: OpenHandsAgentContextPayload): Promise<void> {
    isSendingContext.value = true
    try {
      const response = await sendOpenHandsContext(payload)
      if (response.context) {
        context.value = response.context
      } else {
        context.value = payload
      }
      if (response.message !== undefined) {
        message.value = response.message
      }
    } catch (err: unknown) {
      message.value = messageFromError(err)
    } finally {
      isSendingContext.value = false
    }
  }

  function removeProposal(proposalId: string): void {
    proposals.value = proposals.value.filter((proposal) => proposal.id !== proposalId)
  }

  async function applyProposal(proposalId: string): Promise<void> {
    const uiStore = useUIStore()
    if (uiStore.isExecutionLocked) {
      message.value = 'Proposal review is disabled while execution is running.'
      return
    }
    const proposal = proposals.value.find((item) => item.id === proposalId)
    const draftId = proposal?.draft_id ?? context.value?.draft?.draft_id ?? null
    if (!draftId) {
      message.value = 'Proposal is missing a draft id.'
      return
    }
    isReviewingProposal.value = true
    try {
      const response = await applyOpenHandsProposal(draftId, proposalId)
      const draft = actionDraft(response)
      if (draft?.graph) {
        window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
          detail: {
            graph: draft.graph,
            workflowName: draft.workflow_name,
            workflowDisplayName: draft.workflow_display_name,
            dirty: true,
            pushUndo: true,
            draftRevision: draft.revision,
            validation: draft.validation,
          },
        }))
        undoAvailable.value = true
        if (draft.draft_id || draft.revision !== undefined) {
          context.value = context.value
            ? {
                ...context.value,
                draft: {
                  ...context.value.draft,
                  draft_id: draft.draft_id ?? context.value.draft.draft_id,
                  revision: draft.revision ?? context.value.draft.revision,
                  graph: draft.graph,
                },
              }
            : context.value
        }
      }
      removeProposal(proposalId)
    } catch (err: unknown) {
      message.value = messageFromError(err)
    } finally {
      isReviewingProposal.value = false
    }
  }

  function removeApproval(approvalId: string): void {
    approvals.value = approvals.value.filter((approval) => approval.id !== approvalId)
  }

  async function approveApproval(approvalId: string): Promise<void> {
    isReviewingApproval.value = true
    try {
      await approveOpenHandsApproval(approvalId)
      removeApproval(approvalId)
    } catch (err: unknown) {
      message.value = messageFromError(err)
    } finally {
      isReviewingApproval.value = false
    }
  }

  async function rejectApproval(approvalId: string): Promise<void> {
    isReviewingApproval.value = true
    try {
      await rejectOpenHandsApproval(approvalId)
      removeApproval(approvalId)
    } catch (err: unknown) {
      message.value = messageFromError(err)
    } finally {
      isReviewingApproval.value = false
    }
  }

  async function undoLastChange(): Promise<void> {
    const draftId = context.value?.draft?.draft_id
    const baseRevision = context.value?.draft?.revision
    if (!draftId) {
      message.value = 'No agent draft is available to undo.'
      return
    }
    if (useUIStore().isExecutionLocked) {
      message.value = 'Undo is disabled while execution is running.'
      return
    }
    if (typeof baseRevision !== 'number') {
      message.value = 'No agent draft revision is available to undo.'
      return
    }
    isUndoing.value = true
    try {
      const draft = undoDraft(await undoOpenHandsChange(draftId, baseRevision))
      if (draft?.graph) {
        window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
          detail: {
            graph: draft.graph,
            workflowName: draft.workflow_name,
            workflowDisplayName: draft.workflow_display_name,
            dirty: true,
            draftRevision: draft.revision,
            validation: draft.validation,
          },
        }))
        undoAvailable.value = false
        context.value = context.value
          ? {
              ...context.value,
              draft: {
                ...context.value.draft,
                draft_id: draft.draft_id ?? context.value.draft.draft_id,
                revision: draft.revision ?? context.value.draft.revision,
                graph: draft.graph,
              },
            }
          : context.value
      }
    } catch (err: unknown) {
      message.value = messageFromError(err)
    } finally {
      isUndoing.value = false
    }
  }

  async function rejectProposal(proposalId: string): Promise<void> {
    const proposal = proposals.value.find((item) => item.id === proposalId)
    const draftId = proposal?.draft_id ?? context.value?.draft?.draft_id ?? null
    if (!draftId) {
      message.value = 'Proposal is missing a draft id.'
      return
    }
    isReviewingProposal.value = true
    try {
      await rejectOpenHandsProposal(draftId, proposalId)
      removeProposal(proposalId)
    } catch (err: unknown) {
      message.value = messageFromError(err)
    } finally {
      isReviewingProposal.value = false
    }
  }

  function setIframeBlocked(blocked: boolean): void {
    iframeBlocked.value = blocked
  }

  return {
    status,
    available,
    installed,
    configured,
    configDraft,
    iframeUrl,
    externalUrl,
    message,
    context,
    proposals,
    approvals,
    undoAvailable,
    isLoadingStatus,
    isStarting,
    isShuttingDown,
    isSendingContext,
    isReviewingProposal,
    isLoadingConfig,
    isInstalling,
    isSavingConfig,
    isReviewingApproval,
    isUndoing,
    configDirty,
    iframeBlocked,
    isRunning,
    hasCompleteConfig,
    canStart,
    canShutdown,
    canReviewProposal,
    canUndo,
    applyConfig,
    applyStatus,
    refreshStatus,
    refreshConfig,
    updateConfigDraft,
    install,
    saveConfig,
    start,
    retry,
    shutdown,
    sendCurrentContext,
    applyProposal,
    rejectProposal,
    approveApproval,
    rejectApproval,
    undoLastChange,
    setIframeBlocked,
  }
})
