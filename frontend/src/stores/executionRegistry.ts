import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  cancelExecution,
  fetchExecution,
  fetchExecutions,
  fetchExecutionTargets,
  retryExecution,
  type ExecutionSnapshot,
  type ExecutionTarget,
} from '@/api/executions'

const TERMINAL_STATES = new Set(['succeeded', 'failed', 'cancelled', 'lost'])

export const useExecutionRegistryStore = defineStore('execution-registry', () => {
  const targets = ref<ExecutionTarget[]>([
    { id: 'local', label: 'Local', mode: 'local', enabled: true },
  ])
  const selectedTargetId = ref('local')
  const runs = ref<ExecutionSnapshot[]>([])
  const selectedRunId = ref<string | null>(null)
  const loadingTargets = ref(false)
  const loadingRuns = ref(false)
  const error = ref<string | null>(null)

  const selectedTarget = computed(() => (
    targets.value.find(target => target.id === selectedTargetId.value)
    ?? targets.value[0]
    ?? null
  ))
  const selectedRun = computed(() => (
    runs.value.find(run => run.id === selectedRunId.value) ?? runs.value[0] ?? null
  ))
  const activeRuns = computed(() => runs.value.filter(
    run => !TERMINAL_STATES.has(run.state),
  ))

  function upsertRun(snapshot: ExecutionSnapshot): void {
    const index = runs.value.findIndex(run => run.id === snapshot.id)
    if (index < 0) {
      runs.value = [snapshot, ...runs.value]
    } else if (snapshot.revision >= runs.value[index]!.revision) {
      runs.value.splice(index, 1, snapshot)
    }
    selectedRunId.value ??= snapshot.id
  }

  async function loadTargets(): Promise<void> {
    loadingTargets.value = true
    error.value = null
    try {
      const loaded = await fetchExecutionTargets()
      targets.value = loaded.length > 0
        ? loaded
        : [{ id: 'local', label: 'Local', mode: 'local', enabled: true }]
      if (!targets.value.some(target => (
        target.id === selectedTargetId.value && target.enabled
      ))) {
        selectedTargetId.value = targets.value.find(target => target.enabled)?.id ?? 'local'
      }
    } catch (cause) {
      // Local execution remains available while an older backend is starting.
      targets.value = [{ id: 'local', label: 'Local', mode: 'local', enabled: true }]
      selectedTargetId.value = 'local'
      error.value = cause instanceof Error ? cause.message : String(cause)
    } finally {
      loadingTargets.value = false
    }
  }

  async function loadRuns(workflowId?: string | null): Promise<void> {
    loadingRuns.value = true
    error.value = null
    try {
      const page = await fetchExecutions({ workflowId })
      runs.value = page.items
      if (!runs.value.some(run => run.id === selectedRunId.value)) {
        selectedRunId.value = runs.value[0]?.id ?? null
      }
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause)
    } finally {
      loadingRuns.value = false
    }
  }

  async function refreshRun(id: string): Promise<void> {
    upsertRun(await fetchExecution(id))
  }

  async function cancel(id: string): Promise<void> {
    upsertRun(await cancelExecution(id))
  }

  async function retry(id: string): Promise<void> {
    const retryRun = await retryExecution(id)
    upsertRun(retryRun)
    selectedRunId.value = retryRun.id
  }

  function applySnapshot(snapshot: ExecutionSnapshot): void {
    upsertRun(snapshot)
  }

  return {
    targets,
    selectedTargetId,
    selectedTarget,
    runs,
    selectedRunId,
    selectedRun,
    activeRuns,
    loadingTargets,
    loadingRuns,
    error,
    loadTargets,
    loadRuns,
    refreshRun,
    cancel,
    retry,
    applySnapshot,
  }
})
