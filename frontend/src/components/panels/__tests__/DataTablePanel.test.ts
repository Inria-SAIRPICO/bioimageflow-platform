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
import { useExecutionStore } from '@/stores/execution'
import {
  graphSyncCanvasSessions,
  useGraphSync,
  _resetGraphSyncForTest,
} from '@/composables/useGraphSync'
import { api } from '@/api/client'
import { useWorkflowStore } from '@/stores/workflow'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockedGet = vi.mocked(api.get)
const mockedPost = vi.mocked(api.post)

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

const ImageCellStub = defineComponent({
  props: {
    value: { type: String, required: true },
  },
  template: '<div data-testid="image-cell">{{ value }}</div>',
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
    vi.useRealTimers()
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

  it('requests node data with the active canvas workflow identity', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    const graphA = useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
      getWorkflowId: () => 'a',
    })
    useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'b' },
      getWorkflowId: () => 'b',
    })
    graphA.syncGraphState({
      nodes: [{
        id: 'shared',
        name: 'Node A',
        tool_name: 'files',
        position: [0, 0],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
    })
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
    ui.setCanvasSelectedNodes(canvasA, ['shared'])
    ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
    graphSyncCanvasSessions.activate(canvasA)
    useWorkflowStore().current = { name: 'b', display_name: 'Workflow B' } as any
    const fetchNodeData = vi
      .spyOn(useDataTableStore(), 'fetchNodeData')
      .mockResolvedValue(undefined)

    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: { Button: true, NodeDataTable: true },
      },
    })
    await flushPromises()

    expect(fetchNodeData).toHaveBeenCalledWith('shared', {
      toolName: 'files',
      workflowName: 'a',
    })
    wrapper.unmount()
  })

  it('renders image path rows as thumbnail, path, Napari, reveal, copy only', async () => {
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
      column_types: { mask: 'ImageFile' },
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(new Blob(['png'], { type: 'image/png' }), {
          status: 200,
          headers: { 'X-Thumbnail-Status': 'ready' },
        }),
      ),
    )
    if (typeof URL.createObjectURL !== 'function') {
      ;(URL as any).createObjectURL = vi.fn(() => 'blob:mock-url')
      ;(URL as any).revokeObjectURL = vi.fn()
    } else {
      vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url')
      vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    }

    const wrapper = mount(NodeDataTable, {
      props: { nodeId: 'node-1' },
      global: {
        plugins: [pinia, PrimeVue],
        stubs: {
          DataTable: DataTableStub,
          Column: ColumnStub,
          Paginator: true,
        },
      },
    })
    await flushPromises()

    const row = wrapper.find('.node-data-table__image-path')
    expect(row.exists()).toBe(true)
    const orderedTestIds = Array.from(row.element.querySelectorAll('[data-testid]')).map((el) =>
      el.getAttribute('data-testid'),
    )
    expect(orderedTestIds).toEqual([
      'image-thumbnail',
      'path-display',
      'open-napari-0-mask',
      'open-avivator-0-mask',
      'reveal-0-mask',
      'path-copy',
    ])
    expect(row.find('[data-testid="path-open"]').exists()).toBe(false)

    await wrapper.find('[data-testid="path-copy"]').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('/data/results/cell_mask.tif')
  })

  it('renders and copies regular path columns in node data tables', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const dataTableStore = useDataTableStore()
    dataTableStore.nodeDataCache['node-1'] = {
      columns: ['csv_path'],
      index: ['0'],
      rows: [{ csv_path: '/data/results/measurements.csv' }],
      absolute_rows: [0],
      total_rows: 1,
      page: 0,
      page_size: 50,
      column_types: { csv_path: 'Path' },
    }

    const wrapper = mount(NodeDataTable, {
      props: { nodeId: 'node-1' },
      global: {
        plugins: [pinia, PrimeVue],
        stubs: {
          DataTable: DataTableStub,
          Column: ColumnStub,
          ImageCell: ImageCellStub,
          Paginator: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('/data/results/measurements.csv')
    await wrapper.find('[data-testid="path-copy"]').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('/data/results/measurements.csv')
  })

  it('labels sub-workflow output table columns with published output names', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const uiStore = useUIStore()
    const dataTableStore = useDataTableStore()
    uiStore.setSelectedNodes(['sub_1'])
    dataTableStore.nodeDataCache['sub_1/segment_1'] = {
      columns: ['mask', 'score'],
      index: ['0'],
      rows: [{ mask: '/data/results/mask.tif', score: 0.9 }],
      absolute_rows: [0],
      total_rows: 1,
      page: 0,
      page_size: 50,
      column_types: { mask: 'ImageFile', score: 'float' },
    }

    const { currentGraph } = useGraphSync()
    currentGraph.value = {
      nodes: [
        {
          id: 'sub_1',
          name: 'Segment and measure',
          tool_name: '__sub_workflow__',
          position: [0, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
          published_outputs: [{
            name: 'published_mask',
            internal_node_id: 'segment_1',
            internal_output: 'mask',
            schema: { type: 'ImageFile' },
          }],
        },
      ],
      edges: [],
    }

    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: {
          DataTable: DataTableStub,
          Column: ColumnStub,
          ImageCell: ImageCellStub,
          Paginator: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('published_mask')
    expect(wrapper.text()).not.toContain('scorefloat')
    expect(wrapper.text()).toContain('/data/results/mask.tif')
  })


  it('requests scoped internal result data for synthetic sub-workflow nodes', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const uiStore = useUIStore()
    uiStore.setSelectedNodes(['sub_workflow_1'])

    const { currentGraph } = useGraphSync()
    currentGraph.value = {
      nodes: [
        {
          id: 'sub_workflow_1',
          name: 'Fish analysis',
          tool_name: '__sub_workflow__',
          position: [0, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
          published_outputs: [{
            name: 'mask',
            internal_node_id: 'segment_1',
            internal_output: 'mask',
            schema: { type: 'ImageFile' },
          }],
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
    await flushPromises()

    expect(mockedGet).toHaveBeenCalledWith(
      '/api/v1/nodes/sub_workflow_1%2Fsegment_1/data',
      expect.objectContaining({
        params: expect.objectContaining({ page: 0 }),
      }),
    )
    expect(wrapper.text()).not.toContain('No output data available. Execute the workflow')
  })

  it('keeps a selected executed node in a preparing state after 409 and refreshes on executed status', async () => {
    vi.useFakeTimers()
    const pinia = createPinia()
    setActivePinia(pinia)
    const uiStore = useUIStore()
    const executionStore = useExecutionStore()
    uiStore.setSelectedNodes(['node-1'])
    executionStore.nodeStatuses = {
      'node-1': { node_id: 'node-1', status: 'unexecuted', cached: false },
    }

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

    mockedGet
      .mockRejectedValueOnce({ response: { status: 409, data: { detail: 'not ready' } } })
      .mockResolvedValueOnce({
        data: {
          columns: ['path'],
          index: ['0'],
          rows: [{ path: '/tmp/out.csv' }],
          absolute_rows: [0],
          total_rows: 1,
          page: 0,
          page_size: 50,
          column_types: { path: 'Path' },
        },
      })

    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: {
          DataTable: DataTableStub,
          Column: ColumnStub,
          ImageCell: ImageCellStub,
          Paginator: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('No output data available. Execute the workflow')
    expect(wrapper.text()).toContain('Preparing output data')
    expect(mockedGet).toHaveBeenCalledTimes(1)

    executionStore.applyNodeState({ node_id: 'node-1', status: 'executed', cached: false })
    await flushPromises()

    expect(mockedGet).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('/tmp/out.csv')
    vi.useRealTimers()
  })

  it('retries a not-ready data response without showing the no-output empty state', async () => {
    vi.useFakeTimers()
    const pinia = createPinia()
    setActivePinia(pinia)
    const uiStore = useUIStore()
    uiStore.setSelectedNodes(['node-1'])

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

    mockedGet
      .mockRejectedValueOnce({ response: { status: 409, data: { detail: 'not ready' } } })
      .mockResolvedValueOnce({
        data: {
          columns: ['path'],
          index: ['0'],
          rows: [{ path: '/tmp/retried.csv' }],
          absolute_rows: [0],
          total_rows: 1,
          page: 0,
          page_size: 50,
          column_types: { path: 'Path' },
        },
      })

    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: {
          DataTable: DataTableStub,
          Column: ColumnStub,
          ImageCell: ImageCellStub,
          Paginator: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Preparing output data')
    expect(wrapper.text()).not.toContain('No output data available. Execute the workflow')

    await vi.advanceTimersByTimeAsync(1_000)
    await flushPromises()

    expect(mockedGet).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('/tmp/retried.csv')
    vi.useRealTimers()
  })

  it('does not show stale cached rows while an executed-node refresh is not ready', async () => {
    vi.useFakeTimers()
    const pinia = createPinia()
    setActivePinia(pinia)
    const uiStore = useUIStore()
    const executionStore = useExecutionStore()
    const dataTableStore = useDataTableStore()
    uiStore.setSelectedNodes(['node-1'])
    executionStore.nodeStatuses = {
      'node-1': { node_id: 'node-1', status: 'unexecuted', cached: false },
    }
    dataTableStore.nodeDataCache['node-1'] = {
      columns: ['path'],
      index: ['0'],
      rows: [{ path: '/tmp/stale-before-run.csv' }],
      absolute_rows: [0],
      total_rows: 1,
      page: 0,
      page_size: 50,
      column_types: { path: 'Path' },
    }

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

    mockedGet.mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'not ready after execution' } },
    })

    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: {
          DataTable: DataTableStub,
          Column: ColumnStub,
          ImageCell: ImageCellStub,
          Paginator: true,
        },
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('/tmp/stale-before-run.csv')

    executionStore.applyNodeState({ node_id: 'node-1', status: 'executed', cached: false })
    await flushPromises()

    expect(mockedGet).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Preparing output data')
    expect(wrapper.text()).not.toContain('/tmp/stale-before-run.csv')
    vi.useRealTimers()
  })

  it('refreshes again on execution complete after the latest view is updated', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const uiStore = useUIStore()
    const executionStore = useExecutionStore()
    const dataTableStore = useDataTableStore()
    uiStore.setSelectedNodes(['node-1'])
    executionStore.nodeStatuses = {
      'node-1': { node_id: 'node-1', status: 'unexecuted', cached: false },
    }
    dataTableStore.nodeDataCache['node-1'] = {
      columns: ['path'],
      index: ['0'],
      rows: [{ path: '/tmp/before-run.csv' }],
      absolute_rows: [0],
      total_rows: 1,
      page: 0,
      page_size: 50,
      column_types: { path: 'Path' },
    }

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

    mockedGet
      .mockResolvedValueOnce({
        data: {
          columns: ['path'],
          index: ['0'],
          rows: [{ path: '/tmp/old-latest.csv' }],
          absolute_rows: [0],
          total_rows: 1,
          page: 0,
          page_size: 50,
          column_types: { path: 'Path' },
        },
      })
      .mockResolvedValueOnce({
        data: {
          columns: ['path'],
          index: ['0'],
          rows: [{ path: '/tmp/fresh-latest.csv' }],
          absolute_rows: [0],
          total_rows: 1,
          page: 0,
          page_size: 50,
          column_types: { path: 'Path' },
        },
      })

    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: {
          DataTable: DataTableStub,
          Column: ColumnStub,
          ImageCell: ImageCellStub,
          Paginator: true,
        },
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('/tmp/before-run.csv')

    executionStore.applyNodeState({
      node_id: 'node-1',
      status: 'executed',
      cached: false,
      result_key: 'rk_new',
      record_id: 'rec_new',
    })
    await flushPromises()

    expect(mockedGet).toHaveBeenCalledTimes(1)
    expect(dataTableStore.nodeDataCache['node-1']?.rows[0]?.path).toBe('/tmp/old-latest.csv')

    executionStore.applyExecutionComplete({
      success: true,
      errors: [],
      node_statuses: {
        'node-1': {
          node_id: 'node-1',
          status: 'executed',
          cached: false,
          result_key: 'rk_new',
          record_id: 'rec_new',
        },
      },
    })
    await flushPromises()

    expect(mockedGet).toHaveBeenCalledTimes(2)
    expect(dataTableStore.nodeDataCache['node-1']?.rows[0]?.path).toBe('/tmp/fresh-latest.csv')
  })

  it('shows and copies the full path from path cells', async () => {
    const wrapper = mount(PathCell, {
      props: { value: '/data/results/cell_mask.tif' },
      global: { plugins: [createPinia(), PrimeVue] },
    })

    expect(wrapper.text()).toContain('/data/results/cell_mask.tif')
    await wrapper.find('[data-testid="path-display"]').trigger('click')
    const input = wrapper.find<HTMLInputElement>('[data-testid="path-input"]')
    expect(input.exists()).toBe(true)
    expect(input.element.value).toBe('/data/results/cell_mask.tif')
    expect(wrapper.text()).toContain('cell_mask.tif')

    await wrapper.find('[data-testid="path-copy"]').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('/data/results/cell_mask.tif')
  })

  it('does not show the editor action for regular path cells', async () => {
    const wrapper = mount(PathCell, {
      props: { value: '/data/results/measurements.json' },
      global: { plugins: [createPinia(), PrimeVue] },
    })

    expect(wrapper.find('[data-testid="path-open"]').exists()).toBe(false)

    await wrapper.find('[data-testid="path-reveal"]').trigger('click')
    expect(mockedPost).toHaveBeenCalledWith('/api/v1/fs/reveal', {
      path: '/data/results/measurements.json',
    })
  })
})
