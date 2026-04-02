import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type {
  ExecutionResult,
  ExecutionStatus,
  GraphState,
  ProgressInfo,
} from '@/api/types'

export const useExecutionStore = defineStore('execution', () => {
  const state = ref<'running' | 'idle'>('idle')
  const lastResult = ref<ExecutionResult | null>(null)
  const progress = ref<ProgressInfo | null>(null)
  const error = ref<string | null>(null)

  const isRunning = computed(() => state.value === 'running')

  async function fetchStatus() {
    try {
      const { data } = await api.get<ExecutionStatus>(
        '/api/v1/execution/status',
      )
      state.value = data.state
      lastResult.value = data.last_result
      progress.value = data.progress
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    }
  }

  async function run(graph: GraphState, nodes?: string[]) {
    if (state.value === 'running') {
      throw new Error('already running')
    }
    try {
      state.value = 'running'
      error.value = null
      await api.post('/api/v1/execution/run', { graph, nodes })
    } catch (e: unknown) {
      state.value = 'idle'
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    }
  }

  async function stop() {
    await api.post('/api/v1/execution/stop')
    state.value = 'idle'
  }

  async function clear(nodeIds: string[]) {
    await api.post('/api/v1/execution/clear', { nodes: nodeIds })
  }

  function applyProgress(p: ProgressInfo) {
    progress.value = p
  }

  function applyExecutionComplete(payload: ExecutionResult) {
    state.value = 'idle'
    lastResult.value = payload
    progress.value = null
  }

  return {
    state,
    lastResult,
    progress,
    error,
    isRunning,
    fetchStatus,
    run,
    stop,
    clear,
    applyProgress,
    applyExecutionComplete,
  }
})
