import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  applyOpenHandsProposal,
  getOpenHandsStatus,
  rejectOpenHandsProposal,
  sendOpenHandsContext,
  shutdownOpenHandsAgent,
  startOpenHandsAgent,
  type OpenHandsAgentContextPayload,
  type OpenHandsAgentStatus,
  type OpenHandsAgentStatusValue,
  type OpenHandsProposal,
  type OpenHandsProposalActionResponse,
} from '@/api/openhands'

function messageFromError(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function actionDraft(response: OpenHandsProposalActionResponse) {
  return response.draft ?? response.proposal?.draft ?? null
}

export const useOpenHandsAgentStore = defineStore('openHandsAgent', () => {
  const status = ref<OpenHandsAgentStatusValue>('unavailable')
  const available = ref(false)
  const iframeUrl = ref<string | null>(null)
  const externalUrl = ref<string | null>(null)
  const message = ref<string | null>(null)
  const context = ref<OpenHandsAgentContextPayload | null>(null)
  const proposals = ref<OpenHandsProposal[]>([])
  const isLoadingStatus = ref(false)
  const isStarting = ref(false)
  const isShuttingDown = ref(false)
  const isSendingContext = ref(false)
  const isReviewingProposal = ref(false)
  const iframeBlocked = ref(false)

  const isRunning = computed(() => status.value === 'running')
  const canStart = computed(() => available.value && !isStarting.value && status.value !== 'running')
  const canShutdown = computed(() => available.value && !isShuttingDown.value && status.value === 'running')

  function applyStatus(next: OpenHandsAgentStatus): void {
    available.value = next.available
    status.value = next.status
    iframeUrl.value = next.iframe_url
    externalUrl.value = next.external_url
    message.value = next.message
    context.value = next.context ?? context.value
    proposals.value = next.proposals ?? proposals.value
    iframeBlocked.value = false
  }

  async function refreshStatus(): Promise<void> {
    isLoadingStatus.value = true
    try {
      applyStatus(await getOpenHandsStatus())
    } catch (err: unknown) {
      available.value = false
      status.value = 'unavailable'
      message.value = messageFromError(err)
    } finally {
      isLoadingStatus.value = false
    }
  }

  async function start(): Promise<void> {
    isStarting.value = true
    try {
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
    isReviewingProposal.value = true
    try {
      const response = await applyOpenHandsProposal(proposalId)
      const draft = actionDraft(response)
      if (draft?.graph) {
        window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
          detail: {
            graph: draft.graph,
            workflowName: draft.workflow_name,
            workflowDisplayName: draft.workflow_display_name,
            dirty: true,
          },
        }))
      }
      removeProposal(proposalId)
    } catch (err: unknown) {
      message.value = messageFromError(err)
    } finally {
      isReviewingProposal.value = false
    }
  }

  async function rejectProposal(proposalId: string): Promise<void> {
    isReviewingProposal.value = true
    try {
      await rejectOpenHandsProposal(proposalId)
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
    iframeUrl,
    externalUrl,
    message,
    context,
    proposals,
    isLoadingStatus,
    isStarting,
    isShuttingDown,
    isSendingContext,
    isReviewingProposal,
    iframeBlocked,
    isRunning,
    canStart,
    canShutdown,
    applyStatus,
    refreshStatus,
    start,
    retry,
    shutdown,
    sendCurrentContext,
    applyProposal,
    rejectProposal,
    setIframeBlocked,
  }
})
