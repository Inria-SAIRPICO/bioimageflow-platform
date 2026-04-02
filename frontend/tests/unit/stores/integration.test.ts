import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

import { useExecutionStore } from '@/stores/execution'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'

describe('stores integration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('all stores coexist in same Pinia instance', () => {
    const execution = useExecutionStore()
    const settings = useSettingsStore()
    const ui = useUIStore()

    expect(execution.state).toBe('idle')
    expect(settings.settings).toBeNull()
    expect(ui.selectedNodeIds).toEqual([])
  })

  it('workflow name in UI store drives tab title', () => {
    const ui = useUIStore()
    ui.setActiveWorkflow('Segmentation Pipeline')
    expect(ui.tabTitle).toBe('BioImageFlow \u2014 Segmentation Pipeline')

    ui.markDirty()
    expect(ui.tabTitle).toBe('BioImageFlow \u2014 Segmentation Pipeline *')
  })

  it('execution lock propagates to UI store', () => {
    const execution = useExecutionStore()
    const ui = useUIStore()

    execution.state = 'running'
    ui.setExecutionLocked(true)

    expect(execution.isRunning).toBe(true)
    expect(ui.isExecutionLocked).toBe(true)
  })
})
