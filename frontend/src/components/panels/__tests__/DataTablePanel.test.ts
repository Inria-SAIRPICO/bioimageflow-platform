import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h, inject, provide, type VNodeChild } from 'vue'
import PrimeVue from 'primevue/config'
import DataTablePanel from '../DataTablePanel.vue'
import NodeDataTable from '../NodeDataTable.vue'
import { api } from '@/api/client'
import type { GraphState, NodeState } from '@/api/types'
import { useDataTableStore } from '@/stores/dataTable'
import { useUIStore } from '@/stores/ui'
import { _resetGraphSyncForTest, useGraphSync } from '@/composables/useGraphSync'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockedPost = vi.mocked(api.post)

function node(id: string, name = id): NodeState {
  return {
    id,
    name,
    tool_name: `tool-${id}`,
    position: [0, 0],
    parameters: {},
    resources: {},
    output_templates: {},
    enabled: true,
    collapsed: false,
  }
}

function edge(id: string, source: string, target: string) {
  return {
    id,
    type: 'column_ref' as const,
    source_node: source,
    target_node: target,
    source_output: 'out',
    target_input: 'input',
  }
}

function activate(graph: GraphState, selectedNodeIds: string[], workflowId = 'workflow') {
  const canvasId = canvasIdFromPanelId(`workflow:${workflowId}`)
  const descriptor = { kind: 'root' as const, canvasId, workflowId }
  const graphSync = useGraphSync({ descriptor, getWorkflowId: () => workflowId })
  graphSync.currentGraph.value = graph
  const ui = useUIStore()
  ui.setCanvasWorkflow(canvasId, workflowId, workflowId)
  ui.setCanvasSelectedNodes(canvasId, selectedNodeIds)
  canvasSessionRegistry.activate(canvasId)
  useDataTableStore().registerCanvas(canvasId)
  return { canvasId, graphSync }
}

function stacked(message = 'These indices cannot be aligned safely.') {
  return {
    data: {
      mode: 'stacked' as const,
      sources: [],
      reason: 'incompatible_lineage',
      message,
    },
  }
}

const DataTableStub = defineComponent({
  props: { value: { type: Array, required: true } },
  setup(props, { slots }) {
    provide('rows', props.value as Record<string, unknown>[])
    return () => h('div', slots.default?.())
  },
})

const ColumnStub = defineComponent({
  props: { field: { type: String, required: true } },
  setup(_props, { slots }) {
    const rows = inject<Record<string, unknown>[]>('rows', [])
    return () => {
      const children: VNodeChild[] = [...(slots.header?.() ?? [])]
      for (const row of rows) children.push(...(slots.body?.({ data: row }) ?? []))
      return h('div', children)
    }
  },
})

const ImageCellStub = defineComponent({
  props: {
    nodeId: String,
    row: Number,
    col: String,
    value: String,
    thumbnailEnabled: Boolean,
    showImageActions: Boolean,
  },
  template: '<div data-testid="image-cell">{{ nodeId }}:{{ row }}:{{ col }}:{{ value }}:{{ thumbnailEnabled }}:{{ showImageActions }}</div>',
})

describe('DataTablePanel consolidation', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    _resetGraphSyncForTest()
    mockedPost.mockReset()
  })

  afterEach(() => vi.restoreAllMocks())

  it('shows the empty selection state without querying', async () => {
    const graph = { nodes: [node('a')], edges: [] }
    activate(graph, [])
    const wrapper = mount(DataTablePanel, {
      global: { plugins: [PrimeVue], stubs: { InputNumber: true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('No node selected')
    expect(mockedPost).not.toHaveBeenCalled()
  })

  it('resolves upstream depth in topological order and marks only the selection as anchor', async () => {
    const graph = {
      nodes: [node('a', 'A'), node('b', 'B'), node('c', 'C')],
      edges: [edge('ab', 'a', 'b'), edge('bc', 'b', 'c')],
    }
    activate(graph, ['c'])
    useDataTableStore().setUpstreamDepth(2)
    mockedPost.mockResolvedValue(stacked() as never)
    mount(DataTablePanel, {
      global: {
        plugins: [PrimeVue],
        stubs: { InputNumber: true, NodeDataTable: true },
      },
    })
    await flushPromises()

    const request = mockedPost.mock.calls[0][1] as { sources: Array<Record<string, unknown>> }
    expect(request.sources.map((source) => [source.node_id, source.role])).toEqual([
      ['a', 'context'],
      ['b', 'context'],
      ['c', 'anchor'],
    ])
  })

  it('keeps all explicitly selected nodes as anchors', async () => {
    const graph = {
      nodes: [node('a'), node('b'), node('c')],
      edges: [edge('ab', 'a', 'b'), edge('bc', 'b', 'c')],
    }
    activate(graph, ['a', 'b', 'c'])
    mockedPost.mockResolvedValue(stacked() as never)
    mount(DataTablePanel, {
      global: { plugins: [PrimeVue], stubs: { InputNumber: true, NodeDataTable: true } },
    })
    await flushPromises()

    const request = mockedPost.mock.calls[0][1] as { sources: Array<Record<string, unknown>> }
    expect(request.sources.map((source) => source.role)).toEqual(['anchor', 'anchor', 'anchor'])
  })

  it('falls back locally for independent selections', async () => {
    activate({ nodes: [node('a', 'A'), node('b', 'B')], edges: [] }, ['a', 'b'])
    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [PrimeVue],
        stubs: { InputNumber: true, NodeDataTable: true },
      },
    })
    await flushPromises()

    expect(mockedPost).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="data-table-fallback"]').text()).toContain('independent')
    expect(wrapper.findAllComponents({ name: 'NodeDataTable' })).toHaveLength(2)
  })

  it('shows the backend fallback reason and existing per-node tables', async () => {
    const graph = {
      nodes: [node('a'), node('b')],
      edges: [edge('ab', 'a', 'b')],
    }
    activate(graph, ['a', 'b'])
    mockedPost.mockResolvedValue(stacked('Selected rows would be lost.') as never)
    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [PrimeVue],
        stubs: { InputNumber: true, NodeDataTable: true },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Selected rows would be lost.')
    expect(wrapper.findAllComponents({ name: 'NodeDataTable' })).toHaveLength(2)
  })

  it('sends scoped published subworkflow outputs with aliases and column filters', async () => {
    const subworkflow = node('sub', 'Segment')
    subworkflow.tool_name = '__sub_workflow__'
    subworkflow.sub_workflow = { nodes: [node('inner')], edges: [] }
    subworkflow.published_outputs = [{
      name: 'published_mask',
      internal_node_id: 'inner',
      internal_output: 'mask',
      schema: { type: 'ImageFile' },
    }]
    activate({ nodes: [subworkflow], edges: [] }, ['sub'])
    mockedPost.mockResolvedValue(stacked() as never)
    mount(DataTablePanel, {
      global: { plugins: [PrimeVue], stubs: { InputNumber: true, NodeDataTable: true } },
    })
    await flushPromises()

    const request = mockedPost.mock.calls[0][1] as { sources: Array<Record<string, unknown>> }
    expect(request.sources[0]).toMatchObject({
      node_id: 'sub/inner',
      role: 'anchor',
      columns: ['mask'],
      column_aliases: { mask: 'published_mask' },
    })
  })

  it('renders a merged projection and preserves source-row provenance for image actions', async () => {
    activate({ nodes: [node('a', 'Input'), node('b', 'Result')], edges: [edge('ab', 'a', 'b')] }, ['b'])
    mockedPost.mockResolvedValue({
      data: {
        mode: 'merged',
        sources: [
          { node_id: 'a', role: 'context', label: 'Input', column_aliases: {} },
          { node_id: 'b', role: 'anchor', label: 'Result', column_aliases: {} },
        ],
        columns: [{
          id: 's0:path',
          label: 'path',
          type: 'Path',
          source_node_id: 'a',
          source_column: 'path',
        }],
        rows: [{
          index: 'r0::tile',
          values: { 's0:path': '/images/sample.OME.TIFF' },
          source_rows: { a: 7, b: 2 },
        }],
        total_rows: 1,
        page: 0,
        page_size: 50,
      },
    } as never)
    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [PrimeVue],
        stubs: {
          InputNumber: true,
          DataTable: DataTableStub,
          Column: ColumnStub,
          ImageCell: ImageCellStub,
          Paginator: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="merged-data-table"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="image-cell"]').text()).toContain(
      'a:7:path:/images/sample.OME.TIFF:true:true',
    )
    const toolbarActions = wrapper.find('.merged-data-table__toolbar-actions')
    expect(toolbarActions.find('[data-testid="upstream-depth"]').exists()).toBe(true)
    expect(toolbarActions.element.children[0]?.classList).toContain('data-table-panel__controls')
    expect(toolbarActions.element.children[1]?.getAttribute('data-testid')).toBe('download-merged-csv')
  })
})

describe('NodeDataTable Path image detection', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    _resetGraphSyncForTest()
  })

  function renderValues(values: string[], type = 'Path') {
    activate({ nodes: [node('a')], edges: [] }, ['a'])
    const store = useDataTableStore()
    store.nodeDataCache.a = {
      columns: ['path'],
      index: values.map((_, index) => String(index)),
      rows: values.map((path) => ({ path })),
      absolute_rows: values.map((_, index) => index + 4),
      total_rows: values.length,
      page: 0,
      page_size: 50,
      column_types: { path: type },
    }
    return mount(NodeDataTable, {
      props: { nodeId: 'a' },
      global: {
        plugins: [PrimeVue],
        stubs: {
          DataTable: DataTableStub,
          Column: ColumnStub,
          ImageCell: ImageCellStub,
          Paginator: true,
        },
      },
    })
  }

  it('enables thumbnails and viewer actions for image-valued Path cells', () => {
    const wrapper = renderValues(['/images/sample.OME.TIFF'])
    expect(wrapper.find('[data-testid="image-cell"]').text()).toContain(
      'a:4:path:/images/sample.OME.TIFF:true:true',
    )
  })

  it('does not enable thumbnails or viewer actions for other Path cells', () => {
    const wrapper = renderValues(['/data/measurements.csv'])
    expect(wrapper.find('[data-testid="image-cell"]').text()).toContain(
      'a:4:path:/data/measurements.csv:false:false',
    )
  })

  it('applies Path detection per cell in mixed columns', () => {
    const wrapper = renderValues(['/images/sample.tif', '/data/measurements.csv'])
    const cells = wrapper.findAll('[data-testid="image-cell"]')
    expect(cells[0].text()).toContain('/images/sample.tif:true:true')
    expect(cells[1].text()).toContain('/data/measurements.csv:false:false')
  })

  it('does not infer image behavior for string columns', () => {
    const wrapper = renderValues(['/images/sample.tif'], 'str')
    expect(wrapper.find('[data-testid="image-cell"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('/images/sample.tif')
  })

  it('keeps typed image columns suffix-independent', () => {
    const wrapper = renderValues(['/images/no-extension'], 'ImageFile')
    expect(wrapper.find('[data-testid="image-cell"]').text()).toContain(
      '/images/no-extension:true:true',
    )
  })
})
