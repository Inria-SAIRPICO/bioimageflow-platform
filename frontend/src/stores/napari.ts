import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'

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
  const launchPhase = ref<'installing' | 'opening'>('opening')
  const loggerActivationRequest = ref(0)

  const phase = computed<'installing' | 'opening' | null>(() => {
    if (!requestPending.value) return null
    return launchPhase.value
  })

  function applyEnvironmentStatus(payload: Record<string, unknown>): void {
    if (payload.env_name !== 'napari') return
    const status = payload.status
    if (status !== 'creating' && status !== 'opening') return
    launchPhase.value = status === 'creating' ? 'installing' : 'opening'
    loggerActivationRequest.value += 1
  }

  async function open(payload: NapariOpenPayload): Promise<void> {
    if (requestPending.value) return

    launchPhase.value = 'opening'
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
    loggerActivationRequest,
    applyEnvironmentStatus,
    open,
  }
})
