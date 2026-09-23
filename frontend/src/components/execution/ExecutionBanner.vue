<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import ProgressBar from 'primevue/progressbar'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'

type BannerMode = 'starting' | 'running' | 'stopping' | 'stopped' | 'success' | 'failure' | 'hidden'

const exec = useExecutionStore()
const ui = useUIStore()
const registry = useExecutionRegistryStore()

const DISMISS_SUCCESS_MS = 5000
const DISMISS_FAILURE_MS = 5000
const DISMISS_STOPPED_MS = 3000

// When a terminal banner is visible (stopped/success/failure), this ref
// holds the mode; otherwise it is null.
const terminalMode = ref<BannerMode | null>(null)
const dismissed = ref(false)
let dismissTimer: ReturnType<typeof setTimeout> | null = null

function clearTimer() {
  if (dismissTimer !== null) {
    clearTimeout(dismissTimer)
    dismissTimer = null
  }
}

function scheduleDismiss(ms: number) {
  clearTimer()
  dismissTimer = setTimeout(() => {
    dismissed.value = true
    terminalMode.value = null
  }, ms)
}

function resultMode(result: { success: boolean; errors: Array<Record<string, unknown>> }): BannerMode {
  if (result.success) return 'success'
  return result.errors.some((error) => error.type === 'cancelled') ? 'stopped' : 'failure'
}

watch(
  () => exec.state,
  (next, prev) => {
    if (next === 'starting' || next === 'running' || next === 'stopping') {
      clearTimer()
      dismissed.value = false
      terminalMode.value = null
      return
    }
    // idle transition
    if (prev === 'starting' || prev === 'running' || prev === 'stopping') {
      const result = exec.lastResult
      if (result == null) {
        // A rejected start reports through RunButton instead of presenting a
        // successfully stopped execution.
        if (prev === 'starting') return
        // Explicit stop without a last_result yet.
        terminalMode.value = 'stopped'
        scheduleDismiss(DISMISS_STOPPED_MS)
      } else {
        terminalMode.value = resultMode(result)
        scheduleDismiss(terminalMode.value === 'stopped'
          ? DISMISS_STOPPED_MS
          : terminalMode.value === 'success' ? DISMISS_SUCCESS_MS : DISMISS_FAILURE_MS)
        if (terminalMode.value === 'failure') {
          const failedNodeId = Object.values(result.node_statuses ?? {}).find(
            (ns) => ns.status === 'failed',
          )?.node_id
          if (failedNodeId) ui.setSelectedNodes([failedNodeId])
        }
      }
    }
  },
)

const mode = computed<BannerMode>(() => {
  if (dismissed.value) return 'hidden'
  if (exec.state === 'starting') return 'starting'
  if (exec.state === 'running') return 'running'
  if (exec.state === 'stopping') return 'stopping'
  if (terminalMode.value) return terminalMode.value
  if (exec.lastResult) {
    return resultMode(exec.lastResult)
  }
  return 'hidden'
})

const isVisible = computed(() => mode.value !== 'hidden')
const isDistributedVisible = computed(() => registry.activeRuns.length > 0)

const headline = computed(() => {
  switch (mode.value) {
    case 'starting':
      return 'Starting execution...'
    case 'running':
      return 'Executing workflow…'
    case 'stopping':
      return 'Stopping execution...'
    case 'stopped':
      return 'Execution stopped'
    case 'success':
      return 'Execution complete'
    case 'failure': {
      const firstError = exec.lastResult?.errors?.[0] as
        | { detail?: string }
        | undefined
      const summary =
        typeof firstError?.detail === 'string' ? firstError.detail : 'error'
      return `Execution failed: ${summary}`
    }
    default:
      return registry.activeRuns.length === 1
        ? `${registry.activeRuns[0]!.target_label ?? registry.activeRuns[0]!.target_id}: ${registry.activeRuns[0]!.state}`
        : `${registry.activeRuns.length} executions active`
  }
})

const plannedNodes = computed(() => new Set(exec.plannedNodeIds))
const totalNodes = computed(() => plannedNodes.value.size)
const completedNodes = computed(() => {
  if (mode.value === 'success') return totalNodes.value
  return [...plannedNodes.value].filter(
    (id) => exec.nodeStatuses[id]?.status === 'executed',
  ).length
})
const overallProgress = computed(() => totalNodes.value === 0
  ? 0
  : Math.round((completedNodes.value / totalNodes.value) * 100))
const nodeCountLabel = computed(() => `${completedNodes.value}/${totalNodes.value} nodes complete`)

const currentNodeId = computed(() => {
  const preferred = exec.progress?.node_id
  if (preferred && plannedNodes.value.has(preferred)
    && exec.nodeStatuses[preferred]?.status === 'running') return preferred
  return [...plannedNodes.value].find(
    (id) => exec.nodeStatuses[id]?.status === 'running',
  ) ?? null
})
const currentNodeName = computed(() => currentNodeId.value
  ? exec.plannedNodeNames[currentNodeId.value] || currentNodeId.value
  : null)

const detail = computed(() => {
  if (mode.value !== 'running' || !currentNodeId.value) return null
  const parts = [`Running: ${currentNodeName.value}`]
  const p = exec.progress
  if (p?.node_id === currentNodeId.value && p.total_rows > 0
    && Number.isInteger(p.row) && p.row >= 0) {
    const rowNumber = Math.min(p.row + 1, p.total_rows)
    parts.push(p.status === 'row_complete'
      ? `${rowNumber}/${p.total_rows} rows complete`
      : `Processing row ${rowNumber}/${p.total_rows}`)
  }
  if (p?.node_id === currentNodeId.value && p.status === 'row_progress'
    && p.task_maximum && p.task_maximum > 0
    && p.task_current !== null && p.task_current !== undefined) {
    parts.push(`Task progress ${p.task_current}/${p.task_maximum}`)
  }
  return parts.join(' · ')
})

const modeClass = computed(() => {
  switch (mode.value) {
    case 'success':
      return 'execution-banner--success'
    case 'failure':
      return 'execution-banner--failure'
    case 'stopped':
      return 'execution-banner--stopped'
    case 'starting':
    case 'stopping':
    case 'running':
    default:
      return 'execution-banner--running'
  }
})

function onBannerClick() {
  if (mode.value === 'starting' || mode.value === 'running' || mode.value === 'stopping') return
  clearTimer()
  dismissed.value = true
  terminalMode.value = null
}

function openExecutionPanel() {
  ui.openExecutionPanel()
}

onBeforeUnmount(() => {
  clearTimer()
})

defineExpose({ mode, isVisible })
</script>

<template>
  <Transition name="execution-banner">
    <div
      v-if="isVisible || isDistributedVisible"
      :class="['execution-banner', modeClass]"
      data-testid="execution-banner"
      @click="onBannerClick"
    >
      <div class="execution-banner__row">
        <span class="execution-banner__headline" data-testid="execution-banner-headline">
          {{ headline }}
        </span>
        <button
          type="button"
          class="execution-banner__open"
          data-testid="open-execution-panel"
          @click.stop="openExecutionPanel"
        >
          Open Execution
        </button>
      </div>
      <div
        v-if="totalNodes > 0 && (mode === 'running' || mode === 'stopping' || mode === 'success' || mode === 'failure' || mode === 'stopped')"
        class="execution-banner__progress"
      >
        <ProgressBar
          :value="overallProgress"
          :show-value="false"
          :aria-label="nodeCountLabel"
          data-testid="execution-banner-overall-progress"
          class="execution-banner__bar"
        />
        <span class="execution-banner__bar-label" data-testid="execution-banner-node-count">
          <span>{{ nodeCountLabel }}</span>
        </span>
        <span v-if="detail" class="execution-banner__detail" data-testid="execution-banner-current-node">
          {{ detail }}
        </span>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.execution-banner {
  position: relative;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  color: white;
  font-weight: 500;
}

.execution-banner--running {
  background: var(--p-primary-color, #3b82f6);
  cursor: default;
}

.execution-banner__open {
  margin-left: auto;
  border: 1px solid currentColor;
  border-radius: 4px;
  background: transparent;
  color: inherit;
  padding: 0.15rem 0.45rem;
  cursor: pointer;
}

.execution-banner--success {
  background: var(--p-green-500, #16a34a);
}

.execution-banner--failure {
  background: var(--p-red-500, #dc2626);
}

.execution-banner--stopped {
  background: var(--p-surface-500, #64748b);
}

.execution-banner__row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.execution-banner__headline {
  flex: 1;
}

.execution-banner__progress {
  margin-top: 0.5rem;
  position: relative;
}

.execution-banner__bar {
  height: 1.25rem;
}

.execution-banner__bar-label {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  color: white;
  font-size: 0.8rem;
}

.execution-banner__bar-label span {
  background: rgba(0, 0, 0, 0.75);
  border-radius: 3px;
  padding: 0 0.3rem;
}

.execution-banner__detail {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.8rem;
}

.execution-banner-enter-active,
.execution-banner-leave-active {
  transition: opacity 0.2s ease;
}

.execution-banner-enter-from,
.execution-banner-leave-to {
  opacity: 0;
}
</style>
