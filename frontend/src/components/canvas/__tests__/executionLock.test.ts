import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref, computed, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

// --- Mock shared state that matches the pattern in CanvasView.test.ts ---

let mockNodes: any[] = []
let mockEdges: any[] = []
let connectHandler: ((connection: any) => void) | null = null

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
      updateEdge: vi.fn(),
      getNodes: computed(() => mockNodes),
      getEdges: computed(() => mockEdges),
      onConnect: (handler: any) => {
        connectHandler = handler
      },
      onNodesChange: vi.fn(),
      onEdgeUpdate: vi.fn(),
      onEdgeUpdateEnd: vi.fn(),
      onNodeDragStart: vi.fn(),
      onNodeDragStop: vi.fn(),
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
    flushNow: vi.fn(),
    patchParameters: vi.fn(),
    loadWorkflow: vi.fn().mockResolvedValue(null),
    validationResult: ref(null),
    isPending: ref(false),
  }),
}))

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() },
}))

import CanvasView from '../CanvasView.vue'
import { api } from '@/api/client'
import { useExecutionStore } from '@/stores/execution'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
}

function mountCanvas() {
  return mount(CanvasView, {
    props: { nodes: [], edges: [] },
    attachTo: document.body,
  })
}

describe('CanvasView execution lock', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
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
  })

  it('onConnect is blocked when execution is running', async () => {
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.state = 'running'
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

  it('live executionStore.nodeStatuses propagates into node data', async () => {
    mockNodes = [
      { id: 'n1', data: { toolName: 'T', status: 'unexecuted' } },
    ]
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.applyNodeState({ node_id: 'n1', status: 'running', cached: false })
    await nextTick()
    expect(mockNodes[0].data.status).toBe('running')

    exec.applyNodeState({ node_id: 'n1', status: 'executed', cached: false })
    await nextTick()
    expect(mockNodes[0].data.status).toBe('executed')
    w.unmount()
  })
})
