import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import DataTablePanel from '../DataTablePanel.vue'
import { useUIStore } from '@/stores/ui'
import { useGraphSync, _resetGraphSyncForTest } from '@/composables/useGraphSync'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn() },
}))

describe('DataTablePanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    _resetGraphSyncForTest()
    vi.clearAllMocks()
  })

  it('shows a clear no-node-selected empty state instead of terminal data tables', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const uiStore = useUIStore()
    uiStore.setSelectedNodes([])

    const { currentGraph } = useGraphSync()
    currentGraph.value = {
      nodes: [
        {
          id: 'node-1',
          name: 'Files 1',
          tool_name: 'files',
          position: [0, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        },
      ],
      edges: [],
    }

    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: {
          Button: true,
          NodeDataTable: true,
        },
      },
    })

    expect(wrapper.text().toLowerCase()).toContain('no node selected')
    expect(wrapper.find('[data-testid="node-data-table-node-1"]').exists()).toBe(false)
  })
})
