import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref, computed, nextTick, reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import InputText from 'primevue/inputtext'

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
    syncGraphState: vi.fn(),
    syncNodeParameters: vi.fn(),
    flushNow: vi.fn(),
    dispose: vi.fn(),
    loadWorkflow: vi.fn().mockResolvedValue(null),
    validationResult: ref(null),
    isPending: ref(false),
  }),
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

  it('does not let idle execution statuses overwrite a provisional parameter edit', async () => {
    mockNodes = [
      {
        id: 'n1',
        data: { toolName: 'T', status: 'unexecuted', provisional: true },
      },
    ]
    const w = mountCanvas()
    const exec = useExecutionStore()
    exec.state = 'idle'
    exec.nodeStatuses = {
      n1: { node_id: 'n1', status: 'executed', cached: true },
    }
    await nextTick()

    expect(mockNodes[0].data.status).toBe('unexecuted')
    expect(mockNodes[0].data.provisional).toBe(true)
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
    const ui = useUIStore()
    ui.setGraphNodes(mockNodes)
    ui.setSelectedNodes(['edited'])
    const panel = mount(NodePanel, {
      global: {
        plugins: [[PrimeVue, { theme: { preset: Aura } }]],
      },
    })

    panel
      .find('[data-testid="path-input-path"]')
      .findComponent(InputText)
      .vm.$emit('update:modelValue', '/data/new')
    await nextTick()

    expect(mockNodes[0].data.status).toBe('unexecuted')
    expect(mockNodes[0].data.provisional).toBe(true)
    expect(mockNodes[1].data.status).toBe('executed')
    expect(mockNodes[1].data.provisional).toBe(true)

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

    expect(mockNodes[0].data.status).toBe('executed')
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
    expect(connectHandler).not.toBeNull()

    connectHandler!({
      source: 'source',
      target: 'target',
      sourceHandle: 'out',
      targetHandle: 'in',
    })
    await nextTick()

    expect(mockNodes[0].data.status).toBe('executed')
    expect(mockNodes[1].data.status).toBe('executed')
    expect(mockNodes[0].data.provisional).toBe(true)
    expect(mockNodes[1].data.provisional).toBe(true)
    w.unmount()
  })
})
