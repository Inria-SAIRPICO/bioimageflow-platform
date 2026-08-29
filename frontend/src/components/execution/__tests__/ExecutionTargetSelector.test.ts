import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { primeVueTestGlobal } from '@/test-utils/mountFixtures'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'
import Select from 'primevue/select'
import ExecutionTargetSelector from '../ExecutionTargetSelector.vue'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn() },
}))

describe('ExecutionTargetSelector', () => {
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
  })

  it('keeps the direct-submit acknowledgement warning visible for managed targets', async () => {
    const registry = useExecutionRegistryStore()
    registry.targets = [
      { id: 'local', label: 'Local', mode: 'local', enabled: true },
      {
        id: 'profile_cluster',
        label: 'Cluster',
        mode: 'managed_remote',
        enabled: true,
        profile_revision: 2,
      },
    ]
    const wrapper = mount(ExecutionTargetSelector, {
      global: primeVueTestGlobal({ pinia }),
    })

    expect(wrapper.find('[data-testid="managed-submit-warning"]').exists()).toBe(false)

    registry.selectedTargetId = 'profile_cluster'
    await nextTick()

    const warning = wrapper.get('[data-testid="managed-submit-warning"]')
    expect(warning.text()).toContain('allocated before its ID is returned')
    expect(warning.text()).toContain('reconnect instead of resubmitting')
  })

  it('omits unavailable managed profiles from the Run selector', () => {
    const registry = useExecutionRegistryStore()
    registry.targets = [
      { id: 'local', label: 'Local', mode: 'local', enabled: true },
      {
        id: 'profile_ready',
        label: 'Ready cluster',
        mode: 'managed_remote',
        enabled: true,
        profile_revision: 2,
      },
      {
        id: 'profile_unavailable',
        label: 'Unavailable cluster',
        mode: 'managed_remote',
        enabled: false,
        disabled_reason: 'Required capability is unavailable.',
        profile_revision: 3,
      },
    ]
    const wrapper = mount(ExecutionTargetSelector, {
      global: primeVueTestGlobal({ pinia }),
    })

    expect(wrapper.findComponent(Select).props('options')).toEqual([
      expect.objectContaining({ id: 'local' }),
      expect.objectContaining({ id: 'profile_ready' }),
    ])
  })
})
