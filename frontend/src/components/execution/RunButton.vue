<script setup lang="ts">
import { computed, ref, type Ref } from 'vue'
import Button from 'primevue/button'
import SplitButton from 'primevue/splitbutton'
import type { MenuItem } from 'primevue/menuitem'
import Dialog from 'primevue/dialog'
import { useExecutionLock, type ExecutionGraphSync } from '@/composables/useExecutionLock'
import {
  useExecutionStore,
  type ExecutionCommand,
  type ExecutionMode,
} from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { useCanvasLifecycleStore } from '@/stores/canvasLifecycle'
import { useCanvasPersistence } from '@/composables/useCanvasPersistence'
import {
  outOfDateNodeIdsForExecution,
  validationErrorsForExecution,
} from '@/utils/executionSelection'
import type { GraphState, ValidationResult } from '@/api/types'
import { canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { graphDocumentsEqual } from '@/sessions/graphDocument'

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
const canvasPersistence = useCanvasPersistence()
const canvasLifecycleStore = useCanvasLifecycleStore()
const { lockForExecution } = useExecutionLock()

const confirmOpen = ref(false)
const confirmResolve = ref<((value: boolean) => void) | null>(null)
const pendingOutOfDateNodes = ref<string[]>([])
const advancedConfirmOpen = ref(false)
const pendingAdvancedCommand = ref<ExecutionCommand | null>(null)
const activeWorkflowId = computed(() => ui.activeWorkflowId)
const activeCanvasLifecycleBusy = computed(() => {
  const canvasId = canvasSessionRegistry.activeCanvasId.value
  return canvasId !== null && canvasLifecycleStore.isBusy(canvasId)
})
const isNestedCanvasActive = computed(() => {
  const canvasId = canvasSessionRegistry.activeCanvasId.value
  return canvasId !== null
    && canvasSessionRegistry.get(canvasId)?.descriptor.kind === 'nested'
})

const runDisabled = computed(
  () => exec.isMutationLocked
    || activeCanvasLifecycleBusy.value
    || !activeWorkflowId.value
    || isNestedCanvasActive.value,
)
const runTooltip = computed(() => {
  if (exec.isStarting) return 'Execution is starting'
  if (exec.isStopping) return 'Execution is stopping'
  if (exec.isRunning) return 'Execution in progress'
  if (isNestedCanvasActive.value) {
    return 'Run the owning root workflow to execute this nested-workflow'
  }
  if (!activeWorkflowId.value) return 'Open or save a workflow before running'
  return ''
})

const runLabel = computed(() => exec.isStarting ? 'Starting...' : 'Run Workflow')
const stopLabel = computed(() => exec.isStopping ? 'Stopping...' : 'Stop')
const primaryButtonProps = computed(() => ({
  title: runTooltip.value,
  'data-testid': 'run-workflow-button',
}))

const runSelectedDisabled = computed(
  () => runDisabled.value || ui.selectedNodeIds.length === 0,
)
const retryAvailable = computed(() => (
  !runDisabled.value
  && exec.canRetry
  && exec.executionWorkflowId === activeWorkflowId.value
  && exec.executionId !== null
))
const invalidateFailedAvailable = computed(() => (
  retryAvailable.value && exec.canInvalidateFailed
))
const runMenuItems = computed<MenuItem[]>(() => [
  {
    label: 'Run Selected',
    icon: 'pi pi-forward',
    disabled: runSelectedDisabled.value,
    command: () => void onRunSelected(),
  },
  { separator: true },
  {
    label: 'Retry Failed Execution',
    icon: 'pi pi-refresh',
    disabled: !retryAvailable.value,
    command: () => void onRetry(),
  },
  {
    label: 'Invalidate Failed Nodes and Retry…',
    icon: 'pi pi-replay',
    disabled: !invalidateFailedAvailable.value,
    command: () => requestAdvancedCommand({
      kind: 'invalidate_failed',
      retryOf: exec.executionId!,
    }),
  },
  { separator: true },
  {
    label: 'Recompute Workflow…',
    icon: 'pi pi-sync',
    disabled: runDisabled.value,
    command: () => requestAdvancedCommand({ kind: 'recompute' }),
  },
])

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

function currentExecutionGraph(): GraphState {
  return props.graphSync.currentGraph?.value ?? props.graph
}

function findOutOfDateNodes(
  result: ValidationResult | null,
  graph: GraphState,
  nodes?: string[],
): string[] {
  if (!result || !result.node_statuses) return []
  return outOfDateNodeIdsForExecution(result.node_statuses, graph, nodes)
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function commandMode(command: ExecutionCommand): ExecutionMode {
  if (command.kind === 'workflow' || command.kind === 'selected') return 'normal'
  return command.kind
}

function validationNodes(command: ExecutionCommand): string[] | undefined {
  if (command.kind === 'selected') return command.nodes
  if (command.kind === 'retry' || command.kind === 'invalidate_failed') {
    return exec.requestedNodes ?? undefined
  }
  return undefined
}

async function runCore(command: ExecutionCommand) {
  if (isNestedCanvasActive.value) return
  if (exec.isMutationLocked || activeCanvasLifecycleBusy.value) return
  const targetCanvasId = canvasPersistence.canvasId
  const workflowName = activeWorkflowId.value
  if (!workflowName) return
  const isTargetActive = () => canvasPersistence.canvasId === targetCanvasId
    && activeWorkflowId.value === workflowName
  let graph = cloneJson(currentExecutionGraph())
  try {
    const fresh = await canvasPersistence.ensureFreshForCriticalOperation()
    if (!isTargetActive()) return
    if (!fresh) {
      emit('toast', {
        severity: 'warn',
        summary: 'Resolve workflow changes first',
        detail: 'This workflow changed outside the canvas. Choose which version to keep before running.',
      })
      return
    }
    while (true) {
      // Pending validation is a command barrier, not a reason to disable Run.
      // Each iteration captures one exact validated graph and draft revision.
      await props.graphSync.flushNow()
      if (!isTargetActive()) return
      const preparedGraph = cloneJson(currentExecutionGraph())
      const preparedValidation = cloneJson(props.graphSync.validationResult.value)
      const preparedDraftRevision = canvasPersistence.acceptedDraftRevision.value
      if (targetCanvasId !== null && preparedDraftRevision === null) {
        throw new Error('An accepted draft revision is required for execution')
      }
      const nodes = validationNodes(command)
      const outOfDate = command.kind === 'recompute' ? [] : findOutOfDateNodes(
        preparedValidation,
        preparedGraph,
        nodes,
      )
      if (outOfDate.length > 0) {
        const ok = await confirmOutOfDate(outOfDate)
        if (!ok) return
        if (!isTargetActive()) return
        if (
          !graphDocumentsEqual(currentExecutionGraph(), preparedGraph)
          || canvasPersistence.acceptedDraftRevision.value !== preparedDraftRevision
        ) {
          continue
        }
      }

      graph = preparedGraph
      const started = await lockForExecution({
        graph: preparedGraph,
        ...(command.kind === 'selected' ? { nodes: command.nodes } : {}),
        validationResult: preparedValidation,
        workflowName,
        mode: commandMode(command),
        ...(
          command.kind === 'retry' || command.kind === 'invalidate_failed'
            ? { retryOfExecutionId: command.retryOf }
            : {}
        ),
        isTargetActive,
        ...(targetCanvasId !== null
          ? {
              canvasId: targetCanvasId,
              acceptedDraftRevision: preparedDraftRevision,
            }
          : {}),
      })
      if (!started || !isTargetActive()) return
      emit('run-started')
      return
    }
  } catch (e: unknown) {
    const err = e as {
      response?: { status?: number; data?: { error?: string } }
      message?: string
    }
    const status = err?.response?.status
    if (status === 409) {
      const conflictCode = err.response?.data?.error ?? exec.conflictCode
      if (
        conflictCode === 'draft_revision_conflict'
        || conflictCode === 'draft_graph_mismatch'
      ) {
        emit('toast', {
          severity: 'warn',
          summary: 'Workflow changed before execution',
          detail: 'Refresh the workflow, resolve any draft changes, and retry.',
        })
        return
      }
      if (conflictCode === 'execution_retry_unavailable') {
        emit('toast', {
          severity: 'warn',
          summary: 'Retry is no longer available',
          detail: exec.error ?? 'Run the workflow again to establish a new retry point.',
        })
        return
      }
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
              graph,
              validationNodes(command),
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
  await runCore({ kind: 'workflow' })
}

async function onRunSelected() {
  const selected = [...ui.selectedNodeIds]
  if (selected.length === 0) return
  await runCore({ kind: 'selected', nodes: selected })
}

async function onRetry() {
  if (!retryAvailable.value || exec.executionId === null) return
  await runCore({ kind: 'retry', retryOf: exec.executionId })
}

function requestAdvancedCommand(command: ExecutionCommand): void {
  pendingAdvancedCommand.value = command
  advancedConfirmOpen.value = true
}

async function confirmAdvancedCommand(): Promise<void> {
  const command = pendingAdvancedCommand.value
  advancedConfirmOpen.value = false
  pendingAdvancedCommand.value = null
  if (command) await runCore(command)
}

function cancelAdvancedCommand(): void {
  advancedConfirmOpen.value = false
  pendingAdvancedCommand.value = null
}

async function onStop() {
  await exec.stop()
}

defineExpose({
  onRun,
  onRunSelected,
  onRetry,
  onInvalidateFailed: () => {
    if (invalidateFailedAvailable.value && exec.executionId !== null) {
      requestAdvancedCommand({ kind: 'invalidate_failed', retryOf: exec.executionId })
    }
  },
  onRecompute: () => requestAdvancedCommand({ kind: 'recompute' }),
  onStop,
  confirmOpen,
  pendingOutOfDateNodes,
  resolveConfirm,
  runDisabled,
  runTooltip,
  runSelectedDisabled,
  retryAvailable,
  invalidateFailedAvailable,
})
</script>

<template>
  <div class="run-button-group" data-testid="run-button-group">
    <SplitButton
      v-if="!exec.isRunning"
      icon="pi pi-play"
      :label="runLabel"
      :disabled="runDisabled"
      :button-props="primaryButtonProps"
      :model="runMenuItems"
      @click="onRun"
    />
    <Button
      v-if="exec.isRunning"
      icon="pi pi-stop"
      :label="stopLabel"
      :disabled="!exec.canStop"
      severity="danger"
      data-testid="stop-execution-button"
      @click="onStop"
    />

    <Dialog
      v-model:visible="confirmOpen"
      modal
      :closable="false"
      :close-on-escape="true"
      header="Rebuild nodes before running?"
      :style="{ width: '32rem' }"
      data-testid="out-of-date-confirm"
      @update:visible="onConfirmDialogVisibilityChange"
    >
      <p class="run-button__confirm-message">
        The following nodes need rebuild and will be re-executed, replacing
        their previous outputs:
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

    <Dialog
      v-model:visible="advancedConfirmOpen"
      modal
      header="Confirm cache invalidation"
      :style="{ width: '32rem' }"
      data-testid="advanced-run-confirm"
      @hide="pendingAdvancedCommand = null"
    >
      <p v-if="pendingAdvancedCommand?.kind === 'recompute'">
        Recompute the complete enabled workflow? Existing cache selections will be invalidated before execution. Cached records remain on disk until a separate cleanup.
      </p>
      <p v-else>
        Invalidate the failed nodes and everything downstream, then retry the original execution targets? Cached records remain on disk until a separate cleanup.
      </p>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="cancelAdvancedCommand" />
        <Button
          label="Continue"
          severity="danger"
          data-testid="advanced-run-continue"
          @click="confirmAdvancedCommand"
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
