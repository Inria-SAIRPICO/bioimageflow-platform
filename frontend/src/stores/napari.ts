import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import { useToolRegistryStore } from '@/stores/toolRegistry'

export interface NapariOpenPayload {
  paths: string[]
  clear_layers: boolean
  node_id: string
  row: number
  col: string
  workflow_name: string | null
}

export const useNapariStore = defineStore('napari', () => {
  const requestPending = ref(false)
  const toolRegistry = useToolRegistryStore()

  const phase = computed<'installing' | 'opening' | null>(() => {
    if (!requestPending.value) return null
    return toolRegistry.environmentStatuses.napari === 'creating'
      ? 'installing'
      : 'opening'
  })

  async function open(payload: NapariOpenPayload): Promise<void> {
    if (requestPending.value) return

    requestPending.value = true
    try {
      await api.post('/api/v1/napari/open', payload)
    } finally {
      requestPending.value = false
    }
  }

  return {
    requestPending,
    phase,
    open,
  }
})
