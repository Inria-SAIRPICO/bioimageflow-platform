import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  cancelExecution,
  fetchExecution,
  fetchExecutionLogs,
  fetchExecutions,
  fetchExecutionTargets,
  planExecutionRetry,
  startExecutionRetry,
  type ExecutionCapabilities,
  type ExecutionRetryPlan,
  type RecomputeRequest,
  type ExecutionSnapshot,
  type ExecutionTarget,
} from '@/api/executions'

const TERMINAL_STATES = new Set(['succeeded', 'failed', 'cancelled', 'lost'])

export const useExecutionRegistryStore = defineStore('execution-registry', () => {
  const targets = ref<ExecutionTarget[]>([
    { id: 'local', label: 'Local', mode: 'local', enabled: true },
  ])
  const selectedTargetId = ref('local')
  const capabilities = ref<ExecutionCapabilities | null>(null)
  const runs = ref<ExecutionSnapshot[]>([])
  const selectedRunId = ref<string | null>(null)
  const loadingTargets = ref(false)
  const loadingRuns = ref(false)
  const totalRuns = ref(0)
  const pageLimit = ref(50)
  const nextOffset = ref(0)
  const loadedWorkflowId = ref<string | null>(null)
  const error = ref<string | null>(null)
  let loadGeneration = 0
  let activePageLoadGeneration: number | null = null
  let bufferedSnapshots: Array<{ snapshot: ExecutionSnapshot; initial: boolean }> = []

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
  const hasMoreRuns = computed(() => nextOffset.value < totalRuns.value)

  function upsertRun(snapshot: ExecutionSnapshot): void {
    const index = runs.value.findIndex(run => run.id === snapshot.id)
    if (index < 0) {
      runs.value = [snapshot, ...runs.value]
    } else if (snapshot.revision >= runs.value[index]!.revision) {
      runs.value.splice(index, 1, snapshot)
    }
    selectedRunId.value ??= snapshot.id
    totalRuns.value = Math.max(totalRuns.value, runs.value.length)
  }

  function snapshotMatchesLoadedScope(snapshot: ExecutionSnapshot): boolean {
    return loadedWorkflowId.value === null
      || snapshot.workflow_id === loadedWorkflowId.value
  }

  function applySnapshotNow(snapshot: ExecutionSnapshot, initial: boolean): void {
    const known = runs.value.some(run => run.id === snapshot.id)
    if (initial && !known) totalRuns.value += 1
    upsertRun(snapshot)
  }

  async function loadTargets(): Promise<void> {
    loadingTargets.value = true
    error.value = null
    try {
      const loaded = await fetchExecutionTargets()
      capabilities.value = loaded.capabilities
      targets.value = loaded.targets.length > 0
        ? loaded.targets
        : [{ id: 'local', label: 'Local', mode: 'local', enabled: true }]
      if (!targets.value.some(target => (
        target.id === selectedTargetId.value && target.enabled
      ))) {
        selectedTargetId.value = targets.value.find(target => target.enabled)?.id ?? 'local'
      }
    } catch (cause) {
      targets.value = []
      capabilities.value = null
      error.value = cause instanceof Error ? cause.message : String(cause)
    } finally {
      loadingTargets.value = false
    }
  }

  async function loadRuns(workflowId?: string | null): Promise<void> {
    const normalizedWorkflowId = workflowId ?? null
    const generation = ++loadGeneration
    activePageLoadGeneration = generation
    const scopeChanged = loadedWorkflowId.value !== normalizedWorkflowId
    loadedWorkflowId.value = normalizedWorkflowId
    bufferedSnapshots = []
    if (scopeChanged) {
      runs.value = []
      selectedRunId.value = null
      totalRuns.value = 0
      nextOffset.value = 0
    }
    loadingRuns.value = true
    error.value = null
    try {
      const page = await fetchExecutions({
        workflowId: normalizedWorkflowId,
        offset: 0,
        limit: pageLimit.value,
      })
      if (generation !== loadGeneration) return
      const previousSelection = selectedRunId.value
      runs.value = page.items
      totalRuns.value = page.total
      pageLimit.value = page.limit
      nextOffset.value = page.offset + page.items.length
      for (const item of bufferedSnapshots) {
        applySnapshotNow(item.snapshot, item.initial)
      }
      bufferedSnapshots = []
      selectedRunId.value = runs.value.some(run => run.id === previousSelection)
        ? previousSelection
        : runs.value[0]?.id ?? null
    } catch (cause) {
      if (generation !== loadGeneration) return
      for (const item of bufferedSnapshots) {
        applySnapshotNow(item.snapshot, item.initial)
      }
      bufferedSnapshots = []
      error.value = cause instanceof Error ? cause.message : String(cause)
    } finally {
      if (generation === loadGeneration) {
        activePageLoadGeneration = null
        loadingRuns.value = false
      }
    }
  }

  async function loadMoreRuns(): Promise<void> {
    if (loadingRuns.value || !hasMoreRuns.value) return
    const generation = loadGeneration
    loadingRuns.value = true
    error.value = null
    try {
      const page = await fetchExecutions({
        workflowId: loadedWorkflowId.value,
        offset: nextOffset.value,
        limit: pageLimit.value,
      })
      if (generation !== loadGeneration) return
      for (const snapshot of page.items) {
        const index = runs.value.findIndex(run => run.id === snapshot.id)
        if (index < 0) runs.value.push(snapshot)
        else if (snapshot.revision >= runs.value[index]!.revision) {
          runs.value.splice(index, 1, snapshot)
        }
      }
      totalRuns.value = page.total
      pageLimit.value = page.limit
      nextOffset.value = Math.max(nextOffset.value, page.offset + page.items.length)
    } catch (cause) {
      if (generation !== loadGeneration) return
      error.value = cause instanceof Error ? cause.message : String(cause)
    } finally {
      if (generation === loadGeneration) loadingRuns.value = false
    }
  }

  async function refreshRun(id: string): Promise<void> {
    upsertRun(await fetchExecution(id))
  }

  async function cancel(id: string): Promise<void> {
    upsertRun(await cancelExecution(id))
  }

  async function planRetry(
    id: string,
    recompute: RecomputeRequest | null,
  ): Promise<ExecutionRetryPlan> {
    return planExecutionRetry(id, recompute)
  }

  async function startRetry(id: string, planDigest: string): Promise<ExecutionSnapshot> {
    const retryRun = await startExecutionRetry(id, planDigest)
    applySnapshot(retryRun, true)
    const parent = runs.value.find(run => run.id === id)
    if (parent && !parent.child_execution_ids.includes(retryRun.id)) {
      parent.child_execution_ids = [...parent.child_execution_ids, retryRun.id]
    }
    selectedRunId.value = retryRun.id
    totalRuns.value = Math.max(totalRuns.value, runs.value.length)
    return retryRun
  }

  async function selectExecution(id: string): Promise<void> {
    if (!runs.value.some(run => run.id === id)) upsertRun(await fetchExecution(id))
    selectedRunId.value = id
  }

  async function loadLogs(id: string): Promise<string> {
    return fetchExecutionLogs(id)
  }

  function applySnapshot(snapshot: ExecutionSnapshot, initial = false): void {
    if (!snapshotMatchesLoadedScope(snapshot)) return
    if (activePageLoadGeneration !== null) {
      bufferedSnapshots.push({ snapshot, initial })
      return
    }
    applySnapshotNow(snapshot, initial)
  }

  return {
    targets,
    capabilities,
    selectedTargetId,
    selectedTarget,
    runs,
    selectedRunId,
    selectedRun,
    activeRuns,
    hasMoreRuns,
    loadingTargets,
    loadingRuns,
    totalRuns,
    pageLimit,
    error,
    loadTargets,
    loadRuns,
    loadMoreRuns,
    refreshRun,
    cancel,
    planRetry,
    startRetry,
    selectExecution,
    loadLogs,
    applySnapshot,
  }
})
