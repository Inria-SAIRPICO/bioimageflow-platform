import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref, computed, nextTick, reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import InputText from 'primevue/inputtext'

// --- Mock shared state that matches the pattern in CanvasView.test.ts ---

let mockNodes: any[] = []
let mockEdges: any[] = []
let connectHandler: ((connection: any) => void) | null = null
let edgeUpdateHandler: ((event: any) => void) | null = null
let nodeDragStartHandler: ((event: any) => void) | null = null
let nodeDragStopHandler: ((event: any) => void) | null = null
const vueFlowMocks = vi.hoisted(() => ({ updateEdge: vi.fn() }))

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
      project: (pos: { x: number; y: number }) => pos,
      addNodes: (nodes: any[]) => {
        mockNodes.push(...nodes)
      },
      addEdges: (edges: any[]) => {
        mockEdges.push(...edges)
      },
      removeNodes: (ids: string[]) => {
        const idSet = new Set(ids)
        mockNodes = mockNodes.filter((n: any) => !idSet.has(n.id))
      },
      removeEdges: (ids: string[]) => {
        const idSet = new Set(ids)
        mockEdges = mockEdges.filter((e: any) => !idSet.has(e.id))
      },
      setNodes: (nodes: any[]) => {
        mockNodes = [...nodes]
      },
      setEdges: (edges: any[]) => {
        mockEdges = [...edges]
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

vi.mock('@vue-flow/background', () => ({
  Background: defineComponent({ name: 'Background', template: '<div />' }),
}))

vi.mock('@vue-flow/controls', () => ({
  Controls: defineComponent({ name: 'Controls', template: '<div />' }),
}))

vi.mock('@/composables/useGraphSync', () => ({
  serializeGraph: (raw: { nodes: any[]; edges: any[] }) => ({
    nodes: raw.nodes.map((node) => ({
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
  }),
  useGraphSync: () => ({
    syncGraph: vi.fn(),
    syncGraphState: vi.fn(),
    syncNodeParameters: vi.fn(),
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
import { _resetClipboardForTest, writeClipboardPayload } from '@/utils/clipboard'
import {
  _resetCanvasStatusProjectionForTest,
} from '@/composables/useCanvasStatusProjection'
import { canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { rootCanvasId, rootCanvasParams } from '@/test-utils/canvasFixtures'
import { primeVueTestGlobal } from '@/test-utils/mountFixtures'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
}

function mountCanvas() {
  return mount(CanvasView, {
    props: {
      nodes: [],
      edges: [],
      params: rootCanvasParams('execution-lock'),
    },
    attachTo: document.body,
  })
}

function projectedStatusesOf(wrapper: ReturnType<typeof mountCanvas>) {
  const exposed = (wrapper.vm as any).projectedStatuses
  return exposed?.value ?? exposed
}

describe('CanvasView execution lock', () => {
  beforeEach(() => {
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
        description: null,
        storage_path: '/tmp/workflows/untitled',
      },
    })
    mockNodes = []
    mockEdges = []
    connectHandler = null
    edgeUpdateHandler = null
    nodeDragStartHandler = null
    nodeDragStopHandler = null
    vueFlowMocks.updateEdge.mockClear()
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
      sourceHandle: 'out',
      targetHandle: 'in',
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

  it('rejects an edge update delivered after the stopping phase begins', async () => {
    const edge = {
      id: 'edge-1',
      source: 'a',
      target: 'b',
      sourceHandle: 'out',
      targetHandle: 'in',
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
        sourceHandle: 'out',
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
      clipboard_version: 2,
      nodes: [{
        id: 'a',
        name: 'A',
        tool_name: 'T',
        position: [0, 0],
        parameters: {},
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
      sourceHandle: 'out',
      targetHandle: 'in',
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
    exec.applyNodeState({ node_id: 'n1', status: 'running', cached: false })
    await nextTick()
    expect(projectedStatusesOf(w).n1.status).toBe('running')
    expect(mockNodes[0].data.status).toBe('unexecuted')

    exec.applyNodeState({ node_id: 'n1', status: 'executed', cached: false })
    await nextTick()
    expect(projectedStatusesOf(w).n1.status).toBe('executed')
    expect(mockNodes[0].data.status).toBe('unexecuted')
    w.unmount()
  })

  it('does not let idle execution statuses overwrite a provisional parameter edit', async () => {
    mockNodes = [
      {
        id: 'n1',
        data: { toolName: 'T', status: 'unexecuted', parameters: { value: 1 } },
      },
    ]
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.state = 'idle'
    exec.nodeStatuses = {
      n1: { node_id: 'n1', status: 'executed', cached: true },
    }
    expect(canvasCommandMocks.updateParameter?.('n1', 'value', 2)).toBe(true)
    await nextTick()

    expect(projectedStatusesOf(w).n1).toMatchObject({
      status: 'unexecuted',
      provisional: true,
    })
    expect(mockNodes[0].data.status).toBe('unexecuted')
    expect(mockNodes[0].data.provisional).toBeUndefined()
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
    useExecutionStore().nodeStatuses = {
      edited: { node_id: 'edited', status: 'executed', cached: false },
      untouched: { node_id: 'untouched', status: 'executed', cached: false },
    }
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
      provisional: true,
    })
    expect(projectedStatusesOf(canvas).untouched).toMatchObject({
      status: 'executed',
      provisional: true,
    })
    expect(mockNodes[0].data.status).toBe('executed')
    expect(mockNodes[0].data.provisional).toBeUndefined()
    expect(mockNodes[1].data.status).toBe('executed')
    expect(mockNodes[1].data.provisional).toBeUndefined()

    panel.unmount()
    canvas.unmount()
  })

  it('applies terminal statuses on the running-to-idle transition', async () => {
    mockNodes = [
      { id: 'n1', data: { toolName: 'T', status: 'running' } },
    ]
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.state = 'running'
    await nextTick()

    exec.applyExecutionComplete({
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

  it('keeps authoritative statuses while marking a graph edit provisional', async () => {
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
    useExecutionStore().nodeStatuses = {
      source: { node_id: 'source', status: 'executed', cached: false },
      target: { node_id: 'target', status: 'executed', cached: false },
    }
    expect(connectHandler).not.toBeNull()

    connectHandler!({
      source: 'source',
      target: 'target',
      sourceHandle: 'out',
      targetHandle: 'in',
    })
    await nextTick()

    expect(projectedStatusesOf(w).source).toMatchObject({
      status: 'executed',
      provisional: true,
    })
    expect(projectedStatusesOf(w).target).toMatchObject({
      status: 'executed',
      provisional: true,
    })
    expect(mockNodes[0].data.provisional).toBeUndefined()
    expect(mockNodes[1].data.provisional).toBeUndefined()
    w.unmount()
  })
})
