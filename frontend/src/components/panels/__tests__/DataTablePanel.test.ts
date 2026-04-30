import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, inject, provide, type VNodeChild } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import DataTablePanel from '../DataTablePanel.vue'
import NodeDataTable from '../NodeDataTable.vue'
import PathCell from '../PathCell.vue'
import { useUIStore } from '@/stores/ui'
import { useDataTableStore } from '@/stores/dataTable'
import { useGraphSync, _resetGraphSyncForTest } from '@/composables/useGraphSync'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

const DataTableStub = defineComponent({
  props: {
    value: { type: Array, required: true },
  },
  setup(props, { slots }) {
    provide('dataTableRows', props.value as Record<string, unknown>[])
    return () => h('div', {}, slots.default?.())
  },
})

const ColumnStub = defineComponent({
  props: {
    field: { type: String, required: true },
  },
  setup(_props, { slots }) {
    const rows = inject<Record<string, unknown>[]>('dataTableRows', [])
    return () => {
      const children: VNodeChild[] = []
      const header = slots.header?.()
      if (header) children.push(...header)
      for (const row of rows) {
        const body = slots.body?.({ data: row })
        if (body) children.push(...body)
      }
      return h('div', {}, children)
    }
  },
})

describe('DataTablePanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    _resetGraphSyncForTest()
    vi.clearAllMocks()
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
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

  it('renders image file paths in node data tables so they can be copied', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const dataTableStore = useDataTableStore()
    dataTableStore.nodeDataCache['node-1'] = {
      columns: ['mask'],
      index: ['0'],
      rows: [{ mask: '/data/results/cell_mask.tif' }],
      absolute_rows: [0],
      total_rows: 1,
      page: 0,
      page_size: 50,
      column_types: { mask: 'ImagePath' },
    }

    const wrapper = mount(NodeDataTable, {
      props: { nodeId: 'node-1' },
      global: {
        plugins: [pinia, PrimeVue],
        stubs: {
          DataTable: DataTableStub,
          Column: ColumnStub,
          ImageCell: { template: '<div data-testid="image-cell" />' },
          Paginator: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('/data/results/cell_mask.tif')
    await wrapper.find('[data-testid="path-copy"]').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('/data/results/cell_mask.tif')
  })

  it('shows and copies the full path from path cells', async () => {
    const wrapper = mount(PathCell, {
      props: { value: '/data/results/cell_mask.tif' },
      global: { plugins: [createPinia(), PrimeVue] },
    })

    expect(wrapper.text()).toContain('/data/results/cell_mask.tif')
    await wrapper.find('[data-testid="path-copy"]').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('/data/results/cell_mask.tif')
  })
})
