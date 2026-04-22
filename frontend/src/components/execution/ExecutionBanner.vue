<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'

type BannerMode = 'running' | 'stopped' | 'success' | 'failure' | 'hidden'

const exec = useExecutionStore()
const ui = useUIStore()

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

watch(
  () => exec.state,
  (next, prev) => {
    if (next === 'running') {
      clearTimer()
      dismissed.value = false
      terminalMode.value = null
      return
    }
    // idle transition
    if (prev === 'running') {
      const result = exec.lastResult
      if (result == null) {
        // Explicit stop without a last_result yet.
        terminalMode.value = 'stopped'
        scheduleDismiss(DISMISS_STOPPED_MS)
      } else if (result.success) {
        terminalMode.value = 'success'
        scheduleDismiss(DISMISS_SUCCESS_MS)
      } else {
        terminalMode.value = 'failure'
        scheduleDismiss(DISMISS_FAILURE_MS)
        const failedNodeId = Object.values(result.node_statuses ?? {}).find(
          (ns) => ns.status === 'failed',
        )?.node_id
        if (failedNodeId) {
          ui.setSelectedNodes([failedNodeId])
        }
      }
    }
  },
)

const mode = computed<BannerMode>(() => {
  if (dismissed.value) return 'hidden'
  if (exec.state === 'running') return 'running'
  if (terminalMode.value) return terminalMode.value
  if (exec.lastResult) {
    return exec.lastResult.success ? 'success' : 'failure'
  }
  return 'hidden'
})

const isVisible = computed(() => mode.value !== 'hidden')

const headline = computed(() => {
  switch (mode.value) {
    case 'running':
      return 'Executing workflow…'
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
      return ''
  }
})

const currentNodeId = computed(() => exec.progress?.node_id ?? null)

const rowProgress = computed(() => {
  const p = exec.progress
  if (!p || !p.total_rows) return null
  return Math.round((p.row / p.total_rows) * 100)
})

const overallProgress = computed(() => {
  const total = ui.graphNodes.length || 0
  const executed = Object.values(exec.nodeStatuses).filter(
    (ns) => ns.status === 'executed',
  ).length
  if (total === 0) return 0
  return Math.round((executed / total) * 100)
})

const modeClass = computed(() => {
  switch (mode.value) {
    case 'success':
      return 'execution-banner--success'
    case 'failure':
      return 'execution-banner--failure'
    case 'stopped':
      return 'execution-banner--stopped'
    case 'running':
    default:
      return 'execution-banner--running'
  }
})

function onBannerClick() {
  if (mode.value === 'running') return
  clearTimer()
  dismissed.value = true
  terminalMode.value = null
}

async function onStop() {
  await exec.stop()
}

onBeforeUnmount(() => {
  clearTimer()
})

defineExpose({ mode, isVisible })
</script>

<template>
  <Transition name="execution-banner">
    <div
      v-if="isVisible"
      :class="['execution-banner', modeClass]"
      data-testid="execution-banner"
      @click="onBannerClick"
    >
      <div class="execution-banner__row">
        <span class="execution-banner__headline" data-testid="execution-banner-headline">
          {{ headline }}
        </span>
        <span
          v-if="mode === 'running' && currentNodeId"
          class="execution-banner__current-node"
          data-testid="execution-banner-current-node"
        >
          {{ currentNodeId }}
        </span>
        <Button
          v-if="mode === 'running'"
          icon="pi pi-stop"
          label="Stop"
          severity="danger"
          size="small"
          data-testid="execution-banner-stop"
          @click.stop="onStop"
        />
      </div>
      <div v-if="mode === 'running'" class="execution-banner__progress">
        <ProgressBar
          :value="overallProgress"
          data-testid="execution-banner-overall-progress"
          class="execution-banner__bar"
        />
        <ProgressBar
          v-if="rowProgress !== null"
          :value="rowProgress"
          data-testid="execution-banner-row-progress"
          class="execution-banner__bar"
        />
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
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.execution-banner__bar {
  height: 6px;
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
