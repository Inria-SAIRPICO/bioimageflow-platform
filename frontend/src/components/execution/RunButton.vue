<script setup lang="ts">
import { computed, ref, type Ref } from 'vue'
import Button from 'primevue/button'
import { useExecutionLock, type ExecutionGraphSync } from '@/composables/useExecutionLock'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
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

function findOutOfDateNodes(): string[] {
  const result: ValidationResult | null = props.graphSync.validationResult.value
  if (!result || !result.node_statuses) return []
  return Object.values(result.node_statuses)
    .filter((ns) => ns.status === 'out_of_date')
    .map((ns) => ns.node_id)
}

async function runCore(nodes?: string[]) {
  const outOfDate = findOutOfDateNodes()
  if (outOfDate.length > 0) {
    const ok = await confirmOutOfDate(outOfDate)
    if (!ok) return
  }
  try {
    await lockForExecution({ graph: props.graph, nodes, graphSync: props.graphSync })
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
      // pre-run flushNow has just refreshed it.
      const errs = props.graphSync.validationResult.value?.errors ?? []
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
          : 'Fix them before running'
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
      detail: err?.message ?? 'Unknown error',
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

    <div
      v-if="confirmOpen"
      class="run-button__confirm"
      data-testid="out-of-date-confirm"
    >
      <p>
        The following out-of-date nodes will be re-executed, replacing their
        previous outputs:
      </p>
      <ul>
        <li v-for="nid in pendingOutOfDateNodes" :key="nid">{{ nid }}</li>
      </ul>
      <div class="run-button__confirm-actions">
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
      </div>
    </div>
  </div>
</template>

<style scoped>
.run-button-group {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.run-button__confirm {
  position: absolute;
  background: var(--p-surface-0);
  border: 1px solid var(--p-surface-300);
  padding: 1rem;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
.run-button__confirm-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
</style>
