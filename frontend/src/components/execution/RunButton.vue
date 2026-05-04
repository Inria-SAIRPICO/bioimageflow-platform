<script setup lang="ts">
import { computed, ref, type Ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { useExecutionLock, type ExecutionGraphSync } from '@/composables/useExecutionLock'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { useWorkflowStore } from '@/stores/workflow'
import {
  outOfDateNodeIdsForExecution,
  validationErrorsForExecution,
} from '@/utils/executionSelection'
import type { GraphState, ValidationResult } from '@/api/types'

const props = defineProps<{
  graph: GraphState
  graphSync: ExecutionGraphSync
  /** Optional: pending-validation flag so the button can disable mid-debounce. */
  syncPending?: Ref<boolean> | boolean
}>()

const emit = defineEmits<{
  'run-started': []
  'confirm-required': [outOfDateNodeIds: string[]]
  'toast': [payload: { severity: 'warn' | 'error'; summary: string; detail?: string }]
}>()

const exec = useExecutionStore()
const ui = useUIStore()
const workflowStore = useWorkflowStore()
const { lockForExecution } = useExecutionLock()

const confirmOpen = ref(false)
const confirmResolve = ref<((value: boolean) => void) | null>(null)
const pendingOutOfDateNodes = ref<string[]>([])

const isPending = computed(() => {
  const p = props.syncPending
  if (typeof p === 'boolean') return p
  if (p && typeof p === 'object' && 'value' in p) return Boolean(p.value)
  return false
})

const runDisabled = computed(() => exec.isRunning || isPending.value)
const runTooltip = computed(() => {
  if (exec.isRunning) return 'Execution in progress'
  if (isPending.value) return 'Waiting for validation…'
  return ''
})

const runSelectedDisabled = computed(
  () => runDisabled.value || ui.selectedNodeIds.length === 0,
)

async function confirmOutOfDate(nodeIds: string[]): Promise<boolean> {
  pendingOutOfDateNodes.value = nodeIds
  confirmOpen.value = true
  emit('confirm-required', nodeIds)
  return new Promise<boolean>((resolve) => {
    confirmResolve.value = resolve
  })
}

function resolveConfirm(value: boolean) {
  confirmOpen.value = false
  const resolve = confirmResolve.value
  confirmResolve.value = null
  pendingOutOfDateNodes.value = []
  if (resolve) resolve(value)
}

/** PrimeVue Dialog can close itself (Escape key) without going through one
 * of our action buttons. When that happens, treat it as a cancel so the
 * pending promise resolves and we don't leak state for the next run. */
function onConfirmDialogVisibilityChange(visible: boolean) {
  if (!visible && confirmResolve.value) {
    const resolve = confirmResolve.value
    confirmResolve.value = null
    pendingOutOfDateNodes.value = []
    resolve(false)
  }
}

function findOutOfDateNodes(nodes?: string[]): string[] {
  const result: ValidationResult | null = props.graphSync.validationResult.value
  if (!result || !result.node_statuses) return []
  return outOfDateNodeIdsForExecution(result.node_statuses, props.graph, nodes)
}

async function runCore(nodes?: string[]) {
  const outOfDate = findOutOfDateNodes(nodes)
  if (outOfDate.length > 0) {
    const ok = await confirmOutOfDate(outOfDate)
    if (!ok) return
  }
  try {
    await lockForExecution({
      graph: props.graph,
      nodes,
      graphSync: props.graphSync,
      workflowName: workflowStore.currentName,
    })
    emit('run-started')
  } catch (e: unknown) {
    const err = e as { response?: { status?: number }; message?: string }
    const status = err?.response?.status
    if (status === 409) {
      emit('toast', {
        severity: 'warn',
        summary: 'An execution is already running',
      })
      return
    }
    if (status === 422 || /validation/i.test(err?.message ?? '')) {
      // Pull the fresh validation result so we can enumerate errors. The
      // pre-run flushNow has just refreshed it; run-time build errors are
      // returned directly by POST /execution/run and stored on exec.
      const errs =
        exec.validationErrors.length > 0
          ? exec.validationErrors
          : validationErrorsForExecution(
              props.graphSync.validationResult.value?.errors ?? [],
              props.graph,
              nodes,
            )
      const firstBadNode = errs.find((e) => e.node)?.node
      if (firstBadNode) {
        ui.setSelectedNodes([firstBadNode])
      }
      const summary =
        errs.length > 0
          ? `Validation errors (${errs.length}) — fix them before running`
          : 'Validation errors found — fix them before running'
      const detail =
        errs.length > 0
          ? errs
              .slice(0, 5)
              .map((e) => {
                const loc = e.node
                  ? e.field
                    ? `${e.node}.${e.field}`
                    : e.node
                  : e.edge_id ?? ''
                return loc ? `• ${loc}: ${e.detail}` : `• ${e.detail}`
              })
              .join('\n') +
            (errs.length > 5 ? `\n…and ${errs.length - 5} more` : '')
          : exec.error ?? 'Fix them before running'
      emit('toast', {
        severity: 'error',
        summary,
        detail,
      })
      return
    }
    emit('toast', {
      severity: 'error',
      summary: 'Run failed',
      detail: exec.error ?? err?.message ?? 'Unknown error',
    })
  }
}

async function onRun() {
  await runCore()
}

async function onRunSelected() {
  const selected = [...ui.selectedNodeIds]
  if (selected.length === 0) return
  await runCore(selected)
}

async function onStop() {
  await exec.stop()
}

defineExpose({
  onRun,
  onRunSelected,
  onStop,
  confirmOpen,
  pendingOutOfDateNodes,
  resolveConfirm,
  runDisabled,
  runTooltip,
  runSelectedDisabled,
})
</script>

<template>
  <div class="run-button-group" data-testid="run-button-group">
    <Button
      v-if="!exec.isRunning"
      icon="pi pi-play"
      label="Run Workflow"
      :disabled="runDisabled"
      :title="runTooltip"
      data-testid="run-workflow-button"
      @click="onRun"
    />
    <Button
      v-if="!exec.isRunning"
      icon="pi pi-play"
      label="Run Selected"
      :disabled="runSelectedDisabled"
      data-testid="run-selected-button"
      severity="secondary"
      @click="onRunSelected"
    />
    <Button
      v-if="exec.isRunning"
      icon="pi pi-stop"
      label="Stop"
      severity="danger"
      data-testid="stop-execution-button"
      @click="onStop"
    />

    <Dialog
      v-model:visible="confirmOpen"
      modal
      :closable="false"
      :close-on-escape="true"
      header="Re-execute out-of-date nodes?"
      :style="{ width: '32rem' }"
      data-testid="out-of-date-confirm"
      @update:visible="onConfirmDialogVisibilityChange"
    >
      <p class="run-button__confirm-message">
        The following out-of-date nodes will be re-executed, replacing their
        previous outputs:
      </p>
      <ul class="run-button__confirm-list">
        <li v-for="nid in pendingOutOfDateNodes" :key="nid">{{ nid }}</li>
      </ul>
      <template #footer>
        <Button
          label="Cancel"
          severity="secondary"
          data-testid="out-of-date-cancel"
          @click="resolveConfirm(false)"
        />
        <Button
          label="Continue"
          data-testid="out-of-date-continue"
          @click="resolveConfirm(true)"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.run-button-group {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.run-button__confirm-message {
  margin: 0 0 0.5rem;
}
.run-button__confirm-list {
  margin: 0;
  padding-left: 1.25rem;
  max-height: 40vh;
  overflow-y: auto;
}
</style>
