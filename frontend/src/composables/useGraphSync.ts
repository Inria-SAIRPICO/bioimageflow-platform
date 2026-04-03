import { ref } from 'vue'
import { api } from '@/api/client'
import type { GraphState, ValidationResult } from '@/api/types'

export function useGraphSync() {
  const validationResult = ref<ValidationResult | null>(null)
  const isPending = ref(false)

  let timer: ReturnType<typeof setTimeout> | null = null
  let pendingGraph: GraphState | null = null
  let requestId = 0

  function syncGraph(graph: GraphState): void {
    pendingGraph = graph
    if (timer !== null) {
      clearTimeout(timer)
    }
    timer = setTimeout(() => {
      sendNow()
    }, 300)
  }

  async function sendNow(): Promise<void> {
    if (pendingGraph === null) return
    const graph = pendingGraph
    pendingGraph = null
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }

    const thisId = ++requestId
    isPending.value = true

    try {
      const response = await api.put('/api/v1/graph', graph)
      // Only apply if this is still the latest request
      if (thisId === requestId) {
        validationResult.value = response.data
      }
    } finally {
      if (thisId === requestId) {
        isPending.value = false
      }
    }
  }

  async function flushNow(): Promise<void> {
    await sendNow()
  }

  async function patchParameters(
    nodeId: string,
    parameters: Record<string, unknown>,
  ): Promise<void> {
    await api.patch(`/api/v1/graph/nodes/${nodeId}/parameters`, parameters)
  }

  return { syncGraph, flushNow, patchParameters, validationResult, isPending }
}
