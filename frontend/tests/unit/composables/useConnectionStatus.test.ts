import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

async function setupWithState(
  s: 'connected' | 'connecting' | 'disconnected' | 'error',
) {
  const mod = await import('@/composables/useWebSocket')
  mod.__resetForTests()
  const { connectionState } = mod.useWebSocket()
  connectionState.value = s
  return mod
}

describe('useConnectionStatus', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('connected → green circle and isConnected true', async () => {
    await setupWithState('connected')
    const { useConnectionStatus } = await import(
      '@/composables/useConnectionStatus'
    )
    const s = useConnectionStatus()
    expect(s.icon.value).toBe('pi pi-circle-fill')
    expect(s.tooltip.value).toBe('Connected to server')
    expect(s.color.value).toBe('var(--p-green-500)')
    expect(s.isConnected.value).toBe(true)
  })

  it('connecting → spinner and isConnected false', async () => {
    await setupWithState('connecting')
    const { useConnectionStatus } = await import(
      '@/composables/useConnectionStatus'
    )
    const s = useConnectionStatus()
    expect(s.icon.value).toBe('pi pi-spin pi-spinner')
    expect(s.tooltip.value).toBe('Connecting...')
    expect(s.color.value).toBe('var(--p-yellow-500)')
    expect(s.isConnected.value).toBe(false)
  })

  it('disconnected → empty circle, red, isConnected false', async () => {
    await setupWithState('disconnected')
    const { useConnectionStatus } = await import(
      '@/composables/useConnectionStatus'
    )
    const s = useConnectionStatus()
    expect(s.icon.value).toBe('pi pi-circle')
    expect(s.tooltip.value).toBe('Disconnected — reconnecting...')
    expect(s.color.value).toBe('var(--p-red-500)')
    expect(s.isConnected.value).toBe(false)
  })

  it('error → exclamation icon, red, isConnected false', async () => {
    await setupWithState('error')
    const { useConnectionStatus } = await import(
      '@/composables/useConnectionStatus'
    )
    const s = useConnectionStatus()
    expect(s.icon.value).toBe('pi pi-exclamation-circle')
    expect(s.tooltip.value).toBe('Connection error')
    expect(s.color.value).toBe('var(--p-red-500)')
    expect(s.isConnected.value).toBe(false)
  })

  it('reactivity: updates when connectionState changes', async () => {
    const mod = await setupWithState('disconnected')
    const { useConnectionStatus } = await import(
      '@/composables/useConnectionStatus'
    )
    const s = useConnectionStatus()
    expect(s.isConnected.value).toBe(false)

    mod.useWebSocket().connectionState.value = 'connected'
    expect(s.isConnected.value).toBe(true)
    expect(s.icon.value).toBe('pi pi-circle-fill')
  })
})
