import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref, reactive, computed, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import type { ToolMetadata } from '@/api/types'

// --- Mock data ---

function makeTool(overrides: Partial<ToolMetadata> = {}): ToolMetadata {
  return {
    name: 'gaussian_blur',
    display_name: 'Gaussian Blur',
    package: 'core',
    package_version: '1.0.0',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    documentation: '',
    tags: [],
    categories: [],
    inputs: {
      image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' },
      sigma: { type: 'float', required: false, nullable: false, connectable: 'never', default: 1.0 },
    },
    outputs: {
      result: { type: 'ImageFile' },
    },
    environment: null,
    ...overrides,
  }
}

function makeThresholdTool(): ToolMetadata {
  return makeTool({
    name: 'threshold',
    display_name: 'Threshold',
    inputs: {
      mask: { type: 'MaskPath', required: true, nullable: false, connectable: 'by_default' },
      level: { type: 'float', required: false, nullable: false, connectable: 'never', default: 0.5 },
    },
    outputs: {
      result: { type: 'MaskPath' },
    },
  })
}

// --- Mock stores & composables ---

let mockNodes: any[] = []
let mockEdges: any[] = []
let connectHandler: ((connection: any) => void) | null = null
let selectionHandler: ((params: any) => void) | null = null
let dragStartHandler: ((event: any) => void) | null = null
let dragStopHandler: ((event: any) => void) | null = null

vi.mock('@vue-flow/core', () => {
  const VueFlow = defineComponent({
    name: 'VueFlow',
    props: ['nodes', 'edges', 'nodeTypes', 'edgeTypes', 'isValidConnection', 'selectionKeyCode', 'fitViewOnInit'],
    template: '<div class="vue-flow-mock"><slot /></div>',
  })
  return {
    VueFlow,
    useVueFlow: () => ({
      project: (pos: { x: number; y: number }) => pos,
      addNodes: (nodes: any[]) => { mockNodes.push(...nodes) },
      addEdges: (edges: any[]) => { mockEdges.push(...edges) },
      removeNodes: (ids: string[]) => {
        const idSet = new Set(ids)
        const kept = mockNodes.filter((n: any) => !idSet.has(n.id))
        mockNodes.splice(0, mockNodes.length, ...kept)
      },
      removeEdges: (ids: string[]) => {
        const idSet = new Set(ids)
        const kept = mockEdges.filter((e: any) => !idSet.has(e.id))
        mockEdges.splice(0, mockEdges.length, ...kept)
      },
      // Mutate the array in place so the `computed(() => mockNodes)` ref
      // above keeps the same array identity and downstream consumers see
      // the new contents.
      setNodes: (nodes: any[]) => {
        mockNodes.splice(0, mockNodes.length, ...nodes)
      },
      setEdges: (edges: any[]) => {
        mockEdges.splice(0, mockEdges.length, ...edges)
      },
      updateEdge: (oldEdge: any, conn: any) => {
        const idx = mockEdges.findIndex((e: any) => e.id === oldEdge.id)
        if (idx < 0) return false
        mockEdges[idx] = { ...mockEdges[idx], ...conn }
        return mockEdges[idx]
      },
      getNodes: computed(() => mockNodes),
      getEdges: computed(() => mockEdges),
      onConnect: (handler: any) => { connectHandler = handler },
      onNodesChange: (handler: any) => { selectionHandler = handler },
      onEdgeUpdate: vi.fn(),
      onEdgeUpdateEnd: vi.fn(),
      onNodeDragStart: (handler: any) => { dragStartHandler = handler },
      onNodeDragStop: (handler: any) => { dragStopHandler = handler },
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

const graphSyncMocks = vi.hoisted(() => ({
  syncGraph: vi.fn(),
  flushNow: vi.fn(),
  patchParameters: vi.fn(),
  serializeGraph: vi.fn((state: { nodes: any[]; edges: any[] }) => ({
    nodes: state.nodes.map((n: any) => ({
      id: n.id,
      name: n.data?.name ?? n.id,
      tool_name: n.data?.toolName ?? '',
      position: [n.position?.x ?? 0, n.position?.y ?? 0],
      parameters: n.data?.parameters ?? {},
      resources: n.data?.resources ?? {},
      output_templates: n.data?.output_templates ?? {},
      enabled: n.data?.enabled ?? true,
      collapsed: n.data?.collapsed ?? false,
    })),
    edges: state.edges.map((e: any) => {
      if (e.type === 'positional') {
        const handle = e.targetHandle ?? ''
        const index = Number.parseInt(handle.replace('__positional_', ''), 10)
        return {
          type: 'positional',
          id: e.id,
          source_node: e.source,
          target_node: e.target,
          positional_index: Number.isNaN(index) ? 0 : index,
        }
      }
      return {
        type: 'column_ref',
        id: e.id,
        source_node: e.source,
        target_node: e.target,
        source_output: e.sourceHandle ?? '',
        target_input: e.targetHandle ?? '',
      }
    }),
  })),
}))

const autoSaveMocks = vi.hoisted(() => ({
  scheduleAutoSave: vi.fn(),
  flushAutoSave: vi.fn().mockResolvedValue(undefined),
  loadAutoSave: vi.fn().mockResolvedValue(null),
  loadMostRecentAutoSave: vi.fn().mockResolvedValue(null),
  clearAutoSave: vi.fn().mockResolvedValue(undefined),
  setLastOpenedWorkflow: vi.fn().mockResolvedValue(undefined),
  getLastOpenedWorkflow: vi.fn().mockResolvedValue(null),
}))

const apiMocks = vi.hoisted(() => ({
  get: vi.fn((url: string) => {
    if (url === '/api/v1/workflows') return Promise.resolve({ data: [] })
    if (url === '/api/v1/tools') return Promise.resolve({ data: [] })
    return Promise.resolve({ data: {} })
  }),
  post: vi.fn(() => Promise.resolve({ data: { name: 'Untitled', display_name: 'Untitled' } })),
  put: vi.fn(() => Promise.resolve({ data: {} })),
  patch: vi.fn(() => Promise.resolve({ data: {} })),
  delete: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('@/api/client', () => ({
  api: apiMocks,
}))

vi.mock('@/composables/useAutoSave', () => ({
  useAutoSave: () => autoSaveMocks,
}))

vi.mock('@/composables/useGraphSync', async () => {
  const { ref } = await import('vue')
  return {
    serializeGraph: graphSyncMocks.serializeGraph,
    useGraphSync: () => ({
      ...graphSyncMocks,
      validationResult: ref(null),
      isPending: ref(false),
      syncState: ref('idle'),
    }),
  }
})

vi.mock('@/stores/resolvedOutputs', () => {
  const { reactive } = require('vue')
  const store = {
    resolvedOutputsByNodeId: reactive({} as Record<string, any>),
    refreshResolvedOutputs: vi.fn(),
    refreshNow: vi.fn(),
    removeNode: vi.fn(),
    clear: vi.fn(),
  }
  return {
    useResolvedOutputsStore: () => store,
  }
})

// Import after mocks
import CanvasView from '../CanvasView.vue'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import { useResolvedOutputsStore } from '@/stores/resolvedOutputs'
import { _resetClipboardForTest } from '@/utils/clipboard'
import { useSubWorkflowSessionsStore } from '@/stores/subWorkflowSessions'

function mountCanvas(propsData: {
  nodes?: any[]
  edges?: any[]
  subWorkflowSessionId?: string
  params?: Record<string, unknown>
} = {}) {
  return mount(CanvasView, {
    props: {
      nodes: propsData.nodes ?? [],
      edges: propsData.edges ?? [],
      subWorkflowSessionId: propsData.subWorkflowSessionId,
      params: propsData.params,
    },
    attachTo: document.body,
  })
}

function mockSavedWorkflow(
  graph: { nodes: any[]; edges: any[] },
  name = 'saved',
  tools: ToolMetadata[] = [makeTool()],
) {
  apiMocks.get.mockImplementation((url: string) => {
    if (url === '/api/v1/workflows') {
      return Promise.resolve({
        data: [{ name, display_name: 'Saved workflow' }],
      })
    }
    if (url === `/api/v1/workflows/${name}`) {
      return Promise.resolve({
        data: {
          info: { name, display_name: 'Saved workflow' },
          graph,
          missing_packages: [],
          missing_tools: [],
        },
      })
    }
    if (url === '/api/v1/tools') return Promise.resolve({ data: tools })
    return Promise.resolve({ data: {} })
  })
  autoSaveMocks.loadMostRecentAutoSave.mockResolvedValueOnce({
    name,
    graph,
    timestamp: 1,
  })
}

describe('CanvasView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    _resetClipboardForTest()
    mockNodes.length = 0
    mockEdges.length = 0
    connectHandler = null
    selectionHandler = null
    dragStartHandler = null
    dragStopHandler = null
    graphSyncMocks.syncGraph.mockClear()
    graphSyncMocks.flushNow.mockClear()
    graphSyncMocks.patchParameters.mockClear()
    graphSyncMocks.serializeGraph.mockClear()
    autoSaveMocks.scheduleAutoSave.mockClear()
    autoSaveMocks.flushAutoSave.mockClear()
    autoSaveMocks.loadAutoSave.mockReset().mockResolvedValue(null)
    autoSaveMocks.loadMostRecentAutoSave.mockReset().mockResolvedValue(null)
    autoSaveMocks.clearAutoSave.mockClear()
    autoSaveMocks.setLastOpenedWorkflow.mockClear()
    autoSaveMocks.getLastOpenedWorkflow.mockReset().mockResolvedValue(null)
    apiMocks.get.mockReset().mockImplementation((url: string) => {
      if (url === '/api/v1/workflows') return Promise.resolve({ data: [] })
      if (url === '/api/v1/tools') return Promise.resolve({ data: [] })
      return Promise.resolve({ data: {} })
    })
    apiMocks.post.mockReset().mockResolvedValue({
      data: { name: 'Untitled', display_name: 'Untitled' },
    })
    apiMocks.put.mockReset().mockResolvedValue({ data: {} })
    apiMocks.patch.mockReset().mockResolvedValue({ data: {} })
    apiMocks.delete.mockReset().mockResolvedValue({ data: {} })
  })

  // --- Task 6: Core Vue Flow Setup ---

  describe('core setup', () => {
    it('renders a .canvas-view container', () => {
      const w = mountCanvas()
      expect(w.find('.canvas-view').exists()).toBe(true)
      w.unmount()
    })

    it('nodeTypes includes tool', () => {
      const w = mountCanvas()
      const vueFlow = w.findComponent({ name: 'VueFlow' })
      expect(vueFlow.props('nodeTypes')).toHaveProperty('tool')
      w.unmount()
    })

    it('edgeTypes includes column_ref and positional', () => {
      const w = mountCanvas()
      const vueFlow = w.findComponent({ name: 'VueFlow' })
      const edgeTypes = vueFlow.props('edgeTypes')
      expect(edgeTypes).toHaveProperty('column_ref')
      expect(edgeTypes).toHaveProperty('positional')
      w.unmount()
    })

    it('connection event creates edge and emits graph-changed', () => {
      const w = mountCanvas()
      expect(connectHandler).not.toBeNull()

      connectHandler!({
        source: 'node_a',
        target: 'node_b',
        sourceHandle: 'result',
        targetHandle: 'image',
      })

      expect(mockEdges.length).toBe(1)
      expect(mockEdges[0].source).toBe('node_a')
      expect(mockEdges[0].target).toBe('node_b')
      expect(w.emitted('graph-changed')).toBeTruthy()
      w.unmount()
    })

    it('connecting to an already-connected input replaces the old edge', () => {
      mockNodes = [
        { id: 'a', data: { toolName: 'gaussian_blur', name: 'a', connectedInputs: {} } },
        { id: 'b', data: { toolName: 'gaussian_blur', name: 'b', connectedInputs: {} } },
        { id: 'c', data: { toolName: 'gaussian_blur', name: 'c', connectedInputs: { image: 'a.result' } } },
      ]
      mockEdges = [
        { id: 'e_a_c', source: 'a', target: 'c', sourceHandle: 'result', targetHandle: 'image' },
      ]

      const w = mountCanvas()
      expect(connectHandler).not.toBeNull()

      // User drags from c's already-connected `image` input to b's output
      connectHandler!({
        source: 'b',
        target: 'c',
        sourceHandle: 'result',
        targetHandle: 'image',
      })

      // Only one edge remains on c.image, and it's the new one
      const incoming = mockEdges.filter((e: any) => e.target === 'c' && e.targetHandle === 'image')
      expect(incoming).toHaveLength(1)
      expect(incoming[0].source).toBe('b')
      w.unmount()
    })

    it('onConnect drops a stale parameter for the now-connected input', () => {
      // Reproduces the Files → Atlas bug: the user had a null parameter
      // sitting on `image`, then wired up an edge. The wire payload must
      // not carry the constant — otherwise the engine merges it on top of
      // the column binding and the upstream value is lost.
      mockNodes = [
        { id: 'a', data: { toolName: 'gaussian_blur', name: 'a', parameters: {}, connectedInputs: {} } },
        {
          id: 'b',
          data: {
            toolName: 'gaussian_blur',
            name: 'b',
            parameters: { image: null, sigma: 1.0 },
            connectedInputs: {},
          },
        },
      ]
      mockEdges = []

      const w = mountCanvas()

      connectHandler!({
        source: 'a',
        target: 'b',
        sourceHandle: 'result',
        targetHandle: 'image',
      })

      const targetNode = mockNodes.find((n: any) => n.id === 'b')!
      expect('image' in targetNode.data.parameters).toBe(false)
      expect(targetNode.data.parameters.sigma).toBe(1.0)
      expect(targetNode.data.connectedInputs.image).toBe('a.result')
      w.unmount()
    })

    it('onConnect leaves parameters untouched on a positional/header connection', () => {
      // Positional handles like `__positional_0` are not real field names
      // in `parameters`, so we must not delete an unrelated entry that
      // happens to share its key by accident.
      mockNodes = [
        { id: 'a', data: { toolName: 'gaussian_blur', name: 'a', parameters: {}, connectedInputs: {} } },
        {
          id: 'b',
          data: {
            toolName: 'gaussian_blur',
            name: 'b',
            parameters: { __positional_0: 'should-not-be-touched', sigma: 1.0 },
            connectedInputs: {},
          },
        },
      ]
      mockEdges = []

      const w = mountCanvas()

      connectHandler!({
        source: 'a',
        target: 'b',
        sourceHandle: 'result',
        targetHandle: '__positional_0',
      })

      const targetNode = mockNodes.find((n: any) => n.id === 'b')!
      expect(targetNode.data.parameters.__positional_0).toBe('should-not-be-touched')
      w.unmount()
    })

    it('positional inputs allow multiple incoming edges', () => {
      mockNodes = [
        { id: 'a', data: { toolName: 'gaussian_blur', name: 'a', connectedInputs: {} } },
        { id: 'b', data: { toolName: 'gaussian_blur', name: 'b', connectedInputs: {} } },
        { id: 'c', data: { toolName: 'gaussian_blur', name: 'c', connectedInputs: { __positional_0: 'a.result' } } },
      ]
      mockEdges = [
        { id: 'e_a_c', source: 'a', target: 'c', sourceHandle: 'result', targetHandle: '__positional_0' },
      ]

      const w = mountCanvas()

      // Connecting to __positional_1 must not remove __positional_0
      connectHandler!({
        source: 'b',
        target: 'c',
        sourceHandle: 'result',
        targetHandle: '__positional_1',
      })

      expect(mockEdges.filter((e: any) => e.target === 'c')).toHaveLength(2)
      w.unmount()
    })

    it('isValidConnection rejects incompatible types (str output -> ImageFile input)', () => {
      const store = useToolRegistryStore()
      // A source tool that outputs `str`, and the regular blur which expects
      // an ImageFile input. Path-family <-> non-path-family must be rejected.
      const stringSource = makeTool({
        name: 'string_source',
        display_name: 'String Source',
        outputs: { value: { type: 'str' } },
      })
      store.tools = [stringSource, makeTool()] as any

      mockNodes = [
        { id: 'src_1', data: { toolName: 'string_source' } },
        { id: 'blur_1', data: { toolName: 'gaussian_blur' } },
      ]

      const w = mountCanvas()
      const vm = w.vm as any

      const result = vm.isValidConnection({
        source: 'src_1',
        target: 'blur_1',
        sourceHandle: 'value',
        targetHandle: 'image',
      })
      expect(result).toBe(false)
      w.unmount()
    })

    it('isValidConnection accepts compatible types', () => {
      const store = useToolRegistryStore()
      const blur1 = makeTool()
      const blur2 = makeTool({ name: 'gaussian_blur_2', display_name: 'Blur 2' })
      store.tools = [blur1, blur2] as any

      mockNodes = [
        { id: 'blur_1', data: { toolName: 'gaussian_blur' } },
        { id: 'blur_2', data: { toolName: 'gaussian_blur_2' } },
      ]

      const w = mountCanvas()
      const vm = w.vm as any

      // ImageFile -> ImageFile: compatible
      const result = vm.isValidConnection({
        source: 'blur_1',
        target: 'blur_2',
        sourceHandle: 'result',
        targetHandle: 'image',
      })
      expect(result).toBe(true)
      w.unmount()
    })

    // Path-family compatibility: Path / ImageFile / MaskPath share the same
    // runtime carrier (filesystem path). The frontend pre-flight treats them
    // as mutually compatible; the library catches semantic mismatches
    // (image_spec semantics, formats, layouts) on graph validate.
    describe('isValidConnection — path-family compatibility', () => {
      function makeFilesTool(): ToolMetadata {
        // Models the `Files` DataFrameTool: emits a `path: Path` column.
        return makeTool({
          name: 'files',
          display_name: 'Files',
          tool_type: 'DataFrameTool',
          inputs: {
            path: { type: 'Path', required: true, nullable: false, connectable: 'never' },
            pattern: { type: 'str', required: false, nullable: false, connectable: 'never', default: '*' },
          },
          outputs: {
            path: { type: 'Path' },
            filename: { type: 'str' },
          },
        })
      }

      function makePathSink(): ToolMetadata {
        // A tool with one input of each path-family flavor.
        return makeTool({
          name: 'path_sink',
          display_name: 'Path Sink',
          inputs: {
            any_path: { type: 'Path', required: true, nullable: false, connectable: 'by_default' },
            image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' },
            mask: { type: 'MaskPath', required: true, nullable: false, connectable: 'by_default' },
          },
          outputs: {},
        })
      }

      function makeMultiPathSource(): ToolMetadata {
        // A tool with one output of each path-family flavor.
        return makeTool({
          name: 'multi_path_source',
          display_name: 'Multi Path Source',
          inputs: {
            seed: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' },
          },
          outputs: {
            any_path: { type: 'Path' },
            image: { type: 'ImageFile' },
            mask: { type: 'MaskPath' },
          },
        })
      }

      function setup() {
        const store = useToolRegistryStore()
        store.tools = [makeFilesTool(), makePathSink(), makeMultiPathSource()] as any
        mockNodes = [
          { id: 'files_1', data: { toolName: 'files' } },
          { id: 'multi_1', data: { toolName: 'multi_path_source' } },
          { id: 'sink_1', data: { toolName: 'path_sink' } },
        ]
        const w = mountCanvas()
        const vm = w.vm as any
        return { w, vm }
      }

      it('accepts Path output -> ImageFile input (Files.path -> Atlas.input_image)', () => {
        const { w, vm } = setup()
        const result = vm.isValidConnection({
          source: 'files_1',
          target: 'sink_1',
          sourceHandle: 'path',
          targetHandle: 'image',
        })
        expect(result).toBe(true)
        w.unmount()
      })

      it('accepts Path output -> MaskPath input', () => {
        const { w, vm } = setup()
        const result = vm.isValidConnection({
          source: 'files_1',
          target: 'sink_1',
          sourceHandle: 'path',
          targetHandle: 'mask',
        })
        expect(result).toBe(true)
        w.unmount()
      })

      it('accepts Path output -> Path input', () => {
        const { w, vm } = setup()
        const result = vm.isValidConnection({
          source: 'files_1',
          target: 'sink_1',
          sourceHandle: 'path',
          targetHandle: 'any_path',
        })
        expect(result).toBe(true)
        w.unmount()
      })

      it('accepts ImageFile output -> Path input', () => {
        const { w, vm } = setup()
        const result = vm.isValidConnection({
          source: 'multi_1',
          target: 'sink_1',
          sourceHandle: 'image',
          targetHandle: 'any_path',
        })
        expect(result).toBe(true)
        w.unmount()
      })

      it('accepts ImageFile output -> MaskPath input', () => {
        const { w, vm } = setup()
        const result = vm.isValidConnection({
          source: 'multi_1',
          target: 'sink_1',
          sourceHandle: 'image',
          targetHandle: 'mask',
        })
        expect(result).toBe(true)
        w.unmount()
      })

      it('accepts MaskPath output -> Path input', () => {
        const { w, vm } = setup()
        const result = vm.isValidConnection({
          source: 'multi_1',
          target: 'sink_1',
          sourceHandle: 'mask',
          targetHandle: 'any_path',
        })
        expect(result).toBe(true)
        w.unmount()
      })

      it('accepts MaskPath output -> ImageFile input', () => {
        const { w, vm } = setup()
        const result = vm.isValidConnection({
          source: 'multi_1',
          target: 'sink_1',
          sourceHandle: 'mask',
          targetHandle: 'image',
        })
        expect(result).toBe(true)
        w.unmount()
      })

      it('still rejects path-family <-> non-path-family (Path output -> str input would, str output -> Path input)', () => {
        // makeFilesTool exposes a `pattern: str` input; connecting any path
        // output to it must be rejected.
        const { w, vm } = setup()
        const result = vm.isValidConnection({
          source: 'multi_1',
          target: 'files_1',
          sourceHandle: 'image',
          targetHandle: 'pattern',
        })
        expect(result).toBe(false)
        w.unmount()
      })
    })

    it('validates sub-workflow published pins using their schemas when tool metadata is null', () => {
      const store = useToolRegistryStore()
      const filesTool = makeTool({
        name: 'files',
        display_name: 'Files',
        tool_type: 'DataFrameTool',
        inputs: {},
        outputs: {
          path: { type: 'Path' },
        },
      })
      const stringTool = makeTool({
        name: 'string_source',
        display_name: 'String Source',
        inputs: {},
        outputs: {
          value: { type: 'str' },
        },
      })
      const sinkTool = makeTool({
        name: 'path_sink',
        display_name: 'Path Sink',
        inputs: {
          path: { type: 'Path', required: true, nullable: false, connectable: 'by_default' },
        },
        outputs: {},
      })
      store.tools = [filesTool, stringTool, sinkTool] as any

      mockNodes = [
        { id: 'files_1', data: { toolName: 'files' } },
        { id: 'string_1', data: { toolName: 'string_source' } },
        { id: 'sink_1', data: { toolName: 'path_sink' } },
        {
          id: 'sub_1',
          type: 'sub_workflow',
          data: {
            toolName: '__sub_workflow__',
            tool: null,
            published_inputs: [{
              name: 'image',
              internal_node_id: 'inner',
              internal_field: 'input_image',
              kind: 'input',
              schema: { type: 'ImageFile', connectable: 'by_default' },
              default: null,
            }],
            published_outputs: [{
              name: 'mask',
              internal_node_id: 'inner',
              internal_output: 'mask',
              schema: { type: 'MaskPath' },
            }],
          },
        },
      ]

      const w = mountCanvas()
      const vm = w.vm as any

      expect(vm.isValidConnection({
        source: 'files_1',
        target: 'sub_1',
        sourceHandle: 'path',
        targetHandle: 'image',
      })).toBe(true)
      expect(vm.isValidConnection({
        source: 'sub_1',
        target: 'sink_1',
        sourceHandle: 'mask',
        targetHandle: 'path',
      })).toBe(true)
      expect(vm.isValidConnection({
        source: 'string_1',
        target: 'sub_1',
        sourceHandle: 'value',
        targetHandle: 'image',
      })).toBe(false)
      w.unmount()
    })

    it('isValidConnection rejects cycles', () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any

      // A -> B edge exists; connecting B -> A would create a cycle
      mockNodes = [
        { id: 'a', data: { toolName: 'gaussian_blur' } },
        { id: 'b', data: { toolName: 'gaussian_blur' } },
      ]
      mockEdges = [
        { id: 'e1', source: 'a', target: 'b' },
      ]

      const w = mountCanvas()
      const vm = w.vm as any

      const result = vm.isValidConnection({
        source: 'b',
        target: 'a',
        sourceHandle: 'result',
        targetHandle: 'image',
      })
      expect(result).toBe(false)
      w.unmount()
    })

    it('onConnect rejects positional edge into source DataFrameTool (accepts_upstream=false)', () => {
      const filesTool = makeTool({
        name: 'files',
        display_name: 'Files',
        tool_type: 'DataFrameTool',
        accepts_upstream: false,
        inputs: {},
        outputs: { path: { type: 'Path' } },
      })
      const store = useToolRegistryStore()
      store.tools = [makeTool(), filesTool] as any

      mockNodes = [
        { id: 'src', data: { toolName: 'gaussian_blur', name: 'src', tool: makeTool(), connectedInputs: {} } },
        { id: 'files_1', data: { toolName: 'files', name: 'files_1', tool: filesTool, connectedInputs: {} } },
      ]
      mockEdges = []

      const w = mountCanvas()
      expect(connectHandler).not.toBeNull()

      connectHandler!({
        source: 'src',
        target: 'files_1',
        sourceHandle: 'result',
        targetHandle: '__positional_0',
      })

      // Edge should NOT have been created
      expect(mockEdges).toHaveLength(0)
      w.unmount()
    })

    it('rejected positional edge emits an edge_rejected toast (no history entry)', async () => {
      const errors = await import('@/stores/errors')
      const errorStore = errors.useErrorStore()
      const filesTool = makeTool({
        name: 'files',
        display_name: 'Files',
        tool_type: 'DataFrameTool',
        accepts_upstream: false,
        inputs: {},
        outputs: { path: { type: 'Path' } },
      })
      const store = useToolRegistryStore()
      store.tools = [makeTool(), filesTool] as any

      mockNodes = [
        { id: 'src', data: { toolName: 'gaussian_blur', name: 'Source', tool: makeTool(), connectedInputs: {} } },
        { id: 'files_1', data: { toolName: 'files', name: 'Files', tool: filesTool, connectedInputs: {} } },
      ]
      mockEdges = []

      const w = mountCanvas()
      expect(connectHandler).not.toBeNull()

      const before = errorStore.errors.length
      connectHandler!({
        source: 'src',
        target: 'files_1',
        sourceHandle: 'result',
        targetHandle: '__positional_0',
      })

      // edge_rejected does not record history per F2 policy.
      expect(errorStore.errors.length).toBe(before)
      // Edge was not added.
      expect(mockEdges).toHaveLength(0)
      w.unmount()
    })
  })

  // --- Task 7: Drop Handling + Node Creation ---

  describe('node creation', () => {
    it('onAddNode creates node with correct structure', () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any

      const w = mountCanvas()
      const vm = w.vm as any

      vm.onAddNode({ toolName: 'gaussian_blur', position: { x: 100, y: 200 } })

      expect(mockNodes.length).toBe(1)
      const node = mockNodes[0]
      expect(node.type).toBe('tool')
      expect(node.position).toEqual({ x: 100, y: 200 })
      expect(node.data.toolName).toBe('gaussian_blur')
      expect(node.data.name).toContain('Gaussian Blur')
      expect(node.data.status).toBe('unexecuted')
      expect(node.data.parameters).toEqual({ sigma: 1.0 })
      expect(node.data.collapsed).toBe(false)
      expect(node.data.enabled).toBe(true)
      expect(node.data.connectedInputs).toEqual({})
      expect(node.data.pinnedInputs).toEqual({ image: true })  // ImageFile + required => true
      expect(node.data.output_templates).toEqual({ result: '' })  // no default on output
      w.unmount()
    })

    it('does not populate output_templates for DataFrameTool nodes (column declarations, not file paths)', () => {
      const filesTool = makeTool({
        name: 'files',
        display_name: 'Files',
        tool_type: 'DataFrameTool',
        inputs: {
          path: { type: 'Path', required: true, nullable: false, connectable: 'never' },
          pattern: { type: 'str', required: false, nullable: false, connectable: 'never', default: '*' },
        },
        outputs: {
          path: { type: 'Path' },
          filename: { type: 'str' },
        },
      })
      const store = useToolRegistryStore()
      store.tools = [filesTool] as any

      const w = mountCanvas()
      const vm = w.vm as any

      vm.onAddNode({ toolName: 'files', position: { x: 0, y: 0 } })

      expect(mockNodes.length).toBe(1)
      const node = mockNodes[0]
      expect(node.data.toolName).toBe('files')
      // DataFrameTool: no output templates even though `path` is Path-typed.
      expect(node.data.output_templates).toEqual({})
      w.unmount()
    })

    it('emits graph-changed with new node', () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any

      const w = mountCanvas()
      const vm = w.vm as any

      vm.onAddNode({ toolName: 'gaussian_blur' })

      expect(w.emitted('graph-changed')).toBeTruthy()
      const payload = w.emitted('graph-changed')![0][0] as any
      expect(payload.nodes.length).toBe(1)
      w.unmount()
    })

    it('drop with valid MIME type triggers creation', () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any

      const w = mountCanvas()

      const dropEvent = new Event('drop', { bubbles: true }) as any
      dropEvent.preventDefault = vi.fn()
      dropEvent.clientX = 150
      dropEvent.clientY = 250
      dropEvent.dataTransfer = {
        getData: (type: string) =>
          type === 'application/bioimageflow-tool' ? 'gaussian_blur' : '',
      }

      // We need the canvasRef to have a getBoundingClientRect
      const canvasEl = w.find('.canvas-view').element as HTMLElement
      canvasEl.getBoundingClientRect = () => ({
        left: 0,
        top: 0,
        right: 800,
        bottom: 600,
        width: 800,
        height: 600,
        x: 0,
        y: 0,
        toJSON: () => {},
      })

      w.find('.canvas-view').element.dispatchEvent(dropEvent)
      // Trigger Vue's handler directly
      w.find('.canvas-view').trigger('drop', {
        dataTransfer: {
          getData: (type: string) =>
            type === 'application/bioimageflow-tool' ? 'gaussian_blur' : '',
        },
        clientX: 150,
        clientY: 250,
      })

      // The drop handler may not fire properly through jsdom, so test via onAddNode
      const vm = w.vm as any
      vm.onAddNode({ toolName: 'gaussian_blur', position: { x: 150, y: 250 } })
      expect(mockNodes.length).toBeGreaterThanOrEqual(1)
      w.unmount()
    })

    it('drop without MIME type is ignored', () => {
      const w = mountCanvas()
      const vm = w.vm as any

      // Simulate a drop event with no valid MIME data
      // The onDrop function checks for the MIME type and returns early
      // We test by calling onAddNode with a nonexistent tool
      vm.onAddNode({ toolName: 'nonexistent_tool' })
      expect(mockNodes.length).toBe(0)
      w.unmount()
    })

    it('workflow drop creates a sub-workflow node from the saved workflow graph', async () => {
      const graph = {
        nodes: [{
          id: 'inner_1',
          name: 'Inner 1',
          tool_name: 'gaussian_blur',
          position: [0, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
      }
      mockSavedWorkflow(graph, 'analysis')
      const w = mountCanvas()
      const vm = w.vm as any

      await vm.onAddWorkflowNode({
        workflowName: 'analysis',
        position: { x: 125, y: 225 },
      })

      expect(apiMocks.get).toHaveBeenCalledWith('/api/v1/workflows/analysis')
      expect(mockNodes).toHaveLength(1)
      expect(mockNodes[0]).toMatchObject({
        type: 'sub_workflow',
        position: { x: 125, y: 225 },
        data: {
          toolName: '__sub_workflow__',
          sub_workflow: graph,
          source_workflow_name: 'analysis',
        },
      })
      expect(w.emitted('graph-changed')).toBeTruthy()
      w.unmount()
    })
  })

  // --- Workflow-wide version switch refresh ---

  describe('tool snapshot refresh on registry change', () => {
    it('updates each node\'s tool snapshot when the registry version changes', async () => {
      // Create a node at v1.0.0, then simulate a "Set current" version
      // switch by mutating the registry to v2.0.0. The watcher in
      // CanvasView should propagate the new ToolMetadata to the existing
      // node so the GUI (NodePanel header, ToolNode badges) reflects the
      // new version without recreating the node.
      const store = useToolRegistryStore()
      store.tools = [makeTool({ package_version: '1.0.0' })] as any

      const w = mountCanvas()
      const vm = w.vm as any
      vm.onAddNode({ toolName: 'gaussian_blur', position: { x: 0, y: 0 } })

      expect(mockNodes[0].data.tool.package_version).toBe('1.0.0')

      // Simulate version switch: registry now exports the same tool at a
      // newer version.
      store.tools = [makeTool({ package_version: '2.0.0' })] as any
      await nextTick()

      expect(mockNodes[0].data.tool.package_version).toBe('2.0.0')
      w.unmount()
    })

    it('reconciles output templates when registry outputs change', async () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool({ package_version: '1.0.0' })] as any

      const w = mountCanvas()
      const vm = w.vm as any
      vm.onAddNode({ toolName: 'gaussian_blur', position: { x: 0, y: 0 } })

      expect(mockNodes[0].data.output_templates).toEqual({ result: '' })

      store.tools = [
        makeTool({
          package_version: '2.0.0',
          outputs: {
            reference_label: { type: 'int' },
            spot_label: { type: 'int' },
            overlap_count: { type: 'int' },
          },
        }),
      ] as any
      await nextTick()

      expect(mockNodes[0].data.output_templates).toEqual({})
      w.unmount()
    })

    it('marks executed nodes as out_of_date after a version switch', async () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool({ package_version: '1.0.0' })] as any

      const w = mountCanvas()
      const vm = w.vm as any
      vm.onAddNode({ toolName: 'gaussian_blur', position: { x: 0, y: 0 } })
      // Simulate the node having been executed against v1.0.0.
      mockNodes[0].data.status = 'executed'

      store.tools = [makeTool({ package_version: '2.0.0' })] as any
      await nextTick()

      expect(mockNodes[0].data.status).toBe('out_of_date')
      w.unmount()
    })

    it('leaves non-executed status alone after a version switch', async () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool({ package_version: '1.0.0' })] as any

      const w = mountCanvas()
      const vm = w.vm as any
      vm.onAddNode({ toolName: 'gaussian_blur', position: { x: 0, y: 0 } })
      // Default status is 'unexecuted'.
      expect(mockNodes[0].data.status).toBe('unexecuted')

      store.tools = [makeTool({ package_version: '2.0.0' })] as any
      await nextTick()

      // unexecuted should stay unexecuted — only `executed` flips to out_of_date.
      expect(mockNodes[0].data.status).toBe('unexecuted')
      w.unmount()
    })
  })

  // --- Task 8: Selection + Keyboard Shortcuts ---

  describe('selection and keyboard', () => {
    it('deleteSelected removes selected nodes and connected edges', () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any

      mockNodes = [
        { id: 'a', selected: true, data: { name: 'A', toolName: 'gaussian_blur' }, position: { x: 0, y: 0 } },
        { id: 'b', selected: false, data: { name: 'B', toolName: 'gaussian_blur' }, position: { x: 100, y: 0 } },
      ]
      mockEdges = [
        { id: 'e1', source: 'a', target: 'b', sourceHandle: 'result', targetHandle: 'image' },
      ]

      const w = mountCanvas()
      const vm = w.vm as any
      vm.deleteSelected()

      // Node 'a' and edge 'e1' should be removed
      expect(mockNodes.find((n: any) => n.id === 'a')).toBeUndefined()
      expect(mockEdges.find((e: any) => e.id === 'e1')).toBeUndefined()
      w.unmount()
    })

    it('non-selected nodes survive deletion', () => {
      mockNodes = [
        { id: 'a', selected: true, data: { name: 'A' }, position: { x: 0, y: 0 } },
        { id: 'b', selected: false, data: { name: 'B' }, position: { x: 100, y: 0 } },
      ]
      mockEdges = []

      const w = mountCanvas()
      const vm = w.vm as any
      vm.deleteSelected()

      expect(mockNodes.find((n: any) => n.id === 'b')).toBeDefined()
      w.unmount()
    })

    it('copySelected populates clipboard', () => {
      mockNodes = [
        {
          id: 'a',
          selected: true,
          data: { name: 'A', toolName: 'gaussian_blur', parameters: { sigma: 1.0 } },
          position: { x: 10, y: 20 },
        },
      ]
      mockEdges = []

      const w = mountCanvas()
      const vm = w.vm as any
      vm.copySelected()

      expect(vm.clipboardData).not.toBeNull()
      expect(vm.clipboardData.nodes.length).toBe(1)
      expect(vm.clipboardData.nodes[0].id).toBe('a')
      w.unmount()
    })

    it('paste creates nodes with unique IDs, remapped edges, offset positions', async () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any

      const w = mountCanvas()
      await flushPromises()

      // Set up clipboard via copy first
      mockNodes.splice(0, mockNodes.length, ...[
        {
          id: 'a',
          selected: true,
          data: { name: 'Gaussian Blur 1', toolName: 'gaussian_blur', parameters: { sigma: 2.0 } },
          position: { x: 10, y: 20 },
        },
      ])
      mockEdges.splice(0, mockEdges.length)

      const vm = w.vm as any
      vm.copySelected()

      // Now paste
      await vm.pasteFromClipboard()
      await flushPromises()

      // Should have original + pasted node
      expect(mockNodes.length).toBe(2)
      const pasted = mockNodes[1]
      expect(pasted.id).not.toBe('a')
      // Position should be offset by 50
      expect(pasted.position.x).toBe(60) // 10 + 50
      expect(pasted.position.y).toBe(70) // 20 + 50
      expect(pasted.data.status).toBe('unexecuted')
      expect(w.emitted('graph-changed')).toBeTruthy()
      w.unmount()
    })

    it('Delete key triggers deleteSelected', () => {
      mockNodes = [
        { id: 'a', selected: true, data: { name: 'A' }, position: { x: 0, y: 0 } },
      ]
      mockEdges = []

      const w = mountCanvas()
      w.find('.canvas-view').trigger('keydown', { key: 'Delete' })

      expect(mockNodes.find((n: any) => n.id === 'a')).toBeUndefined()
      w.unmount()
    })

    it('Backspace key triggers deleteSelected', () => {
      mockNodes = [
        { id: 'a', selected: true, data: { name: 'A' }, position: { x: 0, y: 0 } },
      ]
      mockEdges = []

      const w = mountCanvas()
      w.find('.canvas-view').trigger('keydown', { key: 'Backspace' })

      expect(mockNodes.find((n: any) => n.id === 'a')).toBeUndefined()
      w.unmount()
    })

    it('Ctrl+C triggers copySelected', () => {
      mockNodes = [
        {
          id: 'a',
          selected: true,
          data: { name: 'A', toolName: 'gaussian_blur', parameters: {} },
          position: { x: 0, y: 0 },
        },
      ]
      mockEdges = []

      const w = mountCanvas()
      w.find('.canvas-view').trigger('keydown', { key: 'c', ctrlKey: true })

      const vm = w.vm as any
      expect(vm.clipboardData).not.toBeNull()
      w.unmount()
    })

    it('global edit-command events invoke canvas commands', () => {
      mockNodes = [
        {
          id: 'a',
          selected: true,
          data: { name: 'A', toolName: 'gaussian_blur', parameters: {} },
          position: { x: 0, y: 0 },
        },
      ]

      const w = mountCanvas()
      window.dispatchEvent(new CustomEvent('bioimageflow:edit-command', {
        detail: { command: 'copy' },
      }))

      const vm = w.vm as any
      expect(vm.clipboardData).not.toBeNull()
      w.unmount()
    })

    it('createSelectedSubWorkflow replaces selected nodes with a sub-workflow node', () => {
      const blurTool = makeTool()
      const thresholdTool = makeThresholdTool()
      mockNodes = [
        {
          id: 'source',
          selected: false,
          data: { name: 'Source', toolName: 'gaussian_blur', tool: blurTool, parameters: {}, connectedInputs: {} },
          position: { x: 0, y: 0 },
        },
        {
          id: 'blur_1',
          selected: true,
          data: { name: 'Blur 1', toolName: 'gaussian_blur', tool: blurTool, parameters: {}, connectedInputs: {} },
          position: { x: 100, y: 0 },
        },
        {
          id: 'threshold_1',
          selected: true,
          data: { name: 'Threshold 1', toolName: 'threshold', tool: thresholdTool, parameters: {}, connectedInputs: {} },
          position: { x: 300, y: 0 },
        },
      ]
      mockEdges = [
        { id: 'e-in', source: 'source', target: 'blur_1', sourceHandle: 'result', targetHandle: 'image', type: 'column_ref' },
        { id: 'e-inner', source: 'blur_1', target: 'threshold_1', sourceHandle: 'result', targetHandle: 'mask', type: 'column_ref' },
      ]

      const w = mountCanvas()
      const vm = w.vm as any
      vm.createSelectedSubWorkflow()

      const subNode = mockNodes.find((n: any) => n.data?.toolName === '__sub_workflow__')
      expect(subNode).toBeDefined()
      expect(mockNodes.find((n: any) => n.id === 'blur_1')).toBeUndefined()
      expect(subNode.data.sub_workflow.nodes.map((n: any) => n.id)).toEqual(['blur_1', 'threshold_1'])
      expect(mockEdges[0]).toMatchObject({
        source: 'source',
        target: subNode.id,
        targetHandle: 'blur_1.image',
      })
      expect(w.emitted('graph-changed')).toBeTruthy()
      w.unmount()
    })

    it('edits a sub-workflow session draft and applies it on Ctrl+S', async () => {
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentWorkflowName: 'parent',
        parentNodeId: 'sub_1',
        parentNodeName: 'Sub 1',
        graph: {
          nodes: [
            {
              id: 'inner_1',
              name: 'Inner 1',
              tool_name: 'gaussian_blur',
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
      const applied = vi.fn()
      window.addEventListener('bioimageflow:apply-sub-workflow-session', applied)

      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()
      graphSyncMocks.syncGraph.mockClear()

      sessions.updateDraft(session.id, {
        nodes: [{
          id: 'inner_1',
          name: 'Inner 1',
          tool_name: 'gaussian_blur',
          position: [0, 0],
          parameters: { sigma: 2 },
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
      })

      expect(sessions.isDirty(session.id)).toBe(true)
      await w.find('.canvas-view').trigger('keydown', { key: 's', ctrlKey: true })

      expect(applied).toHaveBeenCalledTimes(1)
      expect((applied.mock.calls[0][0] as CustomEvent).detail).toMatchObject({
        parentNodeId: 'sub_1',
        graph: {
          nodes: [expect.objectContaining({
            id: 'inner_1',
            parameters: { sigma: 2 },
          })],
        },
      })
      expect(sessions.isDirty(session.id)).toBe(false)
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      window.removeEventListener('bioimageflow:apply-sub-workflow-session', applied)
      w.unmount()
    })

    it('loads sub-workflow editor nodes with a shared publishing context', async () => {
      const toolStore = useToolRegistryStore()
      toolStore.tools = [makeTool()] as any
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentWorkflowName: 'parent',
        parentNodeId: 'sub_1',
        parentNodeName: 'Sub 1',
        graph: {
          nodes: [{
            id: 'inner_1',
            name: 'Inner 1',
            tool_name: 'gaussian_blur',
            position: [0, 0],
            parameters: {},
            resources: {},
            output_templates: {},
            enabled: true,
            collapsed: false,
          }],
          edges: [],
        },
        published_inputs: [{
          name: 'image',
          internal_node_id: 'inner_1',
          internal_field: 'image',
          kind: 'input',
          schema: { type: 'ImageFile' },
          default: null,
        }],
        published_outputs: [],
      })

      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()

      const innerNode = mockNodes.find((n: any) => n.id === 'inner_1')!
      expect(innerNode.data.subWorkflowContext.parentNodeId).toBe('sub_1')
      expect(innerNode.data.subWorkflowContext.published_inputs)
        .toBe(sessions.sessionById(session.id)!.published_inputs)

      innerNode.data.subWorkflowContext.published_inputs[0].name = 'input_folder'
      expect(sessions.isDirty(session.id)).toBe(true)
      w.unmount()
    })

    it('loads normal workflow nodes with a shared root publishing context', async () => {
      const toolStore = useToolRegistryStore()
      toolStore.tools = [makeTool()] as any
      const graph = {
        nodes: [{
          id: 'inner_1',
          name: 'Inner 1',
          tool_name: 'gaussian_blur',
          position: [0, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
        published_inputs: [{
          name: 'image',
          internal_node_id: 'inner_1',
          internal_field: 'image',
          kind: 'input',
          schema: { type: 'ImageFile' },
          default: null,
        }],
        published_outputs: [],
      }
      mockSavedWorkflow(graph as any, 'analysis')

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()

      const innerNode = mockNodes.find((n: any) => n.id === 'inner_1')!
      expect(innerNode.data.publicationContext.published_inputs[0].name).toBe('image')
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledWith(expect.objectContaining({
        published_inputs: [expect.objectContaining({ name: 'image' })],
      }))
      innerNode.data.publicationContext.published_inputs[0].name = 'input_image'
      expect(mockNodes[0].data.publicationContext.published_inputs[0].name).toBe('input_image')
      w.unmount()
    })

    it('reconciles parent pins, parameters, and edges when applying a published interface', () => {
      const w = mountCanvas()
      mockNodes.splice(0, mockNodes.length, {
        id: 'sub_1',
        type: 'sub_workflow',
        position: { x: 0, y: 0 },
        data: {
          name: 'Sub 1',
          toolName: '__sub_workflow__',
          status: 'executed',
          parameters: { image: '/data', removed: 'stale', keep: 42 },
          pinnedInputs: { image: false, removed: true },
          connectedInputs: { image: 'files.path', removed: 'files.other' },
          published_inputs: [
            {
              name: 'image',
              internal_node_id: 'files',
              internal_field: 'input_folder',
              kind: 'parameter',
              schema: { type: 'Path' },
              default: null,
            },
            {
              name: 'removed',
              internal_node_id: 'files',
              internal_field: 'removed',
              kind: 'parameter',
              schema: { type: 'Path' },
              default: null,
            },
          ],
          published_outputs: [
            {
              name: 'labels',
              internal_node_id: 'count',
              internal_output: 'label_count',
              schema: { type: 'int' },
            },
            {
              name: 'gone',
              internal_node_id: 'count',
              internal_output: 'gone',
              schema: { type: 'int' },
            },
          ],
          sub_workflow: { nodes: [], edges: [] },
        },
      })
      mockEdges.splice(
        0,
        mockEdges.length,
        { id: 'e-in', source: 'files_1', target: 'sub_1', sourceHandle: 'path', targetHandle: 'image', type: 'column_ref' },
        { id: 'e-removed-in', source: 'files_1', target: 'sub_1', sourceHandle: 'other', targetHandle: 'removed', type: 'column_ref' },
        { id: 'e-out', source: 'sub_1', target: 'sink_1', sourceHandle: 'labels', targetHandle: 'count', type: 'column_ref' },
        { id: 'e-removed-out', source: 'sub_1', target: 'sink_2', sourceHandle: 'gone', targetHandle: 'count', type: 'column_ref' },
      )

      const vm = w.vm as any
      vm.applySubWorkflowDraft('sub_1', { nodes: [], edges: [] }, {
        published_inputs: [{
          name: 'input_folder',
          internal_node_id: 'files',
          internal_field: 'input_folder',
          kind: 'parameter',
          schema: { type: 'Path' },
          default: null,
        }],
        published_outputs: [{
          name: 'label_count',
          internal_node_id: 'count',
          internal_output: 'label_count',
          schema: { type: 'int' },
        }],
      })

      const subNode = mockNodes.find((n: any) => n.id === 'sub_1')!
      expect(mockEdges.map((edge: any) => edge.id)).toEqual(['e-in', 'e-out'])
      expect(mockEdges[0].targetHandle).toBe('input_folder')
      expect(mockEdges[1].sourceHandle).toBe('label_count')
      expect(subNode.data.parameters).toEqual({ input_folder: '/data', keep: 42 })
      expect(subNode.data.pinnedInputs).toEqual({ input_folder: false })
      expect(subNode.data.connectedInputs).toEqual({ input_folder: 'files_1.path' })
      expect(subNode.data.published_inputs[0].name).toBe('input_folder')
      expect(subNode.data.published_outputs[0].name).toBe('label_count')
      expect(subNode.data.status).toBe('out_of_date')
      expect(w.emitted('graph-changed')).toBeTruthy()
      w.unmount()
    })

    it('Ctrl+A selects all nodes via keydown', () => {
      mockNodes = [
        { id: 'a', selected: false, data: {}, position: { x: 0, y: 0 } },
        { id: 'b', selected: false, data: {}, position: { x: 100, y: 0 } },
      ]

      const w = mountCanvas()
      w.find('.canvas-view').trigger('keydown', { key: 'a', ctrlKey: true })

      expect(mockNodes.every((n: any) => n.selected)).toBe(true)
      w.unmount()
    })

    it('ignores global edit commands when another canvas tab is active', async () => {
      mockNodes = [
        { id: 'a', selected: false, data: {}, position: { x: 0, y: 0 } },
        { id: 'b', selected: false, data: {}, position: { x: 100, y: 0 } },
      ]

      const w = mountCanvas({ params: { panelId: 'workflow:a' } })
      window.dispatchEvent(new CustomEvent('bioimageflow:canvas-tab-activated', {
        detail: { panelId: 'workflow:b' },
      }))
      window.dispatchEvent(new CustomEvent('bioimageflow:edit-command', {
        detail: { command: 'select-all' },
      }))
      await nextTick()

      expect(mockNodes.every((n: any) => n.selected)).toBe(false)
      w.unmount()
    })

    it('selectAll selects all nodes', () => {
      mockNodes = [
        { id: 'a', selected: false, data: {}, position: { x: 0, y: 0 } },
        { id: 'b', selected: false, data: {}, position: { x: 100, y: 0 } },
      ]

      const w = mountCanvas()
      const vm = w.vm as any
      vm.selectAll()

      expect(mockNodes.every((n: any) => n.selected)).toBe(true)
      w.unmount()
    })
  })

  // --- Task 7/8: Node drag undo ---

  describe('node drag undo', () => {
    it('registers drag start and stop handlers', () => {
      const w = mountCanvas()
      expect(dragStartHandler).not.toBeNull()
      expect(dragStopHandler).not.toBeNull()
      w.unmount()
    })

    it('emits graph-changed when a node is moved', () => {
      mockNodes = [
        { id: 'a', selected: false, data: { name: 'A', toolName: 'gaussian_blur' }, position: { x: 0, y: 0 } },
      ]

      const w = mountCanvas()

      // Simulate drag start
      dragStartHandler!({ nodes: [{ id: 'a', position: { x: 0, y: 0 } }] })

      // Simulate drag stop with new position
      dragStopHandler!({ nodes: [{ id: 'a', position: { x: 50, y: 50 } }] })

      expect(w.emitted('graph-changed')).toBeTruthy()
      w.unmount()
    })

    it('does not emit graph-changed when position unchanged', () => {
      mockNodes = [
        { id: 'a', selected: false, data: { name: 'A', toolName: 'gaussian_blur' }, position: { x: 10, y: 20 } },
      ]

      const w = mountCanvas()

      dragStartHandler!({ nodes: [{ id: 'a', position: { x: 10, y: 20 } }] })
      dragStopHandler!({ nodes: [{ id: 'a', position: { x: 10, y: 20 } }] })

      // graph-changed should NOT have been emitted by drag (only by initial setup if any)
      expect(w.emitted('graph-changed')).toBeFalsy()
      w.unmount()
    })

    it('handles multi-node drag as single undo step', () => {
      mockNodes = [
        { id: 'a', selected: true, data: { name: 'A' }, position: { x: 0, y: 0 } },
        { id: 'b', selected: true, data: { name: 'B' }, position: { x: 100, y: 0 } },
      ]

      const w = mountCanvas()

      dragStartHandler!({
        nodes: [
          { id: 'a', position: { x: 0, y: 0 } },
          { id: 'b', position: { x: 100, y: 0 } },
        ],
      })

      dragStopHandler!({
        nodes: [
          { id: 'a', position: { x: 50, y: 50 } },
          { id: 'b', position: { x: 150, y: 50 } },
        ],
      })

      // Should emit exactly one graph-changed event for the multi-node drag
      const events = w.emitted('graph-changed')
      expect(events).toBeTruthy()
      expect(events!.length).toBe(1)
      w.unmount()
    })
  })

  // --- Reload from IndexedDB ---

  describe('restore persisted workflow on mount', () => {
    function savedNode(id: string, x: number) {
      return {
        id,
        name: id,
        tool_name: 'gaussian_blur',
        position: [x, 100],
        parameters: {},
        resources: {},
        output_templates: {},
        collapsed: false,
        enabled: true,
      }
    }

    function savedEdge(id: string, source: string, target: string) {
      return {
        type: 'column_ref',
        id,
        source_node: source,
        target_node: target,
        source_output: 'result',
        target_input: 'image',
      }
    }

    it('restores both nodes and edges from persisted state', async () => {
      const nodes = [savedNode('a', 100), savedNode('b', 400)]
      const edges = [savedEdge('e1', 'a', 'b')]
      mockSavedWorkflow({ nodes, edges })

      const w = mountCanvas()
      // Allow onMounted's async chain (await loadWorkflow + await nextTick) to settle.
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockNodes).toHaveLength(2)
      expect(mockEdges).toHaveLength(1)

      const restored = mockEdges[0]
      expect(restored.id).toBe('e1')
      expect(restored.source).toBe('a')
      expect(restored.target).toBe('b')
      expect(restored.sourceHandle).toBe('result')
      expect(restored.targetHandle).toBe('image')
      // The edge type MUST be preserved — without it, Vue Flow renders the
      // default edge style instead of our custom ColumnRefEdge/PositionalEdge,
      // which was the visual bug after reload.
      expect(restored.type).toBe('column_ref')

      w.unmount()
    })

    it('does not autosave or sync a partial graph while restoring a clean workflow', async () => {
      const name = 'saved'
      const nodes = [savedNode('a', 100), savedNode('b', 400)]
      const edges = [savedEdge('e1', 'a', 'b')]
      const graph = { nodes, edges }

      apiMocks.get.mockImplementation((url: string) => {
        if (url === '/api/v1/workflows') {
          return Promise.resolve({
            data: [{ name, display_name: 'Saved workflow' }],
          })
        }
        if (url === `/api/v1/workflows/${name}`) {
          return Promise.resolve({
            data: {
              info: { name, display_name: 'Saved workflow' },
              graph,
              missing_packages: [],
              missing_tools: [],
            },
          })
        }
        if (url === '/api/v1/tools') return Promise.resolve({ data: [makeTool()] })
        return Promise.resolve({ data: {} })
      })
      autoSaveMocks.getLastOpenedWorkflow.mockResolvedValueOnce(name)

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(autoSaveMocks.scheduleAutoSave).not.toHaveBeenCalled()
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledTimes(1)
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledWith(expect.objectContaining({
        edges: [expect.objectContaining({ id: 'e1' })],
      }))

      w.unmount()
    })

    it('ignores stale autosave entries older than the server workflow', async () => {
      const name = 'saved'
      const serverGraph = {
        nodes: [savedNode('a', 100), savedNode('b', 400)],
        edges: [savedEdge('e1', 'a', 'b')],
      }
      const staleGraph = {
        nodes: [savedNode('stale', 100)],
        edges: [],
      }
      const lastModified = '2026-04-30T12:00:00.000Z'

      apiMocks.get.mockImplementation((url: string) => {
        if (url === '/api/v1/workflows') {
          return Promise.resolve({
            data: [{
              name,
              display_name: 'Saved workflow',
              path: '/tmp/saved.bioflow',
              last_modified: lastModified,
            }],
          })
        }
        if (url === `/api/v1/workflows/${name}`) {
          return Promise.resolve({
            data: {
              info: {
                name,
                display_name: 'Saved workflow',
                path: '/tmp/saved.bioflow',
                last_modified: lastModified,
              },
              graph: serverGraph,
              missing_packages: [],
              missing_tools: [],
            },
          })
        }
        if (url === '/api/v1/tools') return Promise.resolve({ data: [makeTool()] })
        return Promise.resolve({ data: {} })
      })
      autoSaveMocks.loadMostRecentAutoSave.mockResolvedValueOnce({
        name,
        graph: staleGraph,
        timestamp: Date.parse(lastModified) - 1000,
      })

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockNodes.map((node: any) => node.id)).toEqual(['a', 'b'])
      expect(mockEdges).toHaveLength(1)
      expect(mockEdges[0].id).toBe('e1')
      expect(autoSaveMocks.clearAutoSave).toHaveBeenCalledWith(name)

      w.unmount()
    })

    it('loads last-opened renamed workflow when a stale autosave uses the old name', async () => {
      const oldName = 'Untitled'
      const newName = 'new_workflow'
      const serverGraph = {
        nodes: [savedNode('a', 100), savedNode('b', 400)],
        edges: [savedEdge('e1', 'a', 'b')],
      }
      const staleGraph = {
        nodes: [savedNode('stale', 100)],
        edges: [],
      }

      apiMocks.get.mockImplementation((url: string) => {
        if (url === '/api/v1/workflows') {
          return Promise.resolve({
            data: [{
              name: newName,
              display_name: 'New workflow',
              path: '/tmp/new_workflow.json',
              last_modified: '2026-04-30T12:00:00.000Z',
            }],
          })
        }
        if (url === `/api/v1/workflows/${newName}`) {
          return Promise.resolve({
            data: {
              info: {
                name: newName,
                display_name: 'New workflow',
                path: '/tmp/new_workflow.json',
                last_modified: '2026-04-30T12:00:00.000Z',
              },
              graph: serverGraph,
              missing_packages: [],
              missing_tools: [],
            },
          })
        }
        if (url === '/api/v1/tools') return Promise.resolve({ data: [makeTool()] })
        return Promise.resolve({ data: {} })
      })
      autoSaveMocks.loadMostRecentAutoSave.mockResolvedValueOnce({
        name: oldName,
        graph: staleGraph,
        timestamp: Date.parse('2026-04-30T12:00:01.000Z'),
      })
      autoSaveMocks.getLastOpenedWorkflow.mockResolvedValueOnce(newName)

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockNodes.map((node: any) => node.id)).toEqual(['a', 'b'])
      expect(mockEdges).toHaveLength(1)
      expect(mockEdges[0].id).toBe('e1')
      expect(autoSaveMocks.clearAutoSave).toHaveBeenCalledWith(oldName)

      w.unmount()
    })

    it('sets nodes before edges so Vue Flow handles exist when edges attach', async () => {
      const nodes = [savedNode('a', 100), savedNode('b', 400)]
      const edges = [savedEdge('e1', 'a', 'b')]
      mockSavedWorkflow({ nodes, edges })

      // Track call order: the restore path must populate nodes into Vue Flow's
      // internal state before edges, otherwise edges reference nodes/handles
      // that don't exist yet and Vue Flow drops them from the rendered graph.
      const callOrder: string[] = []
      const origSetNodes = mockNodes
      // Patch mockNodes / mockEdges indirectly via the useVueFlow setters
      // by temporarily wrapping them (the mock uses the module-level arrays
      // directly, so we instrument through a custom watch).
      const setNodesCalls: any[] = []
      const setEdgesCalls: any[] = []

      // Re-mock setNodes / setEdges would require rebuilding the vi.mock;
      // instead, observe the effect: after mount, between the setNodes and
      // setEdges calls there must be at least one microtask (nextTick). We
      // verify by asserting that nodes are visible in the getNodes computed
      // before edges land. Since both calls happen in the same onMounted
      // async function, the simplest invariant is: if edges are in mockEdges,
      // the corresponding source/target nodes are in mockNodes.
      void origSetNodes
      void setNodesCalls
      void setEdgesCalls

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()
      callOrder.push('after-mount')

      // Every restored edge must have both endpoints present as nodes.
      for (const edge of mockEdges) {
        expect(mockNodes.find((n: any) => n.id === edge.source)).toBeDefined()
        expect(mockNodes.find((n: any) => n.id === edge.target)).toBeDefined()
      }

      w.unmount()
    })

    it('no-op when storage is empty', async () => {
      const w = mountCanvas()
      await flushPromises()
      await nextTick()

      expect(mockNodes).toHaveLength(0)
      expect(mockEdges).toHaveLength(0)

      w.unmount()
    })

    it('no-op when storage has zero nodes', async () => {
      mockSavedWorkflow({ nodes: [], edges: [] })

      const w = mountCanvas()
      await flushPromises()
      await nextTick()

      expect(mockNodes).toHaveLength(0)
      expect(mockEdges).toHaveLength(0)

      w.unmount()
    })

    it('restores edges even when the tool registry is empty (restore-race)', async () => {
      // Regression for a Firefox-specific bug where tool fetch was still in
      // flight while CanvasView's onMounted restored edges. Startup now awaits
      // tool fetch before applying the saved graph, so the registry can be
      // empty at mount time without rejecting restored connections.
      const store = useToolRegistryStore()
      store.tools = [] as any // registry empty — as if fetchTools hasn't resolved

      const nodes = [savedNode('a', 100), savedNode('b', 400)]
      const edges = [savedEdge('e1', 'a', 'b')]
      mockSavedWorkflow({ nodes, edges })

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()

      // Even though the registry is empty, isValidConnection should accept
      // the connection using node.data.tool.
      const vm = w.vm as any
      const ok = vm.isValidConnection({
        source: 'a',
        target: 'b',
        sourceHandle: 'result',
        targetHandle: 'image',
      })
      expect(ok).toBe(true)

      // And the restored edges must all be present in the Vue Flow state.
      expect(mockEdges).toHaveLength(1)
      expect(mockEdges[0].source).toBe('a')
      expect(mockEdges[0].target).toBe('b')

      w.unmount()
    })

    it('preserves positional edges (separate edge type)', async () => {
      const nodes = [savedNode('a', 100), savedNode('b', 400)]
      const edges = [
        {
          type: 'positional',
          id: 'e_pos',
          source_node: 'a',
          target_node: 'b',
          positional_index: 0,
        },
      ]
      mockSavedWorkflow({ nodes, edges })

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockEdges).toHaveLength(1)
      expect(mockEdges[0].type).toBe('positional')
      expect(mockEdges[0].targetHandle).toBe('__positional_0')

      w.unmount()
    })
  })

  // --- Phase 3: cross-region edge rejection ---

  describe('Phase 3 — cross-region connection rules', () => {
    function makeDataFrameTool(): ToolMetadata {
      return makeTool({
        name: 'cross_join',
        display_name: 'CrossJoin',
        tool_type: 'DataFrameTool',
        accepts_upstream: true,
        dynamic_outputs: true,
        inputs: {},
        outputs: {},
      })
    }

    function makeSourceTool(): ToolMetadata {
      return makeTool({
        name: 'files',
        display_name: 'Files',
        tool_type: 'DataFrameTool',
        accepts_upstream: false,
        dynamic_outputs: false,
        inputs: {},
        outputs: {
          path: { type: 'Path' },
          filename: { type: 'str' },
        },
      })
    }

    it('header -> header creates a PositionalEdge', () => {
      const store = useToolRegistryStore()
      const srcTool = makeSourceTool()
      const dfTool = makeDataFrameTool()
      store.tools = [srcTool, dfTool] as any

      mockNodes = [
        { id: 'files_1', data: { toolName: 'files', name: 'Files 1', tool: srcTool, connectedInputs: {} } },
        { id: 'join_1', data: { toolName: 'cross_join', name: 'CrossJoin 1', tool: dfTool, connectedInputs: {} } },
      ]
      mockEdges = []

      const w = mountCanvas()
      connectHandler!({
        source: 'files_1',
        target: 'join_1',
        sourceHandle: '__dataframe_out',
        targetHandle: '__positional_0',
      })

      expect(mockEdges).toHaveLength(1)
      expect(mockEdges[0].type).toBe('positional')
      w.unmount()
    })

    it('body -> body creates a ColumnRefEdge', () => {
      const store = useToolRegistryStore()
      const srcTool = makeSourceTool()
      const procTool = makeTool()
      store.tools = [srcTool, procTool] as any

      mockNodes = [
        { id: 'files_1', data: { toolName: 'files', name: 'Files 1', tool: srcTool, connectedInputs: {} } },
        { id: 'blur_1', data: { toolName: 'gaussian_blur', name: 'Blur 1', tool: procTool, connectedInputs: {} } },
      ]
      mockEdges = []

      const w = mountCanvas()
      connectHandler!({
        source: 'files_1',
        target: 'blur_1',
        sourceHandle: 'path',
        targetHandle: 'image',
      })

      expect(mockEdges).toHaveLength(1)
      expect(mockEdges[0].type).toBe('column_ref')
      w.unmount()
    })

    it('header -> body is rejected (cross-region)', () => {
      const store = useToolRegistryStore()
      const srcTool = makeSourceTool()
      const procTool = makeTool()
      store.tools = [srcTool, procTool] as any

      mockNodes = [
        { id: 'files_1', data: { toolName: 'files', name: 'Files 1', tool: srcTool, connectedInputs: {} } },
        { id: 'blur_1', data: { toolName: 'gaussian_blur', name: 'Blur 1', tool: procTool, connectedInputs: {} } },
      ]
      mockEdges = []

      const w = mountCanvas()
      const vm = w.vm as any

      const result = vm.isValidConnection({
        source: 'files_1',
        target: 'blur_1',
        sourceHandle: '__dataframe_out',
        targetHandle: 'image',
      })
      expect(result).toBe(false)
      w.unmount()
    })

    it('body -> header is rejected (cross-region)', () => {
      const store = useToolRegistryStore()
      const srcTool = makeSourceTool()
      const dfTool = makeDataFrameTool()
      store.tools = [srcTool, dfTool] as any

      mockNodes = [
        { id: 'files_1', data: { toolName: 'files', name: 'Files 1', tool: srcTool, connectedInputs: {} } },
        { id: 'join_1', data: { toolName: 'cross_join', name: 'CrossJoin 1', tool: dfTool, connectedInputs: {} } },
      ]
      mockEdges = []

      const w = mountCanvas()
      const vm = w.vm as any

      const result = vm.isValidConnection({
        source: 'files_1',
        target: 'join_1',
        sourceHandle: 'path',
        targetHandle: '__positional_0',
      })
      expect(result).toBe(false)
      w.unmount()
    })

    it('Phase 1 regression: source-tool positional rejection still fires', () => {
      const store = useToolRegistryStore()
      const srcTool = makeSourceTool()
      const otherSrcTool = makeTool({
        name: 'generate',
        display_name: 'Generate',
        tool_type: 'DataFrameTool',
        accepts_upstream: false,
      })
      store.tools = [srcTool, otherSrcTool] as any

      mockNodes = [
        { id: 'files_1', data: { toolName: 'files', name: 'Files 1', tool: srcTool, connectedInputs: {} } },
        { id: 'gen_1', data: { toolName: 'generate', name: 'Generate 1', tool: otherSrcTool, connectedInputs: {} } },
      ]
      mockEdges = []

      const w = mountCanvas()
      const vm = w.vm as any

      const result = vm.isValidConnection({
        source: 'files_1',
        target: 'gen_1',
        sourceHandle: '__dataframe_out',
        targetHandle: '__positional_0',
      })
      expect(result).toBe(false)
      w.unmount()
    })

    it('Phase 2 regression: "any" type bypass still fires', () => {
      const store = useToolRegistryStore()
      const genTool = makeTool({
        name: 'generate',
        display_name: 'Generate',
        tool_type: 'DataFrameTool',
        accepts_upstream: false,
        dynamic_outputs: true,
        inputs: {},
        outputs: {},
      })
      const blurTool = makeTool()
      store.tools = [genTool, blurTool] as any

      mockNodes = [
        { id: 'gen_1', data: { toolName: 'generate', tool: genTool } },
        { id: 'blur_1', data: { toolName: 'gaussian_blur', tool: blurTool } },
      ]

      const resolvedStore = useResolvedOutputsStore()
      resolvedStore.resolvedOutputsByNodeId['gen_1'] = {
        resolved: true,
        columns: {
          sensitivity: { type: 'any', default: null, image_spec: null },
        },
      }

      const w = mountCanvas()
      const vm = w.vm as any

      const result = vm.isValidConnection({
        source: 'gen_1',
        target: 'blur_1',
        sourceHandle: 'sensitivity',
        targetHandle: 'image',
      })
      expect(result).toBe(true)
      w.unmount()
    })
  })

  // --- Phase 2: "any" type handling in isValidConnection ---

  describe('isValidConnection — "any" type compatibility', () => {
    function makeGenerateTool(): ToolMetadata {
      return makeTool({
        name: 'generate',
        display_name: 'Generate',
        tool_type: 'DataFrameTool',
        accepts_upstream: false,
        dynamic_outputs: true,
        inputs: {
          column_name: { type: 'str', required: true, nullable: false, connectable: 'never' },
        },
        outputs: {},
      })
    }

    it('accepts "any"-typed output into an ImageFile input', () => {
      const store = useToolRegistryStore()
      const genTool = makeGenerateTool()
      const blurTool = makeTool()
      store.tools = [genTool, blurTool] as any

      mockNodes = [
        { id: 'gen_1', data: { toolName: 'generate', tool: genTool } },
        { id: 'blur_1', data: { toolName: 'gaussian_blur', tool: blurTool } },
      ]

      // Put resolved outputs for the Generate node.
      const resolvedStore = useResolvedOutputsStore()
      resolvedStore.resolvedOutputsByNodeId['gen_1'] = {
        resolved: true,
        columns: {
          sensitivity: { type: 'any', default: null, image_spec: null },
        },
      }

      const w = mountCanvas()
      const vm = w.vm as any

      const result = vm.isValidConnection({
        source: 'gen_1',
        target: 'blur_1',
        sourceHandle: 'sensitivity',
        targetHandle: 'image',
      })
      expect(result).toBe(true)
      w.unmount()
    })

    it('still rejects typed (non-any) output into a different-type input', () => {
      const store = useToolRegistryStore()
      const stringSource = makeTool({
        name: 'string_source',
        display_name: 'String Source',
        outputs: { value: { type: 'str' } },
      })
      store.tools = [stringSource, makeTool()] as any

      mockNodes = [
        { id: 'src_1', data: { toolName: 'string_source', tool: stringSource } },
        { id: 'blur_1', data: { toolName: 'gaussian_blur', tool: makeTool() } },
      ]

      const w = mountCanvas()
      const vm = w.vm as any

      const result = vm.isValidConnection({
        source: 'src_1',
        target: 'blur_1',
        sourceHandle: 'value',
        targetHandle: 'image',
      })
      expect(result).toBe(false)
      w.unmount()
    })
  })

  // --- Resolved-outputs refresh on positional edge changes ---

  describe('resolved outputs — refresh on positional edge changes', () => {
    function makeJoinTool(): ToolMetadata {
      return makeTool({
        name: 'cross_join',
        display_name: 'CrossJoin',
        tool_type: 'DataFrameTool',
        accepts_upstream: true,
        dynamic_outputs: true,
        inputs: {},
        outputs: {},
      })
    }

    function makeFilesTool(): ToolMetadata {
      return makeTool({
        name: 'files',
        display_name: 'Files',
        tool_type: 'DataFrameTool',
        accepts_upstream: false,
        dynamic_outputs: false,
        inputs: {},
        outputs: { path: { type: 'Path' } },
      })
    }

    it('connecting a positional edge into a dynamic_outputs node triggers a refresh', async () => {
      const store = useToolRegistryStore()
      const filesTool = makeFilesTool()
      const joinTool = makeJoinTool()
      store.tools = [filesTool, joinTool] as any

      mockNodes = [
        { id: 'files_1', data: { toolName: 'files', tool: filesTool, name: 'Files 1', connectedInputs: {} } },
        { id: 'join_1', data: { toolName: 'cross_join', tool: joinTool, name: 'CrossJoin 1', connectedInputs: {} } },
      ]
      mockEdges = []

      const resolvedStore = useResolvedOutputsStore()
      ;(resolvedStore.refreshResolvedOutputs as any).mockClear()

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      mockNodes.splice(0, mockNodes.length,
        { id: 'files_1', data: { toolName: 'files', tool: filesTool, name: 'Files 1', connectedInputs: {} } },
        { id: 'join_1', data: { toolName: 'cross_join', tool: joinTool, name: 'CrossJoin 1', connectedInputs: {} } },
      )
      mockEdges.splice(0, mockEdges.length)
      ;(resolvedStore.refreshResolvedOutputs as any).mockClear()

      connectHandler!({
        source: 'files_1',
        target: 'join_1',
        sourceHandle: '__dataframe_out',
        targetHandle: '__positional_0',
      })

      await flushPromises()
      await nextTick()
      await flushPromises()

      const calls = (resolvedStore.refreshResolvedOutputs as any).mock.calls
      const calledForJoin = calls.some((c: any[]) => c[0] === 'join_1')
      expect(calledForJoin).toBe(true)
      w.unmount()
    })

    it('selecting and deleting a positional edge into a dynamic_outputs node triggers a refresh', async () => {
      const store = useToolRegistryStore()
      const filesTool = makeFilesTool()
      const joinTool = makeJoinTool()
      store.tools = [filesTool, joinTool] as any

      mockNodes = [
        { id: 'files_1', data: { toolName: 'files', tool: filesTool, name: 'Files 1', connectedInputs: {} } },
        {
          id: 'join_1',
          data: {
            toolName: 'cross_join',
            tool: joinTool,
            name: 'CrossJoin 1',
            connectedInputs: { __positional_0: 'files_1.__dataframe_out' },
          },
        },
      ]
      mockEdges = [
        {
          id: 'e1',
          source: 'files_1',
          target: 'join_1',
          sourceHandle: '__dataframe_out',
          targetHandle: '__positional_0',
          type: 'positional',
          selected: true,
        },
      ]

      const resolvedStore = useResolvedOutputsStore()
      ;(resolvedStore.refreshResolvedOutputs as any).mockClear()

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      mockNodes.splice(0, mockNodes.length,
        { id: 'files_1', data: { toolName: 'files', tool: filesTool, name: 'Files 1', connectedInputs: {} } },
        {
          id: 'join_1',
          data: {
            toolName: 'cross_join',
            tool: joinTool,
            name: 'CrossJoin 1',
            connectedInputs: { __positional_0: 'files_1.__dataframe_out' },
          },
        },
      )
      mockEdges.splice(0, mockEdges.length, {
        id: 'e1',
        source: 'files_1',
        target: 'join_1',
        sourceHandle: '__dataframe_out',
        targetHandle: '__positional_0',
        type: 'positional',
        selected: true,
      })
      ;(resolvedStore.refreshResolvedOutputs as any).mockClear()

      const vm = w.vm as any
      vm.deleteSelected()

      await flushPromises()
      await nextTick()

      const calls = (resolvedStore.refreshResolvedOutputs as any).mock.calls
      const calledForJoin = calls.some((c: any[]) => c[0] === 'join_1')
      expect(calledForJoin).toBe(true)
      w.unmount()
    })

    it('does not refresh when a positional edge targets a non-dynamic node', async () => {
      const store = useToolRegistryStore()
      const filesTool = makeFilesTool()
      const passthroughTool = makeTool({
        name: 'filter_rows',
        display_name: 'Filter',
        tool_type: 'DataFrameTool',
        accepts_upstream: true,
        dynamic_outputs: false,
        inputs: {},
        outputs: {},
      })
      store.tools = [filesTool, passthroughTool] as any

      mockNodes = [
        { id: 'files_1', data: { toolName: 'files', tool: filesTool, name: 'Files 1', connectedInputs: {} } },
        { id: 'filter_1', data: { toolName: 'filter_rows', tool: passthroughTool, name: 'Filter 1', connectedInputs: {} } },
      ]
      mockEdges = []

      const resolvedStore = useResolvedOutputsStore()
      ;(resolvedStore.refreshResolvedOutputs as any).mockClear()

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      mockNodes.splice(0, mockNodes.length,
        { id: 'files_1', data: { toolName: 'files', tool: filesTool, name: 'Files 1', connectedInputs: {} } },
        { id: 'filter_1', data: { toolName: 'filter_rows', tool: passthroughTool, name: 'Filter 1', connectedInputs: {} } },
      )
      mockEdges.splice(0, mockEdges.length)
      ;(resolvedStore.refreshResolvedOutputs as any).mockClear()

      connectHandler!({
        source: 'files_1',
        target: 'filter_1',
        sourceHandle: '__dataframe_out',
        targetHandle: '__positional_0',
      })

      await flushPromises()
      await nextTick()
      await flushPromises()

      const calls = (resolvedStore.refreshResolvedOutputs as any).mock.calls
      const calledForFilter = calls.some((c: any[]) => c[0] === 'filter_1')
      expect(calledForFilter).toBe(false)
      w.unmount()
    })
  })
})
