import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { enableAutoUnmount, mount, flushPromises } from '@vue/test-utils'
import { computed, defineComponent, h, inject, nextTick, provide, ref, type VNodeChild } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import type { DockviewPanelApi } from 'dockview-core'
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
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'
import {
  _resetCanvasStatusProjectionForTest,
  useCanvasStatusProjection,
} from '@/composables/useCanvasStatusProjection'
import type { GraphState, NodeStatus } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

enableAutoUnmount(afterEach)

const mockedGet = vi.mocked(api.get)
const mockedPost = vi.mocked(api.post)

const DEFAULT_EXECUTION_CONTEXT = {
  execution_id: 'exec-data-table',
  workflow_id: 'data-table-workflow',
  draft_revision: 7,
} as const

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

function registerStatusProjection(
  canvasId: CanvasId,
  workflowId: string,
  graphSync: ReturnType<typeof useGraphSync>,
  acceptedDraftRevision: number | null = null,
) {
  return useCanvasStatusProjection({
    descriptor: { kind: 'root', canvasId, workflowId },
    nodes: computed(() => graphSync.currentGraph.value.nodes.map(node => ({
      id: node.id,
      enabled: node.enabled !== false,
    }))),
    validationResult: graphSync.validationResult,
    acceptedDraftRevision: ref(acceptedDraftRevision),
  })
}

interface ActiveDataTableCanvasOptions {
  graph: GraphState
  workflowId?: string
  selectedNodeIds?: string[]
  acceptedDraftRevision?: number | null
}

function registerActiveDataTableCanvas({
  graph,
  workflowId = DEFAULT_EXECUTION_CONTEXT.workflow_id,
  selectedNodeIds = [],
  acceptedDraftRevision = DEFAULT_EXECUTION_CONTEXT.draft_revision,
}: ActiveDataTableCanvasOptions) {
  const canvasId = canvasIdFromPanelId(`workflow:${encodeURIComponent(workflowId)}`)
  const descriptor = { kind: 'root' as const, canvasId, workflowId }
  const graphSync = useGraphSync({ descriptor, getWorkflowId: () => workflowId })
  graphSync.currentGraph.value = graph
  const projection = registerStatusProjection(
    canvasId,
    workflowId,
    graphSync,
    acceptedDraftRevision,
  )
  const uiStore = useUIStore()
  uiStore.setCanvasWorkflow(canvasId, workflowId, workflowId)
  uiStore.setCanvasSelectedNodes(canvasId, selectedNodeIds)
  canvasSessionRegistry.activate(canvasId)
  const dataTableStore = useDataTableStore()
  dataTableStore.registerCanvas(canvasId)
  return { canvasId, dataTableStore, graphSync, projection }
}

function applyExecutionStatus(
  nodeStatus: NodeStatus,
  context = DEFAULT_EXECUTION_CONTEXT,
): void {
  useExecutionStore().applyStatusSnapshot({
    type: 'status_snapshot',
    ...context,
    state: 'running',
    progress: null,
    last_result: null,
    node_statuses: { [nodeStatus.node_id]: nodeStatus },
  })
}

function filesGraph(nodeId = 'node-1'): GraphState {
  return {
    nodes: [{
      id: nodeId,
      name: 'Files 1',
      tool_name: 'files',
      position: [0, 0],
      parameters: {},
      resources: {},
      output_templates: {},
      enabled: true,
      collapsed: false,
    }],
    edges: [],
  }
}

describe('DataTablePanel', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    _resetGraphSyncForTest()
    _resetCanvasStatusProjectionForTest()
    vi.clearAllMocks()
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  it('clears canvas data when the projected status becomes unexecuted', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const canvasId = canvasIdFromPanelId('workflow:a')
    const descriptor = { kind: 'root' as const, canvasId, workflowId: 'a' }
    const graphSync = useGraphSync({ descriptor, getWorkflowId: () => 'a' })
    graphSync.syncGraphState({
      nodes: [{
        id: 'node-1',
        name: 'Files 1',
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
    graphSync.validationResult.value = {
      valid: true,
      errors: [],
      node_statuses: {
        'node-1': { node_id: 'node-1', status: 'executed', cached: false },
      },
    }
    const projection = useCanvasStatusProjection({
      descriptor,
      nodes: computed(() => graphSync.currentGraph.value.nodes.map(node => ({
        id: node.id,
        enabled: node.enabled !== false,
      }))),
      validationResult: graphSync.validationResult,
      acceptedDraftRevision: ref(7),
    })
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasId, 'a', 'Workflow A')
    ui.setCanvasSelectedNodes(canvasId, ['node-1'])
    canvasSessionRegistry.activate(canvasId)
    const store = useDataTableStore()
    vi.spyOn(store, 'fetchCanvasNodeData').mockResolvedValue(undefined)
    const clearCanvasCache = vi.spyOn(store, 'clearCanvasCache')
    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: { Button: true, NodeDataTable: true },
      },
    })
    await flushPromises()
    clearCanvasCache.mockClear()

    projection.markProvisional('node-1', {
      node_id: 'node-1',
      status: 'unexecuted',
      cached: false,
    })
    await nextTick()

    expect(clearCanvasCache).toHaveBeenCalledWith(canvasId, 'node-1')
    wrapper.unmount()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('shows a clear no-node-selected empty state instead of terminal data tables', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    registerActiveDataTableCanvas({
      selectedNodeIds: [],
      graph: {
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
      },
    })

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

  it('refreshes executed data when the Data Table tab becomes active after Logger', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { canvasId, projection } = registerActiveDataTableCanvas({
      selectedNodeIds: ['node-1'],
      graph: {
      nodes: [{
        id: 'node-1',
        name: 'Files 1',
        tool_name: 'files',
        position: [0, 0],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
      },
    })
    applyExecutionStatus({ node_id: 'node-1', status: 'executed', cached: false })
    expect(useExecutionStore().executionId).toBe(DEFAULT_EXECUTION_CONTEXT.execution_id)
    expect(useExecutionStore().originCanvasId).toBe(canvasId)
    expect(projection.statusForNode('node-1')).toMatchObject({
      source: 'execution',
      status: 'executed',
    })
    const fetchCanvasNodeData = vi
      .spyOn(useDataTableStore(), 'fetchCanvasNodeData')
      .mockResolvedValue(undefined)
    let activeChangeListener = (_event: { isActive: boolean }) => {}
    const dispose = vi.fn()
    const panelApi = {
      onDidActiveChange: vi.fn((listener: (event: { isActive: boolean }) => void) => {
        activeChangeListener = listener
        return { dispose }
      }),
    } as unknown as DockviewPanelApi

    const wrapper = mount(DataTablePanel, {
      props: { params: { api: panelApi } },
      global: {
        plugins: [pinia, PrimeVue],
        stubs: { Button: true, NodeDataTable: true },
      },
    })
    await flushPromises()
    fetchCanvasNodeData.mockClear()

    activeChangeListener({ isActive: false })
    await nextTick()
    expect(fetchCanvasNodeData).not.toHaveBeenCalled()

    activeChangeListener({ isActive: true })
    await nextTick()
    expect(fetchCanvasNodeData).toHaveBeenCalledOnce()
    expect(fetchCanvasNodeData).toHaveBeenCalledWith(canvasId, 'node-1', {
      toolName: 'files',
      workflowName: DEFAULT_EXECUTION_CONTEXT.workflow_id,
    })

    wrapper.unmount()
    expect(dispose).toHaveBeenCalledOnce()
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

  it('keeps a queued status refresh bound to the canvas that installed its watcher', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    const graphA = useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
      getWorkflowId: () => 'a',
    })
    const graphB = useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'b' },
      getWorkflowId: () => 'b',
    })
    const graph = {
      nodes: [{
        id: 'shared',
        name: 'Shared node',
        tool_name: 'files',
        position: [0, 0] as [number, number],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
    }
    graphA.syncGraphState(graph)
    graphB.syncGraphState(graph)
    registerStatusProjection(canvasA, 'a', graphA, 7)
    registerStatusProjection(canvasB, 'b', graphB, 7)
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
    ui.setCanvasSelectedNodes(canvasA, ['shared'])
    ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
    ui.setCanvasSelectedNodes(canvasB, ['shared'])
    const execution = useExecutionStore()
    graphSyncCanvasSessions.activate(canvasA)
    execution.applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-a',
      workflow_id: 'a',
      draft_revision: 7,
      state: 'running',
      progress: null,
      last_result: null,
      node_statuses: {
        shared: { node_id: 'shared', status: 'unexecuted', cached: false },
      },
    })
    const store = useDataTableStore()
    vi.spyOn(store, 'fetchNodeData').mockResolvedValue(undefined)
    const fetchCanvasNodeData = vi
      .spyOn(store, 'fetchCanvasNodeData')
      .mockResolvedValue(undefined)
    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: { Button: true, NodeDataTable: true },
      },
    })
    await flushPromises()
    fetchCanvasNodeData.mockClear()

    execution.applyNodeState({
      execution_id: 'exec-a',
      workflow_id: 'a',
      draft_revision: 7,
      node_id: 'shared',
      status: 'executed',
      cached: false,
    })
    graphSyncCanvasSessions.activate(canvasB)
    await nextTick()
    await flushPromises()

    expect(fetchCanvasNodeData).toHaveBeenCalledWith(canvasA, 'shared', {
      toolName: 'files',
      workflowName: 'a',
    })
    wrapper.unmount()
  })

  it('refreshes an executed canvas when it is reactivated after completion', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    const graphA = useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasA, workflowId: 'a' },
      getWorkflowId: () => 'a',
    })
    const graphB = useGraphSync({
      descriptor: { kind: 'root', canvasId: canvasB, workflowId: 'b' },
      getWorkflowId: () => 'b',
    })
    const graph = {
      nodes: [{
        id: 'shared',
        name: 'Shared node',
        tool_name: 'files',
        position: [0, 0] as [number, number],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
    }
    graphA.syncGraphState(graph)
    graphB.syncGraphState(graph)
    registerStatusProjection(canvasA, 'a', graphA, 7)
    registerStatusProjection(canvasB, 'b', graphB, 7)
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasA, 'a', 'Workflow A')
    ui.setCanvasSelectedNodes(canvasA, ['shared'])
    ui.setCanvasWorkflow(canvasB, 'b', 'Workflow B')
    ui.setCanvasSelectedNodes(canvasB, ['shared'])
    const store = useDataTableStore()
    store.registerCanvas(canvasA)
    canvasSessionRegistry.activate(canvasA)
    store.nodeDataCache.shared = {
      columns: ['path'],
      index: ['0'],
      rows: [{ path: '/stale.csv' }],
      absolute_rows: [0],
      total_rows: 1,
      page: 0,
      page_size: 50,
      column_types: { path: 'Path' },
    }
    useExecutionStore().applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-a',
      workflow_id: 'a',
      draft_revision: 7,
      state: 'running',
      progress: null,
      last_result: null,
      node_statuses: {
        shared: { node_id: 'shared', status: 'running', cached: false },
      },
    })
    canvasSessionRegistry.activate(canvasB)
    vi.spyOn(store, 'fetchNodeData').mockResolvedValue(undefined)
    const fetchCanvasNodeData = vi
      .spyOn(store, 'fetchCanvasNodeData')
      .mockResolvedValue(undefined)
    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: { Button: true, NodeDataTable: true },
      },
    })
    await flushPromises()
    fetchCanvasNodeData.mockClear()

    useExecutionStore().applyExecutionComplete({
      type: 'execution_complete',
      execution_id: 'exec-a',
      workflow_id: 'a',
      draft_revision: 7,
      success: true,
      errors: [],
      node_statuses: {
        shared: { node_id: 'shared', status: 'executed', cached: false },
      },
    })
    await nextTick()
    expect(fetchCanvasNodeData).not.toHaveBeenCalled()

    canvasSessionRegistry.activate(canvasA)
    await nextTick()
    await flushPromises()

    expect(fetchCanvasNodeData).toHaveBeenCalledOnce()
    expect(fetchCanvasNodeData).toHaveBeenCalledWith(canvasA, 'shared', {
      toolName: 'files',
      workflowName: 'a',
    })
    wrapper.unmount()
  })

  it('ignores status and result updates owned by another canvas', async () => {
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
        name: 'Shared node',
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
    ui.setCanvasSelectedNodes(canvasB, ['shared'])
    graphSyncCanvasSessions.activate(canvasA)
    const store = useDataTableStore()
    vi.spyOn(store, 'fetchNodeData').mockResolvedValue(undefined)
    const fetchCanvasNodeData = vi
      .spyOn(store, 'fetchCanvasNodeData')
      .mockResolvedValue(undefined)
    const clearCanvasCache = vi.spyOn(store, 'clearCanvasCache')
    const wrapper = mount(DataTablePanel, {
      global: {
        plugins: [pinia, PrimeVue],
        stubs: { Button: true, NodeDataTable: true },
      },
    })
    await flushPromises()
    fetchCanvasNodeData.mockClear()
    clearCanvasCache.mockClear()

    useExecutionStore().applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-b',
      workflow_id: 'b',
      draft_revision: 7,
      state: 'idle',
      progress: null,
      last_result: {
        success: true,
        errors: [],
        node_statuses: {
          shared: { node_id: 'shared', status: 'executed', cached: false },
        },
      },
      node_statuses: {
        shared: { node_id: 'shared', status: 'executed', cached: false },
      },
    })
    await nextTick()
    await flushPromises()

    expect(fetchCanvasNodeData).not.toHaveBeenCalled()
    expect(clearCanvasCache).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('does not render a delayed response from another canvas with the same node id', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    graphSyncCanvasSessions.register({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
    graphSyncCanvasSessions.register({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
    const store = useDataTableStore()
    let resolveA!: (value: { data: any }) => void
    const delayedA = new Promise<{ data: any }>((resolve) => {
      resolveA = resolve
    })
    mockedGet
      .mockReturnValueOnce(delayedA as any)
      .mockResolvedValueOnce({
        data: {
          columns: ['path'],
          index: ['0'],
          rows: [{ path: '/canvas-b.csv' }],
          absolute_rows: [0],
          total_rows: 1,
          page: 4,
          page_size: 50,
          column_types: { path: 'Path' },
        },
      })

    const fetchA = store.fetchCanvasNodeData(canvasA, 'shared', {
      page: 2,
      workflowName: 'a',
    })
    await store.fetchCanvasNodeData(canvasB, 'shared', {
      page: 4,
      workflowName: 'b',
    })
    graphSyncCanvasSessions.activate(canvasB)

    const getPageState = vi.spyOn(store, 'getPageState')
    const wrapper = mount(NodeDataTable, {
      props: { nodeId: 'shared', workflowName: 'b' },
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

    expect(wrapper.text()).toContain('/canvas-b.csv')
    expect(getPageState).toHaveBeenCalledWith('shared')

    resolveA({
      data: {
        columns: ['path'],
        index: ['0'],
        rows: [{ path: '/delayed-canvas-a.csv' }],
        absolute_rows: [0],
        total_rows: 1,
        page: 2,
        page_size: 50,
        column_types: { path: 'Path' },
      },
    })
    await fetchA
    await flushPromises()

    expect(wrapper.text()).toContain('/canvas-b.csv')
    expect(wrapper.text()).not.toContain('/delayed-canvas-a.csv')
    wrapper.unmount()
  })

  it('renders image path rows as thumbnail, path, Napari, reveal, copy only', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { dataTableStore } = registerActiveDataTableCanvas({
      graph: { nodes: [], edges: [] },
    })
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

  it('attempts silent thumbnails for regular path columns', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { dataTableStore } = registerActiveDataTableCanvas({
      graph: { nodes: [], edges: [] },
    })
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
    const fetchMock = vi.fn().mockRejectedValue(new Error('not an image'))
    vi.stubGlobal('fetch', fetchMock)

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

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/v1/nodes/node-1/thumbnail')
    expect(wrapper.text()).toContain('/data/results/measurements.csv')
    expect(wrapper.find('[data-testid="image-thumbnail"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="open-napari-0-csv_path"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="open-avivator-0-csv_path"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="reveal-0-csv_path"]').exists()).toBe(true)
    await wrapper.find('[data-testid="path-copy"]').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('/data/results/measurements.csv')
  })

  it('labels sub-workflow output table columns with published output names', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { dataTableStore } = registerActiveDataTableCanvas({
      selectedNodeIds: ['sub_1'],
      graph: {
        nodes: [{
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
        }],
        edges: [],
      },
    })
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
    registerActiveDataTableCanvas({
      selectedNodeIds: ['sub_workflow_1'],
      graph: {
        nodes: [{
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
        }],
        edges: [],
      },
    })

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
    const executionStore = useExecutionStore()
    registerActiveDataTableCanvas({
      selectedNodeIds: ['node-1'],
      graph: filesGraph(),
    })
    applyExecutionStatus({ node_id: 'node-1', status: 'unexecuted', cached: false })

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

    executionStore.applyNodeState({
      ...DEFAULT_EXECUTION_CONTEXT,
      node_id: 'node-1',
      status: 'executed',
      cached: false,
    })
    await flushPromises()

    expect(mockedGet).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('/tmp/out.csv')
    vi.useRealTimers()
  })

  it('retries a not-ready data response without showing the no-output empty state', async () => {
    vi.useFakeTimers()
    const pinia = createPinia()
    setActivePinia(pinia)
    registerActiveDataTableCanvas({
      selectedNodeIds: ['node-1'],
      graph: filesGraph(),
    })

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
    const executionStore = useExecutionStore()
    const { dataTableStore } = registerActiveDataTableCanvas({
      selectedNodeIds: ['node-1'],
      graph: filesGraph(),
    })
    applyExecutionStatus({ node_id: 'node-1', status: 'unexecuted', cached: false })
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

    executionStore.applyNodeState({
      ...DEFAULT_EXECUTION_CONTEXT,
      node_id: 'node-1',
      status: 'executed',
      cached: false,
    })
    await flushPromises()

    expect(mockedGet).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Preparing output data')
    expect(wrapper.text()).not.toContain('/tmp/stale-before-run.csv')
    vi.useRealTimers()
  })

  it('refreshes again on execution complete after the latest view is updated', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const executionStore = useExecutionStore()
    const { dataTableStore } = registerActiveDataTableCanvas({
      selectedNodeIds: ['node-1'],
      graph: filesGraph(),
    })
    applyExecutionStatus({ node_id: 'node-1', status: 'unexecuted', cached: false })
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
      ...DEFAULT_EXECUTION_CONTEXT,
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
      ...DEFAULT_EXECUTION_CONTEXT,
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
