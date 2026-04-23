import { computed, type ComputedRef } from 'vue'
import { useWebSocket, type ConnectionState } from '@/composables/useWebSocket'

interface Presentation {
  icon: string
  tooltip: string
  color: string
  isConnected: boolean
}

const PRESENTATION: Record<ConnectionState, Presentation> = {
  connected: {
    icon: 'pi pi-circle-fill',
    tooltip: 'Connected to server',
    color: 'var(--p-green-500)',
    isConnected: true,
  },
  connecting: {
    icon: 'pi pi-spin pi-spinner',
    tooltip: 'Connecting...',
    color: 'var(--p-yellow-500)',
    isConnected: false,
  },
  disconnected: {
    icon: 'pi pi-circle',
    tooltip: 'Disconnected — reconnecting...',
    color: 'var(--p-red-500)',
    isConnected: false,
  },
  error: {
    icon: 'pi pi-exclamation-circle',
    tooltip: 'Connection error',
    color: 'var(--p-red-500)',
    isConnected: false,
  },
}

export function useConnectionStatus(): {
  icon: ComputedRef<string>
  tooltip: ComputedRef<string>
  color: ComputedRef<string>
  isConnected: ComputedRef<boolean>
} {
  const { connectionState } = useWebSocket()
  const p = computed(() => PRESENTATION[connectionState.value])
  return {
    icon: computed(() => p.value.icon),
    tooltip: computed(() => p.value.tooltip),
    color: computed(() => p.value.color),
    isConnected: computed(() => p.value.isConnected),
  }
}
