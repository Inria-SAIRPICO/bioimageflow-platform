import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref, computed, nextTick, reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import InputText from 'primevue/inputtext'
import { encodeEndpointHandle } from '@/utils/endpointHandles'

// --- Mock shared state that matches the pattern in CanvasView.test.ts ---

let mockNodes: any[] = []
let mockEdges: any[] = []
let connectHandler: ((connection: any) => void) | null = null
let edgeUpdateHandler: ((event: any) => void) | null = null
let nodeDragStartHandler: ((event: any) => void) | null = null
let nodeDragStopHandler: ((event: any) => void) | null = null
const vueFlowMocks = vi.hoisted(() => ({ updateEdge: vi.fn() }))
const graphSyncMocks = vi.hoisted(() => ({ syncGraphState: vi.fn() }))

vi.mock('@vue-flow/core', () => {
  const VueFlow = defineComponent({
    name: 'VueFlow',
    props: [
      'nodes',
      'edges',
      'nodeTypes',
      'edgeTypes',
      'isValidConnection',
      'selectionKeyCode',
      'fitViewOnInit',
      'edgesUpdatable',
      'nodesDraggable',
    ],
    template: '<div class="vue-flow-mock"><slot /></div>',
  })
  return {
    VueFlow,
    useVueFlow: () => ({
      dimensions: computed(() => ({ width: 800, height: 600 })),
      project: (pos: { x: number; y: number }) => pos,
      addNodes: (nodes: any[]) => {
        mockNodes.push(...nodes)
      },
      addEdges: (edges: any[]) => {
        mockEdges.push(...edges)
      },
      removeNodes: (ids: string[]) => {
        const idSet = new Set(ids)
        mockNodes.splice(
          0,
          mockNodes.length,
          ...mockNodes.filter((n: any) => !idSet.has(n.id)),
        )
      },
      removeEdges: (ids: string[]) => {
        const idSet = new Set(ids)
        mockEdges.splice(
          0,
          mockEdges.length,
          ...mockEdges.filter((e: any) => !idSet.has(e.id)),
        )
      },
      setNodes: (nodes: any[]) => {
        mockNodes.splice(0, mockNodes.length, ...nodes)
      },
      setEdges: (edges: any[]) => {
        mockEdges.splice(0, mockEdges.length, ...edges)
      },
      updateEdge: vueFlowMocks.updateEdge,
      getNodes: computed(() => mockNodes),
      getEdges: computed(() => mockEdges),
      onConnect: (handler: any) => {
        connectHandler = handler
      },
      onNodesChange: vi.fn(),
      onEdgeUpdate: (handler: any) => {
        edgeUpdateHandler = handler
      },
      onEdgeUpdateEnd: vi.fn(),
      onNodeDragStart: (handler: any) => {
        nodeDragStartHandler = handler
      },
      onNodeDragStop: (handler: any) => {
        nodeDragStopHandler = handler
      },
      fitView: vi.fn(),
    }),
    Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
  }
})

vi.mock('../CanvasBackground.vue', () => ({
  default: defineComponent({ name: 'Background', template: '<div />' }),
}))

vi.mock('@vue-flow/controls', () => ({
  Controls: defineComponent({ name: 'Controls', template: '<div />' }),
}))

vi.mock('@/composables/useGraphSync', () => ({
  serializeGraph: (raw: { nodes: any[]; edges: any[] }) => ({
    schema_version: 1,
    name: 'execution-lock',
    display_name: 'Execution lock',
    nodes: raw.nodes.map((node) => ({
      type: 'tool',
      id: node.id,
      name: node.data?.name ?? node.id,
      tool_name: node.data?.toolName ?? '',
      position: [node.position?.x ?? 0, node.position?.y ?? 0],
      parameters: node.data?.parameters ?? {},
      resources: node.data?.resources ?? {},
      output_templates: node.data?.output_templates ?? {},
      enabled: node.data?.enabled ?? true,
      collapsed: node.data?.collapsed ?? false,
    })),
    edges: [],
    interface: (raw as any).interface ?? { inputs: [], outputs: [] },
    config: {
      engine: 'wetlands',
      execution: 'parallel',
    },
  }),
  useGraphSync: () => ({
    syncGraph: vi.fn(),
    syncGraphState: graphSyncMocks.syncGraphState,
    flushNow: vi.fn(),
    dispose: vi.fn(),
    loadWorkflow: vi.fn().mockResolvedValue(null),
    validationResult: ref(null),
    isPending: ref(false),
  }),
}))

vi.mock('@/composables/useCanvasPersistence', () => ({
  useCanvasPersistence: () => ({
    queueGraph: vi.fn(),
    initializeFromDraft: vi.fn(),
    isPending: ref(false),
    acceptedDraftRevision: ref(7),
    dispose: vi.fn(),
  }),
}))

const canvasCommandMocks = vi.hoisted(() => ({
  updateParameter: null as null | ((nodeId: string, key: string, value: unknown) => boolean),
}))

vi.mock('@/composables/useCanvasCommands', () => ({
  useCanvasCommands: (options?: {
    updateParameter?: (nodeId: string, key: string, value: unknown) => boolean
  }) => {
    if (options?.updateParameter) {
      canvasCommandMocks.updateParameter = options.updateParameter
    }
    return {
      routeSave: vi.fn().mockResolvedValue('root'),
      updateParameter: (nodeId: string, key: string, value: unknown) => (
        canvasCommandMocks.updateParameter?.(nodeId, key, value) ?? false
      ),
      dispose: vi.fn(),
    }
  },
}))

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() },
}))

import CanvasView from '../CanvasView.vue'
import NodePanel from '@/components/panels/NodePanel.vue'
import { api } from '@/api/client'
import { useExecutionStore } from '@/stores/execution'
import { useUIStore } from '@/stores/ui'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { _resetClipboardForTest, writeClipboardPayload } from '@/utils/clipboard'
import {
  _resetCanvasStatusProjectionForTest,
} from '@/composables/useCanvasStatusProjection'
import { canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { rootCanvasId, rootCanvasParams } from '@/test-utils/canvasFixtures'
import { makeGraph, makeGraphNode } from '@/test-utils/graphFixtures'
import { primeVueTestGlobal } from '@/test-utils/mountFixtures'

const EXECUTION_CONTEXT = {
  execution_id: 'exec-lock',
  workflow_id: 'execution-lock',
  draft_revision: 7,
} as const

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
}

function mountCanvas(graph = makeGraph()) {
  const wrapper = mount(CanvasView, {
    props: {
      nodes: [],
      edges: [],
      params: rootCanvasParams('execution-lock', { graph }),
    },
    attachTo: document.body,
  })
  canvasSessionRegistry.activate(rootCanvasId('execution-lock'))
  return wrapper
}

function projectedStatusesOf(wrapper: ReturnType<typeof mountCanvas>) {
  const exposed = (wrapper.vm as any).projectedStatuses
  return exposed?.value ?? exposed
}

describe('CanvasView execution lock', () => {
  beforeEach(() => {
    delete window.pywebview
    canvasSessionRegistry.dispose()
    _resetCanvasStatusProjectionForTest()
    setActivePinia(createPinia())
    _resetClipboardForTest()
    mockedApi.get.mockResolvedValue({ data: [] })
    mockedApi.post.mockResolvedValue({
      data: {
        name: 'untitled',
        display_name: 'Untitled',
        path: '/tmp/untitled.json',
        last_modified: '2026-01-01T00:00:00Z',
      identity_generation: 0,
        description: null,
        results_path: '/tmp/workflows/untitled/results',
      },
    })
    mockNodes = []
    mockEdges = []
    connectHandler = null
    edgeUpdateHandler = null
    nodeDragStartHandler = null
    nodeDragStopHandler = null
    vueFlowMocks.updateEdge.mockClear()
    graphSyncMocks.syncGraphState.mockClear()
    canvasCommandMocks.updateParameter = null
  })

  it.each(['starting', 'stopping'] as const)(
    'onConnect is blocked when execution is %s',
    async (phase) => {
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.state = phase as any
    await nextTick()
    expect(connectHandler).not.toBeNull()
    connectHandler!({
      source: 'a',
      target: 'b',
      sourceHandle: encodeEndpointHandle({ kind: 'tool-output', name: 'out' }),
      targetHandle: encodeEndpointHandle({ kind: 'tool-input', name: 'in' }),
    })
    expect(mockEdges).toEqual([])
    w.unmount()
    },
  )

  it.each(['starting', 'running', 'stopping'] as const)(
    'disables Vue Flow mutation gestures while execution is %s',
    async (phase) => {
      const w = mountCanvas()
      useExecutionStore().state = phase
      await nextTick()
      const vueFlow = w.findComponent({ name: 'VueFlow' })

      expect(vueFlow.props('nodesDraggable')).toBe(false)
      expect(vueFlow.props('edgesUpdatable')).toBe(false)
      w.unmount()
    },
  )

  it('reverts a drag that crosses into the starting phase', async () => {
    const node = {
      id: 'a',
      position: { x: 0, y: 0 },
      data: { toolName: 'T' },
    }
    mockNodes = [node]
    const w = mountCanvas()
    nodeDragStartHandler!({ nodes: [node] })
    node.position = { x: 50, y: 75 }
    useExecutionStore().state = 'starting'
    await nextTick()

    nodeDragStopHandler!({ nodes: [node] })

    expect(node.position).toEqual({ x: 0, y: 0 })
    w.unmount()
  })

  it('restores every node through repeated movement undo and redo', async () => {
    const initialPositions = [
      [0, 0],
      [100, 20],
      [200, 40],
    ] as const
    const graph = makeGraph({
      nodes: initialPositions.map((position, index) => makeGraphNode({
        id: `node-${index + 1}`,
        name: `Node ${index + 1}`,
        tool_name: `Tool${index + 1}`,
        position: [...position],
      })),
    })
    const w = mountCanvas(graph)
    await flushPromises()
    await nextTick()

    for (let index = 0; index < initialPositions.length; index += 1) {
      const node = mockNodes[index]
      nodeDragStartHandler!({ nodes: [node] })
      node.position = {
        x: initialPositions[index][0] + 25,
        y: initialPositions[index][1] + 50,
      }
      nodeDragStopHandler!({ nodes: [node] })
    }

    for (let remaining = initialPositions.length; remaining > 0; remaining -= 1) {
      await w.find('.canvas-view').trigger('keydown', {
        key: 'z',
        ctrlKey: true,
      })
      await nextTick()

      expect(mockNodes.map(node => node.id)).toEqual([
        'node-1',
        'node-2',
        'node-3',
      ])
      for (let index = 0; index < initialPositions.length; index += 1) {
        const moved = index < remaining - 1
        expect(mockNodes[index].position).toEqual({
          x: initialPositions[index][0] + (moved ? 25 : 0),
          y: initialPositions[index][1] + (moved ? 50 : 0),
        })
      }
    }

    for (let restored = 1; restored <= initialPositions.length; restored += 1) {
      await w.find('.canvas-view').trigger('keydown', {
        key: 'Z',
        ctrlKey: true,
        shiftKey: true,
      })
      await nextTick()

      expect(mockNodes).toHaveLength(initialPositions.length)
      for (let index = 0; index < initialPositions.length; index += 1) {
        const moved = index < restored
        expect(mockNodes[index].position).toEqual({
          x: initialPositions[index][0] + (moved ? 25 : 0),
          y: initialPositions[index][1] + (moved ? 50 : 0),
        })
      }
    }
    w.unmount()
  })

  it('undoes and redoes deleting every node without corrupting the baseline', async () => {
    const graph = makeGraph({
      nodes: [
        makeGraphNode({ id: 'first', name: 'First', position: [10, 20] }),
        makeGraphNode({ id: 'second', name: 'Second', position: [30, 40] }),
      ],
    })
    const w = mountCanvas(graph)
    await flushPromises()
    await nextTick()

    for (const node of mockNodes) node.selected = true
    ;(w.vm as any).deleteSelected()
    expect(mockNodes).toEqual([])

    await w.find('.canvas-view').trigger('keydown', {
      key: 'z',
      ctrlKey: true,
    })
    await nextTick()
    expect(mockNodes.map(node => node.id)).toEqual(['first', 'second'])
    expect(mockNodes.map(node => node.position)).toEqual([
      { x: 10, y: 20 },
      { x: 30, y: 40 },
    ])

    await w.find('.canvas-view').trigger('keydown', {
      key: 'Z',
      ctrlKey: true,
      shiftKey: true,
    })
    await nextTick()
    expect(mockNodes).toEqual([])

    await w.find('.canvas-view').trigger('keydown', {
      key: 'z',
      ctrlKey: true,
    })
    await nextTick()
    expect(mockNodes.map(node => node.id)).toEqual(['first', 'second'])
    w.unmount()
  })

  it('removes workflow interface references in the same graph change as a node', async () => {
    const graph = makeGraph({
      nodes: [
        makeGraphNode({ id: 'increment', name: 'QaIncrement' }),
        makeGraphNode({ id: 'survivor', name: 'Survivor' }),
      ],
      interface: {
        inputs: [{
          id: 'shared-input',
          name: 'Shared input',
          kind: 'field',
          schema: { type: 'int' },
          default: null,
          targets: [
            { node: 'increment', port: { kind: 'field', name: 'value' } },
            { node: 'survivor', port: { kind: 'field', name: 'value' } },
          ],
        }],
        outputs: [{
          id: 'incremented-output',
          name: 'Incremented number',
          schema: { type: 'int' },
          source: { node: 'increment', column: 'number_plus_one' },
        }],
      },
    })
    const w = mountCanvas(graph)
    await flushPromises()
    await nextTick()
    graphSyncMocks.syncGraphState.mockClear()

    mockNodes.find(node => node.id === 'increment')!.selected = true
    ;(w.vm as any).deleteSelected()

    expect(graphSyncMocks.syncGraphState).toHaveBeenCalledOnce()
    expect(graphSyncMocks.syncGraphState).toHaveBeenCalledWith(expect.objectContaining({
      nodes: [expect.objectContaining({ id: 'survivor' })],
      interface: {
        inputs: [{
          ...graph.interface.inputs[0],
          targets: [graph.interface.inputs[0].targets[1]],
        }],
        outputs: [],
      },
    }))

    await w.find('.canvas-view').trigger('keydown', {
      key: 'z',
      ctrlKey: true,
    })
    await nextTick()
    expect(mockNodes.map(node => node.id)).toEqual(['increment', 'survivor'])
    expect(graphSyncMocks.syncGraphState).toHaveBeenLastCalledWith(expect.objectContaining({
      interface: graph.interface,
    }))
    w.unmount()
  })

  it('rejects an edge update delivered after the stopping phase begins', async () => {
    const edge = {
      id: 'edge-1',
      source: 'a',
      target: 'b',
      sourceHandle: encodeEndpointHandle({ kind: 'tool-output', name: 'out' }),
      targetHandle: encodeEndpointHandle({ kind: 'tool-input', name: 'in' }),
    }
    mockEdges = [edge]
    const w = mountCanvas()
    useExecutionStore().state = 'stopping'
    await nextTick()

    edgeUpdateHandler!({
      edge,
      connection: {
        source: 'a',
        target: 'c',
        sourceHandle: encodeEndpointHandle({ kind: 'tool-output', name: 'out' }),
        targetHandle: 'other',
      },
    })

    expect(vueFlowMocks.updateEdge).not.toHaveBeenCalled()
    w.unmount()
  })

  it('deleteSelected is blocked when locked', async () => {
    mockNodes = [
      { id: 'a', selected: true, data: { toolName: 'T' } },
    ]
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    const vm = w.vm as any
    vm.deleteSelected()
    expect(mockNodes).toHaveLength(1)
    w.unmount()
  })

  it('onAddNode is blocked when locked', async () => {
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    const vm = w.vm as any
    vm.onAddNode({ toolName: 'gaussian_blur', position: { x: 0, y: 0 } })
    expect(mockNodes).toEqual([])
    w.unmount()
  })

  it('creates tool nodes with both canonical and renderer discriminators', () => {
    useToolRegistryStore().tools = [{
      name: 'CrossJoin',
      display_name: 'Cross join',
      package: 'bioimageflow-common-tools',
      package_version: '1.0.0',
      tool_type: 'DataFrameTool',
      accepts_upstream: true,
      dynamic_outputs: true,
      dataframe_output: true,
      row_consumption: null,
      documentation: '',
      tags: [],
      categories: [],
      inputs: {},
      outputs: {},
      environment: null,
      source_kind: 'package',
      editable: false,
    }]
    const w = mountCanvas()

    const nodeId = (w.vm as any).onAddNode({
      toolName: 'CrossJoin',
      position: { x: 0, y: 0 },
    })

    const node = mockNodes.find(candidate => candidate.id === nodeId)
    expect(node).toMatchObject({
      type: 'tool',
      data: {
        nodeType: 'tool',
        toolName: 'CrossJoin',
      },
    })
    w.unmount()
  })

  it('creates a Files node from a desktop folder drop without uploading it', async () => {
    useToolRegistryStore().tools = [{
      name: 'Files',
      display_name: 'Files',
      package: 'bioimageflow-common-tools',
      package_version: '1.0.0',
      tool_type: 'DataFrameTool',
      accepts_upstream: false,
      dynamic_outputs: false,
      dataframe_output: true,
      row_consumption: null,
      documentation: '',
      tags: [],
      categories: [],
      inputs: {
        path: { type: 'path', default: null },
        files: { type: 'list', default: null },
      },
      outputs: {},
      environment: null,
      source_kind: 'package',
      editable: false,
    } as any]
    const resolveDroppedPaths = vi.fn().mockResolvedValue({
      path: '/data/images',
      files: null,
    })
    window.pywebview = {
      api: {
        resolve_dropped_paths: resolveDroppedPaths,
      } as any,
    }
    const folder = new File([], 'images')
    ;(folder as File & { path?: string }).path = '/data/images'
    const w = mountCanvas()

    await (w.vm as any).onDrop({
      preventDefault: vi.fn(),
      clientX: 20,
      clientY: 30,
      dataTransfer: {
        files: [folder],
        items: [],
        types: ['Files'],
        getData: vi.fn(() => ''),
      },
    })

    expect(resolveDroppedPaths).toHaveBeenCalledWith(['/data/images'])
    expect(mockNodes).toHaveLength(1)
    expect(mockNodes[0]).toMatchObject({
      data: {
        toolName: 'Files',
        parameters: {
          path: '/data/images',
          files: null,
        },
      },
    })
    w.unmount()
  })

  it('copySelected is a no-op when locked', async () => {
    mockNodes = [
      {
        id: 'a',
        selected: true,
        data: {
          name: 'A',
          toolName: 'T',
          parameters: {},
          connectedInputs: {},
        },
      },
    ]
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    const vm = w.vm as any
    vm.copySelected()
    expect(vm.clipboardData).toBeNull()
    w.unmount()
  })

  it('pasteFromClipboard is a no-op when locked', async () => {
    const w = mountCanvas()
    await writeClipboardPayload({
      bioimageflow_clipboard: true,
      clipboard_version: 1,
      created_at: '2026-07-20T00:00:00Z',
      nodes: [{
        type: 'tool',
        id: 'a',
        name: 'A',
        tool_name: 'T',
        position: [0, 0],
        parameters: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [],
    })
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    const vm = w.vm as any
    await vm.pasteFromClipboard()
    expect(mockNodes).toEqual([])
    w.unmount()
  })

  it('all interactions resume when execution completes', async () => {
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()
    exec.state = 'idle'
    await nextTick()

    expect(connectHandler).not.toBeNull()
    connectHandler!({
      source: 'a',
      target: 'b',
      sourceHandle: encodeEndpointHandle({ kind: 'tool-output', name: 'out' }),
      targetHandle: encodeEndpointHandle({ kind: 'tool-input', name: 'in' }),
    })
    expect(mockEdges.length).toBe(1)
    w.unmount()
  })

  it('projects live execution statuses without mutating node data', async () => {
    mockNodes = [
      { id: 'n1', data: { toolName: 'T', status: 'unexecuted' } },
    ]
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.applyNodeState({
      ...EXECUTION_CONTEXT,
      node_id: 'n1',
      status: 'running',
      cached: false,
    })
    await nextTick()
    expect(projectedStatusesOf(w).n1.status).toBe('running')
    expect(mockNodes[0].data.status).toBe('unexecuted')

    exec.applyNodeState({
      ...EXECUTION_CONTEXT,
      node_id: 'n1',
      status: 'executed',
      cached: false,
    })
    await nextTick()
    expect(projectedStatusesOf(w).n1.status).toBe('executed')
    expect(mockNodes[0].data.status).toBe('unexecuted')
    w.unmount()
  })

  it('does not let idle execution statuses overwrite a pending parameter edit', async () => {
    mockNodes = [
      {
        id: 'n1',
        data: { toolName: 'T', status: 'unexecuted', parameters: { value: 1 } },
      },
    ]
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.applyStatusSnapshot({
      ...EXECUTION_CONTEXT,
      state: 'idle',
      last_result: null,
      progress: null,
      node_statuses: {
        n1: { node_id: 'n1', status: 'executed', cached: true },
      },
    })
    expect(canvasCommandMocks.updateParameter?.('n1', 'value', 2)).toBe(true)
    await nextTick()

    expect(projectedStatusesOf(w).n1).toMatchObject({
      status: 'unexecuted',
      presentationStatus: 'executed',
      source: 'semantic',
    })
    expect(mockNodes[0].data.status).toBe('unexecuted')
    expect(mockNodes[0].data).not.toHaveProperty('provisional')
    w.unmount()
  })

  it('does not record or persist an unchanged parameter value', () => {
    mockNodes = [
      {
        id: 'n1',
        data: { toolName: 'T', status: 'unexecuted', parameters: { value: 7 } },
      },
    ]
    const w = mountCanvas()
    graphSyncMocks.syncGraphState.mockClear()

    expect(canvasCommandMocks.updateParameter?.('n1', 'value', 7)).toBe(false)
    expect(graphSyncMocks.syncGraphState).not.toHaveBeenCalled()
    expect(mockNodes[0].data.parameters).toEqual({ value: 7 })
    w.unmount()
  })

  it('keeps parameter-edit status invalidation scoped to the edited node', async () => {
    const tool = {
      name: 'files',
      display_name: 'Files',
      package: 'bioimageflow-core',
      package_version: '1.0.0',
      tool_type: 'ProcessingTool',
      accepts_upstream: false,
      dynamic_outputs: false,
      documentation: '',
      tags: [],
      categories: [],
      inputs: {
        path: {
          type: 'Path',
          required: true,
          nullable: false,
          connectable: 'never',
        },
      },
      outputs: {},
      environment: null,
    }
    mockNodes = reactive([
      {
        id: 'edited',
        data: {
          name: 'Edited',
          toolName: 'files',
          tool,
          status: 'executed',
          parameters: { path: '/data/old' },
          resources: {},
          output_templates: {},
          collapsed: false,
          enabled: true,
          connectedInputs: {},
          pinnedInputs: {},
        },
      },
      {
        id: 'untouched',
        data: {
          name: 'Untouched',
          toolName: 'files',
          tool,
          status: 'executed',
          parameters: { path: '/data/untouched' },
          resources: {},
          output_templates: {},
          collapsed: false,
          enabled: true,
          connectedInputs: {},
          pinnedInputs: {},
        },
      },
    ]) as any[]
    const canvas = mountCanvas()
    const canvasId = rootCanvasId('execution-lock')
    canvasSessionRegistry.activate(canvasId)
    useExecutionStore().applyStatusSnapshot({
      ...EXECUTION_CONTEXT,
      state: 'idle',
      last_result: null,
      progress: null,
      node_statuses: {
        edited: { node_id: 'edited', status: 'executed', cached: false },
        untouched: { node_id: 'untouched', status: 'executed', cached: false },
      },
    })
    const ui = useUIStore()
    ui.setCanvasGraphNodes(canvasId, mockNodes)
    ui.setCanvasSelectedNodes(canvasId, ['edited'])
    const panel = mount(NodePanel, {
      global: primeVueTestGlobal(),
    })

    panel
      .find('[data-testid="path-input-path"]')
      .findComponent(InputText)
      .vm.$emit('update:modelValue', '/data/new')
    await nextTick()

    expect(projectedStatusesOf(canvas).edited).toMatchObject({
      status: 'unexecuted',
      presentationStatus: 'executed',
      source: 'semantic',
    })
    expect(projectedStatusesOf(canvas).untouched).toMatchObject({
      status: 'executed',
      presentationStatus: 'executed',
      source: 'semantic',
    })
    expect(mockNodes[0].data.status).toBe('executed')
    expect(mockNodes[0].data).not.toHaveProperty('provisional')
    expect(mockNodes[1].data.status).toBe('executed')
    expect(mockNodes[1].data).not.toHaveProperty('provisional')

    panel.unmount()
    canvas.unmount()
  })

  it('applies terminal statuses on the running-to-idle transition', async () => {
    mockNodes = [
      { id: 'n1', data: { toolName: 'T', status: 'running' } },
    ]
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.applyNodeState({
      ...EXECUTION_CONTEXT,
      node_id: 'n1',
      status: 'running',
      cached: false,
    })
    await nextTick()

    exec.applyExecutionComplete({
      ...EXECUTION_CONTEXT,
      success: true,
      errors: [],
      node_statuses: {
        n1: { node_id: 'n1', status: 'executed', cached: false },
      },
    })
    await nextTick()

    expect(projectedStatusesOf(w).n1.status).toBe('executed')
    expect(mockNodes[0].data.status).toBe('running')
    w.unmount()
  })

  it('keeps authoritative presentation while staging a graph edit', async () => {
    mockNodes = [
      {
        id: 'source',
        data: {
          name: 'Source',
          toolName: 'SourceTool',
          status: 'executed',
          parameters: {},
          connectedInputs: {},
        },
      },
      {
        id: 'target',
        data: {
          name: 'Target',
          toolName: 'TargetTool',
          status: 'executed',
          parameters: { in: '/old' },
          connectedInputs: {},
        },
      },
    ]
    const w = mountCanvas()
    useExecutionStore().applyStatusSnapshot({
      ...EXECUTION_CONTEXT,
      state: 'idle',
      last_result: null,
      progress: null,
      node_statuses: {
        source: { node_id: 'source', status: 'executed', cached: false },
        target: { node_id: 'target', status: 'executed', cached: false },
      },
    })
    expect(connectHandler).not.toBeNull()

    connectHandler!({
      source: 'source',
      target: 'target',
      sourceHandle: encodeEndpointHandle({ kind: 'tool-output', name: 'out' }),
      targetHandle: encodeEndpointHandle({ kind: 'tool-input', name: 'in' }),
    })
    await nextTick()

    expect(projectedStatusesOf(w).source).toMatchObject({
      status: 'executed',
      presentationStatus: 'executed',
      source: 'semantic',
    })
    expect(projectedStatusesOf(w).target).toMatchObject({
      status: 'executed',
      presentationStatus: 'executed',
      source: 'semantic',
    })
    expect(mockNodes[0].data).not.toHaveProperty('provisional')
    expect(mockNodes[1].data).not.toHaveProperty('provisional')
    w.unmount()
  })
})
