<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useGraphSync } from '@/composables/useGraphSync'
import { useOpenHandsAgentStore } from '@/stores/openHandsAgent'
import { useUIStore } from '@/stores/ui'
import { useWorkflowStore } from '@/stores/workflow'

const agentStore = useOpenHandsAgentStore()
const uiStore = useUIStore()
const workflowStore = useWorkflowStore()
const graphSync = useGraphSync()

const {
  available,
  installed,
  status,
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
  isInstalling,
  isReviewingApproval,
  isUndoing,
  iframeBlocked,
  canStart,
  canShutdown,
  canReviewProposal,
  canUndo,
} = storeToRefs(agentStore)

const workflowLabel = computed(() => (
  workflowStore.current?.display_name
  ?? uiStore.activeWorkflowName
  ?? 'No workflow'
))

const nodeCount = computed(() => graphSync.currentGraph.value.nodes.length)
const selectedCount = computed(() => uiStore.selectedNodeIds.length)
const externalTarget = computed(() => externalUrl.value ?? iframeUrl.value)
const showIframe = computed(() => Boolean(iframeUrl.value) && !iframeBlocked.value)
const unavailableMessage = computed(() => (
  message.value ?? 'OpenHands Agent is not available for this session.'
))
const draftRevision = computed(() => graphSync.revision?.value ?? 0)

function currentContextPayload() {
  return {
    workflow_name: workflowStore.current?.name ?? null,
    workflow_display_name: workflowStore.current?.display_name ?? uiStore.activeWorkflowName,
    selected_node_ids: [...uiStore.selectedNodeIds],
    dirty: uiStore.hasUnsavedChanges,
    draft: {
      draft_id: graphSync.draft_id.value,
      revision: draftRevision.value,
      graph: graphSync.currentGraph.value,
      workflow_name: workflowStore.current?.name ?? null,
      workflow_display_name: workflowStore.current?.display_name ?? uiStore.activeWorkflowName,
    },
  }
}

async function sendContext(): Promise<void> {
  await graphSync.flushNow()
  await agentStore.sendCurrentContext(currentContextPayload())
}

function openExternal(): void {
  if (!externalTarget.value) return
  window.open(externalTarget.value, '_blank', 'noopener')
}

onMounted(() => {
  if (!isLoadingStatus.value) {
    void agentStore.refreshStatus()
  }
})
</script>

<template>
  <section class="openhands-agent-panel" data-testid="openhands-agent-panel">
    <header class="openhands-agent-panel__header">
      <div>
        <h2>OpenHands Agent</h2>
        <span data-testid="openhands-agent-status">{{ status }}</span>
      </div>
      <div class="openhands-agent-panel__actions">
        <button
          type="button"
          :disabled="!canStart"
          data-testid="openhands-agent-start"
          @click="agentStore.start"
        >
          Start
        </button>
        <button
          type="button"
          :disabled="!canStart"
          data-testid="openhands-agent-retry"
          @click="agentStore.retry"
        >
          Retry
        </button>
        <button
          type="button"
          :disabled="!canShutdown"
          data-testid="openhands-agent-shutdown"
          @click="agentStore.shutdown"
        >
          Shutdown
        </button>
        <button
          type="button"
          :disabled="!canUndo"
          data-testid="openhands-agent-undo"
          @click="agentStore.undoLastChange"
        >
          Undo
        </button>
      </div>
    </header>

    <section class="openhands-agent-panel__settings" aria-label="OpenHands settings">
      <button
        v-if="!installed"
        type="button"
        :disabled="isInstalling"
        data-testid="openhands-agent-install"
        @click="agentStore.install"
      >
        Install
      </button>
      <span data-testid="openhands-agent-config-state">
        {{ installed ? 'Installed' : 'Not installed' }} · Configure model and API keys inside OpenHands
      </span>
    </section>

    <div class="openhands-agent-panel__context" data-testid="openhands-agent-context">
      <span>{{ workflowLabel }}</span>
      <span>{{ nodeCount }} nodes</span>
      <span>{{ selectedCount }} selected</span>
      <span>{{ uiStore.hasUnsavedChanges ? 'Unsaved' : 'Saved' }}</span>
      <span>Draft {{ graphSync.draft_id.value ?? 'none' }} rev {{ draftRevision }}</span>
      <button
        type="button"
        :disabled="isSendingContext"
        data-testid="openhands-agent-send-context"
        @click="sendContext"
      >
        Send context
      </button>
    </div>

    <div
      v-if="isLoadingStatus"
      class="openhands-agent-panel__state"
      data-testid="openhands-agent-loading"
    >
      <i class="pi pi-spin pi-spinner" aria-hidden="true" />
      <span>Checking OpenHands...</span>
    </div>

    <div
      v-else-if="!available"
      class="openhands-agent-panel__state"
      data-testid="openhands-agent-unavailable"
    >
      {{ unavailableMessage }}
    </div>

    <template v-else>
      <div
        v-if="iframeBlocked"
        class="openhands-agent-panel__state"
        data-testid="openhands-agent-iframe-blocked"
      >
        <span>OpenHands blocked embedded display.</span>
        <button
          type="button"
          :disabled="!externalTarget"
          data-testid="openhands-agent-open-external"
          @click="openExternal"
        >
          Open in browser
        </button>
      </div>
      <iframe
        v-else-if="showIframe"
        class="openhands-agent-panel__frame"
        data-testid="openhands-agent-iframe"
        :src="iframeUrl ?? undefined"
        title="OpenHands Agent"
        @error="agentStore.setIframeBlocked(true)"
      />
      <div v-else class="openhands-agent-panel__state" data-testid="openhands-agent-ready">
        <span>{{ message ?? 'OpenHands is ready.' }}</span>
        <button
          type="button"
          :disabled="!externalTarget"
          data-testid="openhands-agent-open-external"
          @click="openExternal"
        >
          Open in browser
        </button>
      </div>
    </template>

    <section class="openhands-agent-panel__proposals" aria-label="OpenHands proposals">
      <article
        v-for="approval in approvals"
        :key="approval.id"
        class="openhands-agent-panel__proposal"
        data-testid="openhands-agent-approval"
      >
        <div>
          <h3>Package install</h3>
          <p>{{ approval.package_name }} {{ approval.package_version ?? '' }}</p>
          <p v-if="approval.command">{{ approval.command }}</p>
        </div>
        <div class="openhands-agent-panel__proposal-actions">
          <button
            type="button"
            :disabled="isReviewingApproval"
            data-testid="openhands-agent-approve-approval"
            @click="agentStore.approveApproval(approval.id)"
          >
            Approve
          </button>
          <button
            type="button"
            :disabled="isReviewingApproval"
            data-testid="openhands-agent-reject-approval"
            @click="agentStore.rejectApproval(approval.id)"
          >
            Reject
          </button>
        </div>
      </article>
      <article
        v-for="proposal in proposals"
        :key="proposal.id"
        class="openhands-agent-panel__proposal"
        data-testid="openhands-agent-proposal"
      >
        <div>
          <h3>{{ proposal.title }}</h3>
          <p>{{ proposal.summary }}</p>
        </div>
        <div class="openhands-agent-panel__proposal-actions">
          <button
            type="button"
            :disabled="!canReviewProposal"
            data-testid="openhands-agent-apply-proposal"
            @click="agentStore.applyProposal(proposal.id)"
          >
            Apply
          </button>
          <button
            type="button"
            :disabled="isReviewingProposal"
            data-testid="openhands-agent-reject-proposal"
            @click="agentStore.rejectProposal(proposal.id)"
          >
            Reject
          </button>
        </div>
      </article>
      <div
        v-if="context"
        class="openhands-agent-panel__sent-context"
        data-testid="openhands-agent-sent-context"
      >
        Last sent: {{ context.workflow_display_name ?? context.workflow_name ?? 'Untitled' }}
      </div>
    </section>
  </section>
</template>

<style scoped>
.openhands-agent-panel {
  width: 100%;
  height: 100%;
  min-height: 260px;
  display: flex;
  flex-direction: column;
  background: var(--bif-surface);
  color: var(--p-text-color);
}

.openhands-agent-panel__header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.625rem 0.75rem;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--bif-surface-muted);
}

.openhands-agent-panel__header h2,
.openhands-agent-panel__proposal h3 {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.2;
}

.openhands-agent-panel__header span {
  display: block;
  margin-top: 0.125rem;
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
  text-transform: capitalize;
}

.openhands-agent-panel__actions,
.openhands-agent-panel__proposal-actions {
  display: flex;
  gap: 0.375rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.openhands-agent-panel button {
  min-height: 1.875rem;
  padding: 0 0.625rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: 4px;
  color: var(--p-text-color);
  background: var(--bif-surface);
  cursor: pointer;
}

.openhands-agent-panel button:hover:not(:disabled) {
  background: var(--bif-surface-hover);
}

.openhands-agent-panel button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.openhands-agent-panel__context {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 0.625rem;
  flex-wrap: wrap;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--p-content-border-color);
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
}

.openhands-agent-panel__settings {
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.5rem;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.openhands-agent-panel__settings > span {
  color: var(--p-text-muted-color);
  font-size: 0.75rem;
  white-space: nowrap;
}

.openhands-agent-panel__context span:first-child {
  color: var(--p-text-color);
  font-weight: 600;
}

.openhands-agent-panel__context button {
  margin-left: auto;
}

.openhands-agent-panel__frame {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
  border: 0;
}

.openhands-agent-panel__state {
  flex: 1 1 auto;
  min-height: 8rem;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 0.75rem;
  padding: 1rem;
  text-align: center;
  color: var(--p-text-muted-color);
}

.openhands-agent-panel__proposals {
  flex: 0 0 auto;
  max-height: 40%;
  overflow: auto;
  border-top: 1px solid var(--p-content-border-color);
}

.openhands-agent-panel__proposal {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.openhands-agent-panel__proposal p {
  margin: 0.25rem 0 0;
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
  line-height: 1.35;
}

.openhands-agent-panel__sent-context {
  padding: 0.5rem 0.75rem;
  color: var(--p-text-muted-color);
  font-size: 0.8rem;
}
</style>
