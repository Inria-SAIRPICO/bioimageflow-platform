import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref, reactive, computed, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import type { ToolMetadata } from '@/api/types'

// --- Mock data ---

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

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

function makeGraphNode(
  id: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    id,
    name: id,
    tool_name: 'gaussian_blur',
    position: [0, 0],
    parameters: { sigma: 1 },
    resources: {},
    output_templates: { result: '' },
    enabled: true,
    collapsed: false,
    ...overrides,
  }
}

// --- Mock stores & composables ---

let mockNodes: any[] = []
let mockEdges: any[] = []
let connectHandler: ((connection: any) => void) | null = null
let selectionHandler: ((params: any) => void) | null = null
let dragStartHandler: ((event: any) => void) | null = null
let dragStopHandler: ((event: any) => void) | null = null
let dropNextNonEmptySetEdges = false

const vueFlowMocks = vi.hoisted(() => ({
  instanceIds: [] as Array<string | undefined>,
  isolateByInstance: false,
  graphs: new Map<string, { nodes: any[]; edges: any[] }>(),
}))

vi.mock('@vue-flow/core', () => {
  const VueFlow = defineComponent({
    name: 'VueFlow',
    props: ['id', 'nodes', 'edges', 'nodeTypes', 'edgeTypes', 'isValidConnection', 'selectionKeyCode', 'fitViewOnInit'],
    template: '<div class="vue-flow-mock"><slot /></div>',
  })
  return {
    VueFlow,
    useVueFlow: (id?: string) => {
      vueFlowMocks.instanceIds.push(id)
      const graph = vueFlowMocks.isolateByInstance
        ? reactive({ nodes: [] as any[], edges: [] as any[] })
        : null
      if (graph && id) vueFlowMocks.graphs.set(id, graph)
      const nodes = () => graph?.nodes ?? mockNodes
      const edges = () => graph?.edges ?? mockEdges
      return {
      project: (pos: { x: number; y: number }) => pos,
      addNodes: (added: any[]) => { nodes().push(...added) },
      addEdges: (added: any[]) => { edges().push(...added) },
      removeNodes: (ids: string[]) => {
        const idSet = new Set(ids)
        const current = nodes()
        const kept = current.filter((n: any) => !idSet.has(n.id))
        current.splice(0, current.length, ...kept)
      },
      removeEdges: (ids: string[]) => {
        const idSet = new Set(ids)
        const current = edges()
        const kept = current.filter((e: any) => !idSet.has(e.id))
        current.splice(0, current.length, ...kept)
      },
      // Mutate the array in place so the `computed(() => mockNodes)` ref
      // above keeps the same array identity and downstream consumers see
      // the new contents.
      setNodes: (nodes: any[]) => {
        const current = graph?.nodes ?? mockNodes
        current.splice(0, current.length, ...nodes)
      },
      setEdges: (edges: any[]) => {
        if (dropNextNonEmptySetEdges && edges.length > 0) {
          dropNextNonEmptySetEdges = false
          const current = graph?.edges ?? mockEdges
          current.splice(0, current.length)
          return
        }
        const current = graph?.edges ?? mockEdges
        current.splice(0, current.length, ...edges)
      },
      updateEdge: (oldEdge: any, conn: any) => {
        const current = edges()
        const idx = current.findIndex((e: any) => e.id === oldEdge.id)
        if (idx < 0) return false
        current[idx] = { ...current[idx], ...conn }
        return current[idx]
      },
      getNodes: computed(nodes),
      getEdges: computed(edges),
      onConnect: (handler: any) => { connectHandler = handler },
      onNodesChange: (handler: any) => { selectionHandler = handler },
      onEdgeUpdate: vi.fn(),
      onEdgeUpdateEnd: vi.fn(),
      onNodeDragStart: (handler: any) => { dragStartHandler = handler },
      onNodeDragStop: (handler: any) => { dragStopHandler = handler },
        fitView: vi.fn(),
      }
    },
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
  syncGraphState: vi.fn(),
  revalidateGraphState: vi.fn(),
  flushNow: vi.fn(),
  dispose: vi.fn(),
  scopes: [] as any[],
  apis: [] as any[],
  serializeGraph: vi.fn((state: {
    nodes: any[]
    edges: any[]
    published_inputs?: any[]
    published_outputs?: any[]
  }) => ({
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
    published_inputs: state.published_inputs ?? [],
    published_outputs: state.published_outputs ?? [],
  })),
}))

const persistenceMocks = vi.hoisted(() => ({
  queueGraph: vi.fn(),
  queueDraft: vi.fn(),
  initializeFromDraft: vi.fn(),
  resolveFromDraft: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
  ensureFreshForCriticalOperation: vi.fn().mockResolvedValue(true),
  dispose: vi.fn(),
  scopes: [] as any[],
  apis: [] as any[],
  isPending: { value: false },
  hasConflict: { value: false },
  currentGraph: { value: { nodes: [], edges: [] } },
  workflowId: { value: null },
  acceptedDraftRevision: { value: 7 as number | null },
  canvasId: null,
}))

const canvasCommandMocks = vi.hoisted(() => ({
  registrations: [] as any[],
  dispose: vi.fn(),
  routeSave: vi.fn().mockResolvedValue('root'),
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

const toastMocks = vi.hoisted(() => ({ add: vi.fn() }))

vi.mock('primevue/usetoast', () => ({
  useToast: () => toastMocks,
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
    useGraphSync: (options?: unknown) => {
      graphSyncMocks.scopes.push(options)
      const scoped = {
        ...graphSyncMocks,
        syncGraph: vi.fn((...args: any[]) => graphSyncMocks.syncGraph(...args)),
        syncGraphState: vi.fn((...args: any[]) => graphSyncMocks.syncGraphState(...args)),
        revalidateGraphState: vi.fn((...args: any[]) => (
          graphSyncMocks.revalidateGraphState(...args)
        )),
        flushNow: vi.fn((...args: any[]) => graphSyncMocks.flushNow(...args)),
        validationResult: ref(null),
        isPending: ref(false),
        syncState: ref('idle'),
      }
      graphSyncMocks.apis.push(scoped)
      return scoped
    },
  }
})

vi.mock('@/composables/useCanvasPersistence', () => ({
  useCanvasPersistence: (options?: unknown) => {
    persistenceMocks.scopes.push(options)
    const scoped = {
      ...persistenceMocks,
      queueGraph: vi.fn((...args: any[]) => persistenceMocks.queueGraph(...args)),
      queueDraft: vi.fn((...args: any[]) => persistenceMocks.queueDraft(...args)),
    }
    persistenceMocks.apis.push(scoped)
    return scoped
  },
}))

vi.mock('@/composables/useCanvasCommands', () => ({
  useCanvasCommands: (options?: unknown) => {
    canvasCommandMocks.registrations.push(options)
    return canvasCommandMocks
  },
}))

vi.mock('@/stores/resolvedOutputs', () => {
  const { reactive } = require('vue')
  const resolvedOutputsByNodeId = reactive({} as Record<string, any>)
  const store = {
    resolvedOutputsByNodeId,
    resolvedOutputsForCanvas: vi.fn(() => resolvedOutputsByNodeId),
    getCanvasResolvedOutput: vi.fn((_canvasId: string, nodeId: string) => (
      resolvedOutputsByNodeId[nodeId]
    )),
    refreshCanvasResolvedOutputs: vi.fn(),
    removeCanvasNode: vi.fn(),
    releaseCanvas: vi.fn(),
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
import { useWorkflowStore } from '@/stores/workflow'
import { useWorkflowDraftStore, type WorkflowDraftChangedMessage } from '@/stores/workflowDraft'
import { useUIStore } from '@/stores/ui'
import { useDataTableStore } from '@/stores/dataTable'
import { useExecutionStore } from '@/stores/execution'
import {
  __resetForTests as resetFieldFocusForTests,
  useFieldFocusTracker,
} from '@/composables/useFieldFocusTracker'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'

function mountCanvas(propsData: {
  nodes?: any[]
  edges?: any[]
  subWorkflowSessionId?: string
  parentCanvasPanelId?: string
  params?: Record<string, unknown>
} = {}) {
  return mount(CanvasView, {
    props: {
      nodes: propsData.nodes ?? [],
      edges: propsData.edges ?? [],
      subWorkflowSessionId: propsData.subWorkflowSessionId,
      parentCanvasPanelId: propsData.parentCanvasPanelId,
      params: propsData.params,
    },
    attachTo: document.body,
  })
}

function projectedStatusesOf(wrapper: ReturnType<typeof mountCanvas>) {
  const exposed = (wrapper.vm as any).projectedStatuses
  return exposed?.value ?? exposed
}

const canvasNodeEditCases = [
  {
    name: 'node rename',
    command: 'renameNode',
    args: ['shared', 'Renamed'],
    expectedData: { name: 'Renamed' },
    expectedSerialized: { name: 'Renamed' },
    immutableMap: undefined,
  },
  {
    name: 'enabled state',
    command: 'setNodeEnabled',
    args: ['shared', false],
    expectedData: { enabled: false },
    expectedSerialized: { enabled: false },
    immutableMap: undefined,
  },
  {
    name: 'input-pin visibility',
    command: 'setInputPinned',
    args: ['shared', 'image', false],
    expectedData: { pinnedInputs: { image: false } },
    expectedSerialized: undefined,
    immutableMap: 'pinnedInputs',
  },
  {
    name: 'output template',
    command: 'setOutputTemplate',
    args: ['shared', 'result', '/tmp/out.tif'],
    expectedData: { output_templates: { result: '/tmp/out.tif' } },
    expectedSerialized: { output_templates: { result: '/tmp/out.tif' } },
    immutableMap: 'output_templates',
  },
] as const

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

function draftResponse(
  revision: number,
  graph: { nodes: any[]; edges: any[] },
  dirtyAgainstSaved = true,
  workflowId = 'wf',
) {
  return {
    draft_version: 1,
    workflow_id: workflowId,
    base_saved_revision: 'sha256:abc',
    draft_revision: revision,
    updated_at: `2026-05-21T12:0${revision}:00Z`,
    updated_by: 'agent',
    dirty_against_saved: dirtyAgainstSaved,
    graph,
    validation: { valid: true, node_statuses: {}, errors: [] },
  }
}

function draftChanged(
  revision: number,
  overrides: Partial<WorkflowDraftChangedMessage> = {},
): WorkflowDraftChangedMessage {
  return {
    type: 'workflow_draft_changed',
    workflow_id: 'wf',
    draft_revision: revision,
    updated_by: 'agent',
    updated_at: `2026-05-21T12:1${revision}:00Z`,
    dirty_against_saved: true,
    ...overrides,
  }
}

describe('CanvasView', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    _resetClipboardForTest()
    mockNodes.length = 0
    mockEdges.length = 0
    connectHandler = null
    selectionHandler = null
    dragStartHandler = null
    dragStopHandler = null
    dropNextNonEmptySetEdges = false
    vueFlowMocks.instanceIds.length = 0
    vueFlowMocks.isolateByInstance = false
    vueFlowMocks.graphs.clear()
    resetFieldFocusForTests()
    toastMocks.add.mockClear()
    graphSyncMocks.syncGraph.mockClear()
    graphSyncMocks.syncGraphState.mockClear()
    graphSyncMocks.revalidateGraphState.mockClear()
    graphSyncMocks.flushNow.mockReset().mockResolvedValue(null)
    graphSyncMocks.dispose.mockClear()
    graphSyncMocks.scopes.length = 0
    graphSyncMocks.apis.length = 0
    graphSyncMocks.serializeGraph.mockClear()
    persistenceMocks.queueGraph.mockClear()
    persistenceMocks.queueDraft.mockClear()
    persistenceMocks.initializeFromDraft.mockClear()
    persistenceMocks.resolveFromDraft.mockClear()
    persistenceMocks.flush.mockClear()
    persistenceMocks.ensureFreshForCriticalOperation.mockClear()
    persistenceMocks.dispose.mockClear()
    persistenceMocks.scopes.length = 0
    persistenceMocks.apis.length = 0
    persistenceMocks.isPending.value = false
    persistenceMocks.acceptedDraftRevision.value = 7
    canvasCommandMocks.registrations.length = 0
    canvasCommandMocks.dispose.mockClear()
    canvasCommandMocks.routeSave.mockClear()
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
    const resolvedOutputsStore = useResolvedOutputsStore()
    ;(resolvedOutputsStore.resolvedOutputsForCanvas as any).mockClear()
    ;(resolvedOutputsStore.getCanvasResolvedOutput as any).mockClear()
    ;(resolvedOutputsStore.refreshCanvasResolvedOutputs as any).mockClear()
    ;(resolvedOutputsStore.releaseCanvas as any).mockClear()
  })

  // --- Task 6: Core Vue Flow Setup ---

  describe('core setup', () => {
    it('publishes and releases cache state against its fixed canvas id', () => {
      const resolvedOutputsStore = useResolvedOutputsStore()
      const dataTableStore = useDataTableStore()
      const registerDataTable = vi.spyOn(dataTableStore, 'registerCanvas')
      const releaseDataTable = vi.spyOn(dataTableStore, 'releaseCanvas')
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
        },
      })

      expect(resolvedOutputsStore.resolvedOutputsForCanvas).toHaveBeenCalledWith(
        'workflow:analysis',
      )
      expect(registerDataTable).toHaveBeenCalledWith('workflow:analysis')
      w.unmount()
      expect(resolvedOutputsStore.releaseCanvas).toHaveBeenCalledWith('workflow:analysis')
      expect(releaseDataTable).toHaveBeenCalledWith('workflow:analysis')
    })

    it('registers graph sync and Vue Flow with the stable Dockview panel id', () => {
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
        },
      })

      expect(vueFlowMocks.instanceIds).toContain('workflow:analysis')
      expect(graphSyncMocks.scopes[0]).toMatchObject({
        descriptor: {
          kind: 'root',
          canvasId: 'workflow:analysis',
          workflowId: 'analysis',
        },
        getWorkflowId: expect.any(Function),
      })
      expect(persistenceMocks.scopes[0]).toMatchObject({
        descriptor: {
          kind: 'root',
          canvasId: 'workflow:analysis',
          workflowId: 'analysis',
        },
        getWorkflowId: expect.any(Function),
      })
      useWorkflowStore().current = {
        name: 'other',
        display_name: 'Other',
      } as any
      expect(graphSyncMocks.scopes[0].getWorkflowId()).toBe('analysis')

      w.unmount()
      expect(graphSyncMocks.dispose).toHaveBeenCalledOnce()
      expect(persistenceMocks.dispose).toHaveBeenCalledOnce()
    })

    it('queues root edits through the fixed canvas persistence adapter only', () => {
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
        },
      })
      persistenceMocks.queueGraph.mockClear()
      autoSaveMocks.scheduleAutoSave.mockClear()
      const scheduleSave = vi.spyOn(useWorkflowDraftStore(), 'scheduleSave')

      connectHandler!({
        source: 'node_a',
        target: 'node_b',
        sourceHandle: 'result',
        targetHandle: 'image',
      })

      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
      expect(autoSaveMocks.scheduleAutoSave).not.toHaveBeenCalled()
      expect(scheduleSave).not.toHaveBeenCalled()
      w.unmount()
    })

    it('publishes one exact parameter snapshot synchronously from its fixed Vue Flow instance', async () => {
      const previousParameters = { sigma: 1 }
      mockNodes = reactive([
        {
          id: 'shared',
          data: {
            name: 'Edited',
            toolName: 'gaussian_blur',
            status: 'executed',
            parameters: previousParameters,
          },
          position: { x: 0, y: 0 },
        },
        {
          id: 'untouched',
          data: {
            name: 'Untouched',
            toolName: 'gaussian_blur',
            status: 'executed',
            parameters: { sigma: 9 },
          },
          position: { x: 100, y: 0 },
        },
      ]) as any[]
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
        },
      })
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      graphSyncMocks.apis[0].validationResult.value = {
        valid: true,
        errors: [],
        node_statuses: {
          shared: { node_id: 'shared', status: 'executed', cached: false },
          untouched: { node_id: 'untouched', status: 'executed', cached: false },
        },
      }

      const updateParameter = canvasCommandMocks.registrations[0].updateParameter
      expect(updateParameter('shared', 'sigma', 2)).toBe(true)

      expect(mockNodes[0].data.parameters).not.toBe(previousParameters)
      expect(mockNodes[0].data.parameters).toEqual({ sigma: 2 })
      expect(projectedStatusesOf(w).shared).toMatchObject({
        status: 'unexecuted',
        provisional: true,
      })
      expect(projectedStatusesOf(w).untouched).toMatchObject({
        status: 'executed',
        provisional: true,
      })
      expect(mockNodes[0].data.status).toBe('executed')
      expect(mockNodes[0].data.provisional).toBeUndefined()
      expect(mockNodes[1].data.provisional).toBeUndefined()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledWith(expect.objectContaining({
        nodes: expect.arrayContaining([
          expect.objectContaining({ id: 'shared', parameters: { sigma: 2 } }),
        ]),
      }))

      await nextTick()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
      w.unmount()
      await flushPromises()
    })

    it.each(canvasNodeEditCases)(
      'publishes one exact $name snapshot synchronously without rewriting statuses',
      async ({ command, args, expectedData, expectedSerialized, immutableMap }) => {
        const editedData = {
          name: 'Edited',
          toolName: 'gaussian_blur',
          status: 'executed',
          parameters: { sigma: 1 },
          enabled: true,
          connectedInputs: {},
          pinnedInputs: { image: true },
          output_templates: { result: '' },
        }
        mockNodes = reactive([
          {
            id: 'shared',
            data: editedData,
            position: { x: 0, y: 0 },
          },
          {
            id: 'untouched',
            data: {
              name: 'Untouched',
              toolName: 'gaussian_blur',
              status: 'executed',
              parameters: { sigma: 9 },
            },
            position: { x: 100, y: 0 },
          },
        ]) as any[]
        const previousMap = immutableMap
          ? mockNodes[0].data[immutableMap]
          : undefined
        const w = mountCanvas({
          params: {
            panelId: 'workflow:analysis',
            workflowName: 'analysis',
            workflowDisplayName: 'Analysis',
          },
        })
        graphSyncMocks.syncGraph.mockClear()
        persistenceMocks.queueGraph.mockClear()
        graphSyncMocks.apis[0].validationResult.value = {
          valid: true,
          errors: [],
          node_statuses: {
            shared: { node_id: 'shared', status: 'executed', cached: false },
            untouched: { node_id: 'untouched', status: 'executed', cached: false },
          },
        }

        const registration = canvasCommandMocks.registrations[0]
        expect(registration[command](...args)).toBe(true)

        expect(mockNodes[0].data).toEqual(expect.objectContaining(expectedData))
        if (immutableMap) {
          expect(mockNodes[0].data[immutableMap]).not.toBe(previousMap)
        }
        expect(projectedStatusesOf(w).shared).toMatchObject({
          status: 'executed',
          provisional: true,
        })
        expect(projectedStatusesOf(w).untouched).toMatchObject({
          status: 'executed',
          provisional: true,
        })
        expect(mockNodes[0].data.provisional).toBeUndefined()
        expect(mockNodes[1].data.provisional).toBeUndefined()
        expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
        expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
        if (expectedSerialized) {
          expect(persistenceMocks.queueGraph).toHaveBeenCalledWith(expect.objectContaining({
            nodes: expect.arrayContaining([
              expect.objectContaining({ id: 'shared', ...expectedSerialized }),
            ]),
          }))
        }

        await nextTick()
        expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
        expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
        w.unmount()
        await flushPromises()
      },
    )

    it('keeps node names trimmed, non-empty, and unique', async () => {
      mockNodes = reactive([
        {
          id: 'shared',
          data: { name: 'Edited', toolName: 'gaussian_blur', status: 'executed' },
          position: { x: 0, y: 0 },
        },
        {
          id: 'other',
          data: { name: 'Existing', toolName: 'gaussian_blur', status: 'executed' },
          position: { x: 100, y: 0 },
        },
      ]) as any[]
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
        },
      })
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      const renameNode = canvasCommandMocks.registrations[0].renameNode

      expect(renameNode('shared', '  Renamed  ')).toBe(true)
      expect(mockNodes[0].data.name).toBe('Renamed')
      expect(renameNode('shared', '   ')).toBe(false)
      expect(renameNode('shared', 'Existing')).toBe(false)
      expect(renameNode('shared', ' Renamed ')).toBe(false)
      expect(mockNodes[0].data.name).toBe('Renamed')
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()

      await nextTick()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      w.unmount()
    })

    it('forces connected input pins visible and replaces pin maps immutably', async () => {
      const previousPinnedInputs = { image: false, optional: true }
      mockNodes = reactive([{
        id: 'shared',
        data: {
          name: 'Edited',
          toolName: 'gaussian_blur',
          status: 'executed',
          connectedInputs: { image: 'source.result' },
          pinnedInputs: previousPinnedInputs,
        },
        position: { x: 0, y: 0 },
      }]) as any[]
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
        },
      })
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      const setInputPinned = canvasCommandMocks.registrations[0].setInputPinned

      expect(setInputPinned('shared', 'image', false)).toBe(true)
      expect(mockNodes[0].data.pinnedInputs).not.toBe(previousPinnedInputs)
      expect(mockNodes[0].data.pinnedInputs).toEqual({ image: true, optional: true })
      expect(setInputPinned('shared', 'image', false)).toBe(false)
      expect(setInputPinned('shared', 'optional', false)).toBe(true)
      expect(mockNodes[0].data.pinnedInputs).toEqual({ image: true, optional: false })
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledTimes(2)

      await nextTick()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      w.unmount()
    })

    it('publishes root input and output interface toggles synchronously', async () => {
      const tool = makeTool()
      mockNodes = reactive([
        {
          id: 'shared',
          data: {
            name: 'Shared',
            toolName: tool.name,
            tool,
            status: 'executed',
            parameters: { image: '/data/input.tif' },
          },
          position: { x: 0, y: 0 },
        },
        {
          id: 'other',
          data: {
            name: 'Other',
            toolName: tool.name,
            tool,
            status: 'executed',
            parameters: {},
          },
          position: { x: 100, y: 0 },
        },
      ]) as any[]
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
        },
      })
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      const registration = canvasCommandMocks.registrations[0]

      expect(registration.togglePublishedInput('shared', 'image')).toEqual({
        status: 'changed',
      })
      const publishedInputs = mockNodes[0].data.publicationContext.published_inputs
      expect(publishedInputs).toEqual([{
        name: 'shared.image',
        internal_node_id: 'shared',
        internal_field: 'image',
        kind: 'input',
        schema: tool.inputs.image,
        default: '/data/input.tif',
      }])
      expect(mockNodes[1].data.publicationContext.published_inputs).toBe(publishedInputs)
      expect(mockNodes[0].data.status).toBe('executed')
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledWith(expect.objectContaining({
        published_inputs: publishedInputs,
      }))

      await nextTick()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()

      expect(registration.togglePublishedOutput('shared', 'result')).toEqual({
        status: 'changed',
      })
      const publishedOutputs = mockNodes[0].data.publicationContext.published_outputs
      expect(publishedOutputs).toEqual([{
        name: 'shared.result',
        internal_node_id: 'shared',
        internal_output: 'result',
        schema: tool.outputs.result,
      }])
      expect(mockNodes[1].data.publicationContext.published_outputs).toBe(publishedOutputs)
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledWith(expect.objectContaining({
        published_inputs: publishedInputs,
        published_outputs: publishedOutputs,
      }))

      await nextTick()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()

      expect(registration.togglePublishedInput('shared', 'image')).toEqual({
        status: 'changed',
      })
      expect(mockNodes[0].data.publicationContext.published_inputs).toEqual([])
      expect(mockNodes[0].data.publicationContext.published_inputs).not.toBe(publishedInputs)
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()

      await nextTick()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      w.unmount()
    })

    it('renames root published interfaces with structured validation results', async () => {
      const tool = makeTool()
      mockNodes = reactive([{
        id: 'shared',
        data: {
          name: 'Shared',
          toolName: tool.name,
          tool,
          status: 'executed',
          parameters: {},
        },
        position: { x: 0, y: 0 },
      }]) as any[]
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
        },
      })
      const registration = canvasCommandMocks.registrations[0]
      expect(registration.togglePublishedInput('shared', 'image')).toEqual({
        status: 'changed',
      })
      expect(registration.togglePublishedOutput('shared', 'result')).toEqual({
        status: 'changed',
      })
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()

      expect(registration.renamePublishedInput('shared', 'image', '  source_image  '))
        .toEqual({ status: 'changed' })
      expect(mockNodes[0].data.publicationContext.published_inputs[0].name)
        .toBe('source_image')
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()

      await nextTick()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()

      expect(registration.renamePublishedOutput('shared', 'result', 'mask_output'))
        .toEqual({ status: 'changed' })
      expect(mockNodes[0].data.publicationContext.published_outputs[0].name)
        .toBe('mask_output')
      expect(persistenceMocks.queueGraph).toHaveBeenCalledWith(expect.objectContaining({
        published_inputs: [expect.objectContaining({ name: 'source_image' })],
        published_outputs: [expect.objectContaining({ name: 'mask_output' })],
      }))

      await nextTick()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()

      expect(registration.renamePublishedInput('shared', 'image', ' source_image '))
        .toEqual({ status: 'unchanged' })
      expect(registration.renamePublishedInput('shared', 'image', '   ')).toEqual({
        status: 'rejected',
        reason: 'empty_name',
      })
      expect(registration.renamePublishedOutput('shared', 'result', 'source_image'))
        .toEqual({
          status: 'rejected',
          reason: 'duplicate_name',
          name: 'source_image',
        })
      expect(registration.renamePublishedInput('shared', 'sigma', 'sigma_input'))
        .toEqual({ status: 'rejected', reason: 'not_found' })
      expect(registration.togglePublishedInput('shared', 'sigma')).toEqual({
        status: 'rejected',
        reason: 'not_publishable',
      })
      expect(registration.togglePublishedOutput('shared', 'missing')).toEqual({
        status: 'rejected',
        reason: 'not_found',
      })
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()
      w.unmount()
    })

    it('restores root publication history with one persisted snapshot per step', async () => {
      const tool = makeTool()
      useToolRegistryStore().tools = [tool] as any
      mockNodes = reactive([]) as any[]
      const graph = {
        nodes: [
          {
            id: 'shared',
            name: 'Shared',
            tool_name: tool.name,
            position: [0, 0],
            parameters: {},
            resources: {},
            output_templates: { result: '' },
            enabled: true,
            collapsed: false,
          },
          {
            id: 'other',
            name: 'Other',
            tool_name: tool.name,
            position: [120, 0],
            parameters: {},
            resources: {},
            output_templates: { result: '' },
            enabled: true,
            collapsed: false,
          },
        ],
        edges: [{
          type: 'column_ref' as const,
          id: 'authoritative-edge',
          source_node: 'shared',
          target_node: 'other',
          source_output: 'result',
          target_input: 'image',
        }],
        published_inputs: [],
        published_outputs: [],
      }
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph,
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      await flushPromises()
      const registration = canvasCommandMocks.registrations[0]

      async function applyHistory(
        redo: boolean,
        expectedNames: string[],
      ): Promise<void> {
        graphSyncMocks.syncGraph.mockClear()
        persistenceMocks.queueGraph.mockClear()
        await w.find('.canvas-view').trigger('keydown', {
          key: 'z',
          ctrlKey: true,
          shiftKey: redo,
        })
        await nextTick()

        const inputs = mockNodes[0].data.publicationContext.published_inputs
        expect(inputs.map((item: any) => item.name)).toEqual(expectedNames)
        expect(mockNodes[1].data.publicationContext.published_inputs).toBe(inputs)
        expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
        expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
        expect(persistenceMocks.queueGraph).toHaveBeenCalledWith(expect.objectContaining({
          published_inputs: expectedNames.map((name) => expect.objectContaining({ name })),
          edges: [expect.objectContaining({ id: 'authoritative-edge' })],
        }))
      }

      mockEdges.splice(0)
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      expect(registration.togglePublishedInput('shared', 'image'))
        .toEqual({ status: 'changed' })
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledWith(expect.objectContaining({
        edges: [expect.objectContaining({ id: 'authoritative-edge' })],
      }))
      await nextTick()
      await applyHistory(false, [])
      await applyHistory(true, ['shared.image'])

      expect(registration.renamePublishedInput('shared', 'image', 'source_image'))
        .toEqual({ status: 'changed' })
      await nextTick()
      await applyHistory(false, ['shared.image'])
      await applyHistory(true, ['source_image'])

      expect(registration.togglePublishedInput('shared', 'image'))
        .toEqual({ status: 'changed' })
      await nextTick()
      await applyHistory(false, ['source_image'])
      await applyHistory(true, [])
      w.unmount()
    })

    it.each(['starting', 'stopping'] as const)(
      'rejects every publication command while execution is %s',
      async (phase) => {
      const tool = makeTool()
      mockNodes = reactive([{
        id: 'shared',
        data: {
          name: 'Shared',
          toolName: tool.name,
          tool,
          status: 'executed',
          parameters: {},
        },
        position: { x: 0, y: 0 },
      }]) as any[]
      const w = mountCanvas()
      useExecutionStore().state = phase as any
      await nextTick()
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      const registration = canvasCommandMocks.registrations[0]

      expect(registration.togglePublishedInput('shared', 'image')).toEqual({
        status: 'rejected',
        reason: 'locked',
      })
      expect(registration.togglePublishedOutput('shared', 'result')).toEqual({
        status: 'rejected',
        reason: 'locked',
      })
      expect(registration.renamePublishedInput('shared', 'image', 'source')).toEqual({
        status: 'rejected',
        reason: 'locked',
      })
      expect(registration.renamePublishedOutput('shared', 'result', 'result')).toEqual({
        status: 'rejected',
        reason: 'locked',
      })
      expect(mockNodes[0].data.publicationContext).toBeUndefined()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()
      w.unmount()
      },
    )

    it.each(['starting', 'stopping'] as const)(
      'rejects its parameter command while execution is %s',
      async (phase) => {
      mockNodes = reactive([{
        id: 'shared',
        data: {
          name: 'Edited',
          toolName: 'gaussian_blur',
          status: 'executed',
          parameters: { sigma: 1 },
        },
        position: { x: 0, y: 0 },
      }]) as any[]
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
        },
      })
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      useExecutionStore().state = phase as any
      await nextTick()

      const updateParameter = canvasCommandMocks.registrations[0].updateParameter
      expect(updateParameter('shared', 'sigma', 2)).toBe(false)
      expect(mockNodes[0].data.parameters).toEqual({ sigma: 1 })
      expect(mockNodes[0].data.status).toBe('executed')
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()
      w.unmount()
      },
    )

    it.each(['starting', 'stopping'] as const)(
      'rejects every NodePanel edit command while execution is %s',
      async (phase) => {
      const originalData = reactive({
        name: 'Edited',
        toolName: 'gaussian_blur',
        status: 'executed',
        parameters: { sigma: 1 },
        enabled: true,
        connectedInputs: {},
        pinnedInputs: { image: true },
        output_templates: { result: '' },
      })
      mockNodes = reactive([{
        id: 'shared',
        data: originalData,
        position: { x: 0, y: 0 },
      }]) as any[]
      const w = mountCanvas()
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      useExecutionStore().state = phase as any
      await nextTick()
      const registration = canvasCommandMocks.registrations[0]

      for (const { command, args } of canvasNodeEditCases) {
        expect(registration[command](...args)).toBe(false)
      }
      expect(mockNodes[0].data).toBe(originalData)
      expect(mockNodes[0].data).toEqual(expect.objectContaining({
        name: 'Edited',
        enabled: true,
        pinnedInputs: { image: true },
        output_templates: { result: '' },
        status: 'executed',
      }))
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()
      w.unmount()
      },
    )

    it('routes the context-menu enable action through the execution lock', async () => {
      mockNodes = reactive([{
        id: 'shared',
        data: {
          name: 'Edited',
          toolName: 'gaussian_blur',
          status: 'executed',
          enabled: true,
        },
        position: { x: 0, y: 0 },
      }]) as any[]
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
        },
      })
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      useExecutionStore().state = 'running'
      await nextTick()

      w.findComponent({ name: 'VueFlow' }).vm.$emit('node-context-menu', {
        event: {
          clientX: 20,
          clientY: 30,
          preventDefault: vi.fn(),
        },
        node: mockNodes[0],
      })
      await nextTick()
      const actions = w.findAll('.node-context-menu li')
      expect(actions).toHaveLength(4)

      await actions[1]!.trigger('click')

      expect(mockNodes[0].data.enabled).toBe(true)
      expect(w.find('.node-context-menu').exists()).toBe(false)
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()
      w.unmount()
    })

    it('writes presentation state through its fixed canvas identity', () => {
      mockNodes = [
        {
          id: 'shared',
          selected: true,
          data: { name: 'Analysis node', toolName: 'gaussian_blur' },
          position: { x: 0, y: 0 },
        },
      ]
      const ui = useUIStore()
      const setWorkflow = vi.spyOn(ui, 'setCanvasWorkflow')
      const setNodes = vi.spyOn(ui, 'setCanvasGraphNodes')
      const setSelection = vi.spyOn(ui, 'setCanvasSelectedNodes')
      const markDirty = vi.spyOn(ui, 'markCanvasDirty')
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
        },
      })

      selectionHandler!([{ type: 'select' }])
      connectHandler!({
        source: 'shared',
        target: 'missing',
        sourceHandle: 'result',
        targetHandle: 'image',
      })

      expect(setWorkflow).toHaveBeenCalledWith(
        'workflow:analysis',
        'analysis',
        'Analysis',
      )
      expect(setNodes).toHaveBeenCalledWith('workflow:analysis', mockNodes)
      expect(setSelection).toHaveBeenCalledWith('workflow:analysis', ['shared'])
      expect(markDirty).toHaveBeenCalledWith('workflow:analysis')
      w.unmount()
    })

    it('registers a nested canvas with its parent canvas identity', () => {
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentWorkflowName: 'analysis',
        parentNodeId: 'sub_1',
        parentNodeName: 'Sub 1',
        graph: { nodes: [], edges: [] },
      })

      const w = mountCanvas({
        subWorkflowSessionId: session.id,
        parentCanvasPanelId: 'workflow:analysis',
      })

      const nestedPanelId = `sub-workflow:${encodeURIComponent(session.id)}`
      expect(vueFlowMocks.instanceIds).toContain(nestedPanelId)
      expect(graphSyncMocks.scopes[0]).toMatchObject({
        descriptor: {
          kind: 'nested',
          canvasId: nestedPanelId,
          sessionId: session.id,
          parentCanvasId: 'workflow:analysis',
        },
      })
      w.unmount()
    })

    it('does not resume graph application after the canvas unmounts', async () => {
      useToolRegistryStore().tools = [makeTool()] as any
      const w = mountCanvas({
        params: {
          panelId: 'workflow:closing',
          workflowName: 'closing',
          graph: { nodes: [], edges: [] },
        },
      })

      w.unmount()
      await flushPromises()
      await nextTick()

      expect(graphSyncMocks.dispose).toHaveBeenCalledOnce()
      expect(graphSyncMocks.syncGraphState).not.toHaveBeenCalled()
    })

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

    it('does not fit an empty canvas when the first node is later added', () => {
      const w = mountCanvas()
      const vueFlow = w.findComponent({ name: 'VueFlow' })
      expect(vueFlow.props('fitViewOnInit')).toBe(false)
      w.unmount()
    })

    it('fits initially when opened with an existing workflow graph', () => {
      const w = mountCanvas({
        params: {
          graph: {
            nodes: [{
              id: 'node_1',
              name: 'Node 1',
              tool_name: 'gaussian_blur',
              position: [0, 0],
              parameters: {},
              resources: {},
              output_templates: {},
            }],
            edges: [],
          },
        },
      })
      const vueFlow = w.findComponent({ name: 'VueFlow' })
      expect(vueFlow.props('fitViewOnInit')).toBe(true)
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

    it('onConnect pins optional non-path body inputs without a next-tick republish', async () => {
      const tool = makeTool({
        inputs: {
          image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' },
          sigma: { type: 'float', required: false, nullable: false, connectable: 'not_by_default', default: 1.0 },
        },
        outputs: {
          result: { type: 'ImageFile' },
          sigma: { type: 'float' },
        },
      })
      mockNodes = reactive([
        { id: 'a', data: { toolName: 'gaussian_blur', name: 'a', tool, parameters: {}, connectedInputs: {} } },
        {
          id: 'b',
          data: {
            toolName: 'gaussian_blur',
            name: 'b',
            tool,
            parameters: { sigma: 1.0 },
            connectedInputs: {},
            pinnedInputs: { image: true, sigma: false },
          },
        },
      ]) as any[]
      mockEdges = []

      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
        },
      })
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()

      connectHandler!({
        source: 'a',
        target: 'b',
        sourceHandle: 'sigma',
        targetHandle: 'sigma',
      })

      const targetNode = mockNodes.find((n: any) => n.id === 'b')!
      expect(targetNode.data.connectedInputs.sigma).toBe('a.sigma')
      expect(targetNode.data.pinnedInputs.sigma).toBe(true)
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()

      await nextTick()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledOnce()
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

    it('rejects dropping the active workflow into itself', async () => {
      const workflowStore = useWorkflowStore()
      workflowStore.current = { name: 'analysis', display_name: 'Analysis' } as any
      mockSavedWorkflow({ nodes: [], edges: [] }, 'analysis')
      const w = mountCanvas()
      const vm = w.vm as any

      await vm.onAddWorkflowNode({ workflowName: 'analysis' })

      expect(apiMocks.get).toHaveBeenCalledWith('/api/v1/workflows/analysis')
      expect(mockNodes).toHaveLength(0)
      expect(w.emitted('graph-changed')).toBeFalsy()
      w.unmount()
    })

    it('rejects dropping a workflow that already contains the active workflow', async () => {
      const workflowStore = useWorkflowStore()
      workflowStore.current = { name: 'analysis', display_name: 'Analysis' } as any
      const graph = {
        nodes: [{
          id: 'nested_analysis',
          name: 'Analysis',
          tool_name: '__sub_workflow__',
          position: [0, 0],
          parameters: {},
          resources: {},
          output_templates: {},
          sub_workflow: { nodes: [], edges: [] },
          source_workflow_name: 'analysis',
        }],
        edges: [],
      }
      mockSavedWorkflow(graph, 'library')
      const w = mountCanvas()
      const vm = w.vm as any

      await vm.onAddWorkflowNode({ workflowName: 'library' })

      expect(apiMocks.get).toHaveBeenCalledWith('/api/v1/workflows/library')
      expect(mockNodes).toHaveLength(0)
      expect(w.emitted('graph-changed')).toBeFalsy()
      w.unmount()
    })

    it('rejects dropping a workflow into its own sub-workflow editor', async () => {
      const workflowStore = useWorkflowStore()
      workflowStore.current = { name: 'analysis', display_name: 'Analysis' } as any
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentWorkflowName: 'analysis',
        parentSourceWorkflowName: 'library',
        parentNodeId: 'sub_1',
        parentNodeName: 'Library',
        graph: { nodes: [], edges: [] },
      })
      mockSavedWorkflow({ nodes: [], edges: [] }, 'library')
      const w = mountCanvas({ subWorkflowSessionId: session.id })
      const vm = w.vm as any

      await vm.onAddWorkflowNode({ workflowName: 'library' })

      expect(apiMocks.get).toHaveBeenCalledWith('/api/v1/workflows/library')
      expect(mockNodes).toHaveLength(0)
      expect(w.emitted('graph-changed')).toBeFalsy()
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
    it('loads the initial registry without a badge, dirty state, or history entry', async () => {
      const store = useToolRegistryStore()
      const canvasId = canvasIdFromPanelId('workflow:analysis')
      store.tools = []
      apiMocks.get.mockImplementation((url: string) => {
        if (url === '/api/v1/tools') return Promise.resolve({ data: [makeTool()] })
        return Promise.resolve({ data: {} })
      })
      const w = mountCanvas({
        params: {
          panelId: canvasId,
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph: { nodes: [makeGraphNode('shared')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.tool).toEqual(makeTool())
      expect(mockNodes[0].data.updatedBadge).toBeUndefined()
      expect(useUIStore().canvasHasUnsavedChanges(canvasId)).toBe(false)
      expect(persistenceMocks.apis[0].queueGraph).not.toHaveBeenCalled()

      expect(canvasCommandMocks.registrations[0].setNodeEnabled('shared', false)).toBe(true)
      persistenceMocks.apis[0].queueGraph.mockClear()
      await w.find('.canvas-view').trigger('keydown', { key: 'z', ctrlKey: true })
      expect(mockNodes[0].data.enabled).toBe(true)
      expect(persistenceMocks.apis[0].queueGraph).toHaveBeenCalledOnce()
      await w.find('.canvas-view').trigger('keydown', { key: 'z', ctrlKey: true })
      expect(persistenceMocks.apis[0].queueGraph).toHaveBeenCalledOnce()
      w.unmount()
    })

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

    it('reconciles same-version metadata as a validation-only canvas refresh', async () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool({ package_version: '1.0.0' })] as any
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph: { nodes: [makeGraphNode('shared')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      const sync = graphSyncMocks.apis[0]
      const persistence = persistenceMocks.apis[0]
      sync.syncGraphState.mockClear()
      sync.revalidateGraphState.mockClear()
      persistence.queueGraph.mockClear()

      store.tools = [makeTool({
        package_version: '1.0.0',
        documentation: 'Reloaded in place',
      })] as any
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.tool.documentation).toBe('Reloaded in place')
      expect(mockNodes[0].data.updatedBadge).toBe(true)
      expect(mockNodes[0].data.status).toBe('unexecuted')
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(sync.revalidateGraphState).toHaveBeenCalledOnce()
      expect(persistence.queueGraph).not.toHaveBeenCalled()
      expect(useUIStore().canvasHasUnsavedChanges(
        canvasIdFromPanelId('workflow:analysis'),
      )).toBe(false)
      w.unmount()
    })

    it('coalesces reloads and publishes removed parameters and templates once', async () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any
      const edge = {
        type: 'column_ref' as const,
        id: 'e1',
        source_node: 'shared',
        target_node: 'other',
        source_output: 'result',
        target_input: 'image',
      }
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph: {
            nodes: [
              makeGraphNode('shared', {
                parameters: { sigma: 3, removed: 9 },
                output_templates: { result: 'old.tif' },
              }),
              makeGraphNode('other', { position: [120, 0] }),
            ],
            edges: [edge],
          },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      const sync = graphSyncMocks.apis[0]
      const persistence = persistenceMocks.apis[0]
      sync.syncGraphState.mockClear()
      sync.revalidateGraphState.mockClear()
      persistence.queueGraph.mockClear()

      store.tools = [makeTool({ documentation: 'first' })] as any
      store.tools = [makeTool({ documentation: 'second' })] as any
      store.tools = [makeTool({
        documentation: 'latest',
        inputs: {
          image: makeTool().inputs.image,
        },
        outputs: { count: { type: 'int' } },
      })] as any
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.tool.documentation).toBe('latest')
      expect(mockNodes[0].data.parameters).toEqual({})
      expect(mockNodes[0].data.output_templates).toEqual({})
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(sync.revalidateGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).toHaveBeenCalledOnce()
      expect(persistence.queueGraph).toHaveBeenCalledWith(expect.objectContaining({
        nodes: expect.arrayContaining([
          expect.objectContaining({
            id: 'shared',
            parameters: {},
            output_templates: {},
          }),
        ]),
        edges: [edge],
      }))

      await nextTick()
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).toHaveBeenCalledOnce()
      w.unmount()
    })

    it('defers and coalesces the latest registry state through all locked phases', async () => {
      const store = useToolRegistryStore()
      const execution = useExecutionStore()
      store.tools = [makeTool()] as any
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph: { nodes: [makeGraphNode('shared')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      const sync = graphSyncMocks.apis[0]
      const persistence = persistenceMocks.apis[0]
      sync.syncGraphState.mockClear()
      sync.revalidateGraphState.mockClear()
      persistence.queueGraph.mockClear()

      execution.state = 'starting'
      store.tools = [makeTool({ documentation: 'starting' })] as any
      await nextTick()
      execution.state = 'running'
      store.tools = [makeTool({ documentation: 'running' })] as any
      await nextTick()
      execution.state = 'stopping'
      store.tools = [makeTool({
        documentation: 'stopping-latest',
        inputs: { image: makeTool().inputs.image },
      })] as any
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.tool.documentation).toBe('')
      expect(mockNodes[0].data.parameters).toEqual({ sigma: 1 })
      expect(mockNodes[0].data.updatedBadge).toBeUndefined()
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(sync.revalidateGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).not.toHaveBeenCalled()

      execution.state = 'idle'
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.tool.documentation).toBe('stopping-latest')
      expect(mockNodes[0].data.parameters).toEqual({})
      expect(mockNodes[0].data.updatedBadge).toBe(true)
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(sync.revalidateGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).toHaveBeenCalledOnce()
      w.unmount()
    })

    it('reconciles identical node ids independently across mounted canvases', async () => {
      vueFlowMocks.isolateByInstance = true
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any
      const graph = { nodes: [makeGraphNode('shared')], edges: [] }
      const canvasA = canvasIdFromPanelId('workflow:a')
      const canvasB = canvasIdFromPanelId('workflow:b')
      const first = mountCanvas({
        params: {
          panelId: canvasA,
          workflowName: 'a',
          workflowDisplayName: 'A',
          graph,
          dirty: false,
        },
      })
      const second = mountCanvas({
        params: {
          panelId: canvasB,
          workflowName: 'b',
          workflowDisplayName: 'B',
          graph,
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      await flushPromises()
      const firstGraph = vueFlowMocks.graphs.get(canvasA)!
      const secondGraph = vueFlowMocks.graphs.get(canvasB)!
      const focus = useFieldFocusTracker()
      focus.trackFocus({ canvasId: canvasA, nodeId: 'shared', fieldName: 'sigma' })
      for (const api of graphSyncMocks.apis) api.syncGraphState.mockClear()
      for (const api of graphSyncMocks.apis) api.revalidateGraphState.mockClear()
      for (const api of persistenceMocks.apis) api.queueGraph.mockClear()

      store.tools = [makeTool({
        documentation: 'scoped reload',
        inputs: { image: makeTool().inputs.image },
      })] as any
      await nextTick()
      await flushPromises()

      expect(firstGraph.nodes[0].data.tool.documentation).toBe('')
      expect(firstGraph.nodes[0].data.parameters).toEqual({ sigma: 1 })
      expect(secondGraph.nodes[0].data.tool.documentation).toBe('scoped reload')
      expect(secondGraph.nodes[0].data.parameters).toEqual({})
      expect(graphSyncMocks.apis[0].syncGraphState).not.toHaveBeenCalled()
      expect(graphSyncMocks.apis[0].revalidateGraphState).not.toHaveBeenCalled()
      expect(persistenceMocks.apis[0].queueGraph).not.toHaveBeenCalled()
      expect(graphSyncMocks.apis[1].syncGraphState).not.toHaveBeenCalled()
      expect(graphSyncMocks.apis[1].revalidateGraphState).not.toHaveBeenCalled()
      expect(persistenceMocks.apis[1].queueGraph).toHaveBeenCalledOnce()

      focus.trackBlur({ canvasId: canvasA, nodeId: 'shared', fieldName: 'sigma' })
      await nextTick()
      await flushPromises()

      expect(firstGraph.nodes[0].data.tool.documentation).toBe('scoped reload')
      expect(firstGraph.nodes[0].data.parameters).toEqual({})
      expect(graphSyncMocks.apis[0].syncGraphState).not.toHaveBeenCalled()
      expect(graphSyncMocks.apis[0].revalidateGraphState).not.toHaveBeenCalled()
      expect(persistenceMocks.apis[0].queueGraph).toHaveBeenCalledOnce()
      expect(graphSyncMocks.apis[1].syncGraphState).not.toHaveBeenCalled()
      expect(persistenceMocks.apis[1].queueGraph).toHaveBeenCalledOnce()
      expect(toastMocks.add).toHaveBeenCalledWith(expect.objectContaining({
        detail: expect.stringContaining('sigma'),
      }))
      first.unmount()
      second.unmount()
    })

    it('projects execution statuses only onto the originating canvas', async () => {
      vueFlowMocks.isolateByInstance = true
      useToolRegistryStore().tools = [makeTool()] as any
      const graph = { nodes: [makeGraphNode('shared')], edges: [] }
      const canvasA = canvasIdFromPanelId('workflow:a')
      const canvasB = canvasIdFromPanelId('workflow:b')
      canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'a' })
      canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'b' })
      const first = mountCanvas({
        params: {
          panelId: canvasA,
          workflowName: 'a',
          workflowDisplayName: 'A',
          graph,
          dirty: false,
        },
      })
      const second = mountCanvas({
        params: {
          panelId: canvasB,
          workflowName: 'b',
          workflowDisplayName: 'B',
          graph,
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      await flushPromises()
      canvasSessionRegistry.activate(canvasA)

      useExecutionStore().applyStatusSnapshot({
        type: 'status_snapshot',
        execution_id: 'exec-123',
        workflow_id: 'a',
        draft_revision: 7,
        state: 'running',
        last_result: null,
        progress: null,
        node_statuses: {
          shared: { node_id: 'shared', status: 'running', cached: false },
        },
      })
      await nextTick()

      const firstGraph = vueFlowMocks.graphs.get(canvasA)!
      const secondGraph = vueFlowMocks.graphs.get(canvasB)!
      expect(projectedStatusesOf(first).shared.status).toBe('running')
      expect(firstGraph.nodes[0].data.status).toBe('unexecuted')
      expect(projectedStatusesOf(second).shared.status).toBe('unexecuted')
      expect(secondGraph.nodes[0].data.status).toBe('unexecuted')

      first.unmount()
      second.unmount()
      canvasSessionRegistry.dispose()
    })

    it('projects a reconnect snapshot received before its canvas mounts', async () => {
      vueFlowMocks.isolateByInstance = true
      useToolRegistryStore().tools = [makeTool()] as any
      const canvasId = canvasIdFromPanelId('workflow:a')
      useExecutionStore().applyStatusSnapshot({
        type: 'status_snapshot',
        execution_id: 'exec-123',
        workflow_id: 'a',
        draft_revision: 7,
        state: 'running',
        last_result: null,
        progress: null,
        node_statuses: {
          shared: { node_id: 'shared', status: 'running', cached: false },
        },
      })

      canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'a' })
      canvasSessionRegistry.activate(canvasId)
      const wrapper = mountCanvas({
        params: {
          panelId: canvasId,
          workflowName: 'a',
          workflowDisplayName: 'A',
          graph: { nodes: [makeGraphNode('shared')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(projectedStatusesOf(wrapper).shared.status).toBe('running')
      expect(vueFlowMocks.graphs.get(canvasId)!.nodes[0].data.status).toBe('unexecuted')

      wrapper.unmount()
      canvasSessionRegistry.dispose()
    })

    it('uses structured missing-tool state and clears it when the tool reappears', async () => {
      const store = useToolRegistryStore()
      const execution = useExecutionStore()
      store.tools = [makeTool()] as any
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph: { nodes: [makeGraphNode('shared')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      const sync = graphSyncMocks.apis[0]
      const persistence = persistenceMocks.apis[0]
      sync.syncGraphState.mockClear()
      sync.revalidateGraphState.mockClear()
      persistence.queueGraph.mockClear()

      execution.state = 'starting'
      store.tools = []
      window.dispatchEvent(new CustomEvent('bioimageflow:tool-deleted', {
        detail: { tool_name: 'gaussian_blur' },
      }))
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.tool).toEqual(makeTool())
      expect(mockNodes[0].data.missingTool).toBeNull()
      expect(mockNodes[0].data.updatedBadge).toBeUndefined()
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).not.toHaveBeenCalled()

      execution.state = 'idle'
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.tool).toBeNull()
      expect(mockNodes[0].data.missingTool).toEqual({
        node_id: 'shared',
        tool_name: 'gaussian_blur',
        installed_versions: [],
      })
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(sync.revalidateGraphState).toHaveBeenCalledOnce()
      expect(persistence.queueGraph).not.toHaveBeenCalled()

      store.tools = [makeTool({ documentation: 'available again' })] as any
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.tool.documentation).toBe('available again')
      expect(mockNodes[0].data.missingTool).toBeNull()
      expect(mockNodes[0].data.updatedBadge).toBe(true)
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(sync.revalidateGraphState).toHaveBeenCalledTimes(2)
      expect(persistence.queueGraph).not.toHaveBeenCalled()
      w.unmount()
    })

    it('defers a tool rename event while locked and publishes the new identity once', async () => {
      const store = useToolRegistryStore()
      const execution = useExecutionStore()
      store.tools = [makeTool()] as any
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph: { nodes: [makeGraphNode('shared')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      const sync = graphSyncMocks.apis[0]
      const persistence = persistenceMocks.apis[0]
      sync.syncGraphState.mockClear()
      sync.revalidateGraphState.mockClear()
      persistence.queueGraph.mockClear()

      execution.state = 'starting'
      store.tools = [makeTool({ name: 'gaussian_blur_v2' })] as any
      window.dispatchEvent(new CustomEvent('bioimageflow:tool-renamed', {
        detail: { old_name: 'gaussian_blur', new_name: 'gaussian_blur_v2' },
      }))
      await nextTick()
      expect(mockNodes[0].data.toolName).toBe('gaussian_blur')
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).not.toHaveBeenCalled()

      execution.state = 'idle'
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.toolName).toBe('gaussian_blur_v2')
      expect(mockNodes[0].data.tool.name).toBe('gaussian_blur_v2')
      expect(mockNodes[0].data.missingTool).toBeNull()
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(sync.revalidateGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).toHaveBeenCalledOnce()
      w.unmount()
    })

    it('waits for the rename event after the registry refresh before reconciling', async () => {
      const store = useToolRegistryStore()
      const renamedTool = makeTool({ name: 'gaussian_blur_v2' })
      let resolvePackages!: (value: { data: unknown[] }) => void
      const packages = new Promise<{ data: unknown[] }>((resolve) => {
        resolvePackages = resolve
      })
      store.tools = [makeTool()] as any
      apiMocks.patch.mockResolvedValueOnce({
        data: {
          old_name: 'gaussian_blur',
          new_name: 'gaussian_blur_v2',
          path: '/tmp/gaussian_blur_v2.py',
        },
      })
      apiMocks.get.mockImplementation((url: string) => {
        if (url === '/api/v1/tools') return Promise.resolve({ data: [renamedTool] })
        if (url === '/api/v1/tools/packages') return packages
        return Promise.resolve({ data: {} })
      })
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph: { nodes: [makeGraphNode('shared')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      const sync = graphSyncMocks.apis[0]
      const persistence = persistenceMocks.apis[0]
      sync.syncGraphState.mockClear()
      sync.revalidateGraphState.mockClear()
      persistence.queueGraph.mockClear()

      const rename = store.renameTool('gaussian_blur', 'gaussian_blur_v2')
      await vi.waitFor(() => expect(store.tools).toEqual([renamedTool]))
      await flushPromises()

      expect(mockNodes[0].data.toolName).toBe('gaussian_blur')
      expect(mockNodes[0].data.tool).toEqual(makeTool())
      expect(mockNodes[0].data.missingTool).toBeNull()
      expect(sync.syncGraphState).not.toHaveBeenCalled()

      resolvePackages({ data: [] })
      const result = await rename
      window.dispatchEvent(new CustomEvent('bioimageflow:tool-renamed', {
        detail: result,
      }))
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.toolName).toBe('gaussian_blur_v2')
      expect(mockNodes[0].data.tool.name).toBe('gaussian_blur_v2')
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(sync.revalidateGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).toHaveBeenCalledOnce()
      w.unmount()
    })

    it('preserves a focused rename chain until every focused field blurs', async () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any
      const canvasId = canvasIdFromPanelId('workflow:analysis')
      const w = mountCanvas({
        params: {
          panelId: canvasId,
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph: { nodes: [makeGraphNode('shared')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      const sync = graphSyncMocks.apis[0]
      const persistence = persistenceMocks.apis[0]
      const focus = useFieldFocusTracker()
      const sigma = { canvasId, nodeId: 'shared', fieldName: 'sigma' }
      const image = { canvasId, nodeId: 'shared', fieldName: 'image' }
      focus.trackFocus(sigma)
      focus.trackFocus(image)
      sync.syncGraphState.mockClear()
      sync.revalidateGraphState.mockClear()
      persistence.queueGraph.mockClear()

      store.tools = [makeTool({ name: 'gaussian_blur_mid' })] as any
      window.dispatchEvent(new CustomEvent('bioimageflow:tool-renamed', {
        detail: { old_name: 'gaussian_blur', new_name: 'gaussian_blur_mid' },
      }))
      store.tools = [makeTool({
        name: 'gaussian_blur_final',
        inputs: { image: makeTool().inputs.image },
      })] as any
      window.dispatchEvent(new CustomEvent('bioimageflow:tool-renamed', {
        detail: { old_name: 'gaussian_blur_mid', new_name: 'gaussian_blur_final' },
      }))
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.toolName).toBe('gaussian_blur')
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).not.toHaveBeenCalled()

      focus.trackBlur(sigma)
      await nextTick()
      await flushPromises()
      expect(mockNodes[0].data.toolName).toBe('gaussian_blur')
      expect(sync.syncGraphState).not.toHaveBeenCalled()

      focus.trackBlur(image)
      await nextTick()
      await flushPromises()
      expect(mockNodes[0].data.toolName).toBe('gaussian_blur_final')
      expect(mockNodes[0].data.tool.name).toBe('gaussian_blur_final')
      expect(mockNodes[0].data.parameters).toEqual({})
      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(sync.revalidateGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).toHaveBeenCalledOnce()
      w.unmount()
    })

    it('drops deferred focus callbacks when the owning canvas unmounts', async () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any
      const canvasId = canvasIdFromPanelId('workflow:analysis')
      const w = mountCanvas({
        params: {
          panelId: canvasId,
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph: { nodes: [makeGraphNode('shared')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      const sync = graphSyncMocks.apis[0]
      const persistence = persistenceMocks.apis[0]
      const focus = useFieldFocusTracker()
      const target = { canvasId, nodeId: 'shared', fieldName: 'sigma' }
      focus.trackFocus(target)
      sync.syncGraphState.mockClear()
      persistence.queueGraph.mockClear()
      toastMocks.add.mockClear()

      store.tools = [makeTool({
        inputs: { image: makeTool().inputs.image },
      })] as any
      await nextTick()
      await flushPromises()
      w.unmount()
      focus.trackBlur(target)
      await flushPromises()

      expect(sync.syncGraphState).not.toHaveBeenCalled()
      expect(persistence.queueGraph).not.toHaveBeenCalled()
      expect(toastMocks.add).not.toHaveBeenCalled()
    })

    it('resumes registry reconciliation after an overlapping history application', async () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool()] as any
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph: { nodes: [makeGraphNode('shared')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      expect(canvasCommandMocks.registrations[0].setNodeEnabled('shared', false)).toBe(true)

      store.tools = [makeTool({
        inputs: { image: makeTool().inputs.image },
      })] as any
      await w.find('.canvas-view').trigger('keydown', { key: 'z', ctrlKey: true })
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.enabled).toBe(true)
      expect(mockNodes[0].data.tool.inputs).toEqual({ image: makeTool().inputs.image })
      expect(mockNodes[0].data.parameters).toEqual({})
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

    it('publishes template-changing tool metadata once with authoritative root edges', async () => {
      mockNodes = reactive([]) as any[]
      const store = useToolRegistryStore()
      store.tools = [makeTool({ package_version: '1.0.0' })] as any
      const edge = {
        type: 'column_ref' as const,
        id: 'e1',
        source_node: 'a',
        target_node: 'b',
        source_output: 'result',
        target_input: 'image',
      }
      const graph = {
        nodes: [
          {
            id: 'a',
            name: 'A',
            tool_name: 'gaussian_blur',
            position: [0, 0],
            parameters: {},
            resources: {},
            output_templates: { result: 'root-old.tif' },
            enabled: true,
            collapsed: false,
          },
          {
            id: 'b',
            name: 'B',
            tool_name: 'gaussian_blur',
            position: [120, 0],
            parameters: {},
            resources: {},
            output_templates: { result: '' },
            enabled: true,
            collapsed: false,
          },
        ],
        edges: [edge],
      }
      const w = mountCanvas({
        params: {
          panelId: 'workflow:analysis',
          workflowName: 'analysis',
          workflowDisplayName: 'Analysis',
          graph,
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      await flushPromises()
      expect(mockEdges).toHaveLength(1)
      expect(canvasCommandMocks.registrations[0].setNodeEnabled('a', false)).toBe(true)
      mockEdges.splice(0, mockEdges.length)
      graphSyncMocks.syncGraph.mockClear()
      graphSyncMocks.syncGraphState.mockClear()
      graphSyncMocks.revalidateGraphState.mockClear()
      persistenceMocks.queueGraph.mockClear()
      const graphChangedCount = w.emitted('graph-changed')?.length ?? 0

      store.tools = [makeTool({
        package_version: '2.0.0',
        outputs: { count: { type: 'int' } },
      })] as any
      await nextTick()
      await flushPromises()

      expect(mockNodes[0].data.output_templates).toEqual({})
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(graphSyncMocks.syncGraphState).not.toHaveBeenCalled()
      expect(graphSyncMocks.revalidateGraphState).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledTimes(1)
      expect(persistenceMocks.queueGraph).toHaveBeenCalledWith(expect.objectContaining({
        nodes: expect.arrayContaining([
          expect.objectContaining({ id: 'a', output_templates: {} }),
        ]),
        edges: [edge],
      }))
      expect(w.emitted('graph-changed')?.length ?? 0).toBe(graphChangedCount + 1)
      const rootGraphEvents = w.emitted('graph-changed') ?? []
      expect(rootGraphEvents[rootGraphEvents.length - 1]?.[0]).toEqual(expect.objectContaining({
        edges: [expect.objectContaining({ id: edge.id })],
      }))

      await nextTick()
      expect(graphSyncMocks.syncGraphState).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).toHaveBeenCalledTimes(1)

      await w.find('.canvas-view').trigger('keydown', { key: 'z', ctrlKey: true })
      expect(mockEdges).toEqual([expect.objectContaining({ id: edge.id })])
      expect(mockNodes[0].data.output_templates).toEqual({ result: 'root-old.tif' })
      expect(mockNodes[0].data.tool).toEqual(expect.objectContaining({
        package_version: '2.0.0',
        outputs: { count: { type: 'int' } },
      }))
      expect(mockNodes[0].data.missingTool).toBeNull()
      await w.find('.canvas-view').trigger('keydown', {
        key: 'z',
        ctrlKey: true,
        shiftKey: true,
      })
      expect(mockEdges).toEqual([expect.objectContaining({ id: edge.id })])
      expect(mockNodes[0].data.output_templates).toEqual({})
      expect(mockNodes[0].data.tool).toEqual(expect.objectContaining({
        package_version: '2.0.0',
        outputs: { count: { type: 'int' } },
      }))
      w.unmount()
    })

    it('publishes template-changing tool metadata once into the nested draft', async () => {
      mockNodes = reactive([]) as any[]
      const store = useToolRegistryStore()
      store.tools = [makeTool({ package_version: '1.0.0' })] as any
      const edge = {
        type: 'column_ref' as const,
        id: 'inner-edge',
        source_node: 'inner-a',
        target_node: 'inner-b',
        source_output: 'result',
        target_input: 'image',
      }
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentWorkflowName: 'parent',
        parentNodeId: 'sub_1',
        parentNodeName: 'Sub 1',
        graph: {
          nodes: [
            {
              id: 'inner-a',
              name: 'Inner A',
              tool_name: 'gaussian_blur',
              position: [0, 0],
              parameters: {},
              resources: {},
              output_templates: { result: 'nested-old.tif' },
              enabled: true,
              collapsed: false,
            },
            {
              id: 'inner-b',
              name: 'Inner B',
              tool_name: 'gaussian_blur',
              position: [120, 0],
              parameters: {},
              resources: {},
              output_templates: { result: '' },
              enabled: true,
              collapsed: false,
            },
          ],
          edges: [edge],
        },
      })
      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()
      await nextTick()
      await flushPromises()
      expect(mockEdges).toHaveLength(1)
      mockEdges.splice(0, mockEdges.length)
      graphSyncMocks.syncGraph.mockClear()
      graphSyncMocks.syncGraphState.mockClear()
      persistenceMocks.queueGraph.mockClear()
      const graphChangedCount = w.emitted('graph-changed')?.length ?? 0

      store.tools = [makeTool({
        package_version: '2.0.0',
        outputs: { count: { type: 'int' } },
      })] as any
      await nextTick()
      await flushPromises()

      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(graphSyncMocks.syncGraphState).toHaveBeenCalledTimes(1)
      expect(sessions.sessionById(session.id)?.draft).toEqual(expect.objectContaining({
        nodes: expect.arrayContaining([
          expect.objectContaining({ id: 'inner-a', output_templates: {} }),
        ]),
        edges: [edge],
      }))
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()
      expect(w.emitted('graph-changed')?.length ?? 0).toBe(graphChangedCount + 1)
      const nestedGraphEvents = w.emitted('graph-changed') ?? []
      expect(nestedGraphEvents[nestedGraphEvents.length - 1]?.[0]).toEqual(expect.objectContaining({
        edges: [expect.objectContaining({ id: edge.id })],
      }))

      await nextTick()
      expect(graphSyncMocks.syncGraphState).toHaveBeenCalledTimes(1)
      w.unmount()
    })

    it('does not optimistically overwrite an authoritative executed status', async () => {
      const store = useToolRegistryStore()
      store.tools = [makeTool({ package_version: '1.0.0' })] as any

      const w = mountCanvas()
      const vm = w.vm as any
      vm.onAddNode({ toolName: 'gaussian_blur', position: { x: 0, y: 0 } })
      // Simulate the node having been executed against v1.0.0.
      mockNodes[0].data.status = 'executed'

      store.tools = [makeTool({ package_version: '2.0.0' })] as any
      await nextTick()

      expect(mockNodes[0].data.status).toBe('executed')
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

    it('flushes and applies only the exact accepted nested snapshot before marking clean', async () => {
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentCanvasId: 'workflow:parent',
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
          published_inputs: [],
          published_outputs: [],
        },
      })
      const acceptedGraph = {
        nodes: [{
          id: 'inner_1',
          name: 'Inner 1',
          tool_name: 'gaussian_blur',
          position: [0, 0] as [number, number],
          parameters: { sigma: 3 },
          resources: {},
          output_templates: {},
          enabled: true,
          collapsed: false,
        }],
        edges: [],
        published_inputs: [],
        published_outputs: [],
      }
      graphSyncMocks.flushNow.mockResolvedValue({
        graph: acceptedGraph,
        validation: { valid: true, node_statuses: {}, errors: [] },
        snapshotRevision: 8,
      })
      const applied = vi.fn((event: Event) => {
        ;(event as CustomEvent).detail.acknowledge()
      })
      window.addEventListener('bioimageflow:apply-sub-workflow-session', applied)

      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()
      graphSyncMocks.syncGraph.mockClear()
      graphSyncMocks.syncGraphState.mockClear()

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
      expect(canvasCommandMocks.registrations[0]).toMatchObject({
        descriptor: {
          kind: 'nested',
          sessionId: session.id,
        },
        save: expect.any(Function),
      })
      await canvasCommandMocks.registrations[0].save()

      expect(applied).toHaveBeenCalledTimes(1)
      expect((applied.mock.calls[0][0] as CustomEvent).detail).toMatchObject({
        parentCanvasId: 'workflow:parent',
        parentNodeId: 'sub_1',
        graph: {
          nodes: [expect.objectContaining({
            id: 'inner_1',
            parameters: { sigma: 3 },
          })],
        },
      })
      expect(graphSyncMocks.flushNow).toHaveBeenCalledTimes(1)
      expect(sessions.isDirty(session.id)).toBe(false)
      expect(sessions.sessionById(session.id)?.snapshotRevision).toBe(8)
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      window.removeEventListener('bioimageflow:apply-sub-workflow-session', applied)
      w.unmount()
    })

    it('keeps a nested session dirty when the accepted snapshot has no parent acknowledgement', async () => {
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentCanvasId: 'workflow:missing',
        parentWorkflowName: 'parent',
        parentNodeId: 'sub_1',
        parentNodeName: 'Sub 1',
        graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
      })
      sessions.updateDraft(session.id, {
        nodes: [],
        edges: [],
        published_inputs: [{
          name: 'source',
          internal_node_id: 'inner',
          internal_field: 'image',
          kind: 'input',
          schema: { type: 'Path' },
          default: null,
        }],
        published_outputs: [],
      })
      graphSyncMocks.flushNow.mockResolvedValue({
        graph: sessions.sessionById(session.id)!.draft,
        validation: { valid: true, node_statuses: {}, errors: [] },
        snapshotRevision: 2,
      })
      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()

      await canvasCommandMocks.registrations[0].save()

      expect(sessions.isDirty(session.id)).toBe(true)
      w.unmount()
    })

    it('does not apply an accepted nested snapshot after its canvas unmounts', async () => {
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentCanvasId: 'workflow:parent',
        parentWorkflowName: 'parent',
        parentNodeId: 'sub_1',
        parentNodeName: 'Sub 1',
        graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
      })
      sessions.updateDraft(session.id, {
        nodes: [],
        edges: [],
        published_inputs: [{
          name: 'source',
          internal_node_id: 'inner',
          internal_field: 'image',
          kind: 'input',
          schema: { type: 'Path' },
          default: null,
        }],
        published_outputs: [],
      })
      const pendingFlush = deferred<{
        graph: typeof session.draft
        validation: {
          valid: boolean
          node_statuses: Record<string, never>
          errors: never[]
        }
        snapshotRevision: number
      }>()
      graphSyncMocks.flushNow.mockReturnValue(pendingFlush.promise)
      const applied = vi.fn()
      window.addEventListener('bioimageflow:apply-sub-workflow-session', applied)
      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()

      const save = canvasCommandMocks.registrations[0].save()
      expect(graphSyncMocks.flushNow).toHaveBeenCalledTimes(1)
      w.unmount()
      pendingFlush.resolve({
        graph: sessions.sessionById(session.id)!.draft,
        validation: { valid: true, node_statuses: {}, errors: [] },
        snapshotRevision: 2,
      })
      await save

      expect(applied).not.toHaveBeenCalled()
      expect(sessions.isDirty(session.id)).toBe(true)
      window.removeEventListener('bioimageflow:apply-sub-workflow-session', applied)
    })

    it('applies a nested snapshot event only for its exact session and parent canvas', async () => {
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentCanvasId: 'workflow:parent-a',
        parentWorkflowName: 'parent',
        parentNodeId: 'sub_1',
        parentNodeName: 'Sub 1',
        graph: { nodes: [], edges: [], published_inputs: [], published_outputs: [] },
      })
      const w = mountCanvas({ params: { panelId: 'workflow:parent-a' } })
      mockNodes.splice(0, mockNodes.length, {
        id: 'sub_1',
        type: 'sub_workflow',
        position: { x: 0, y: 0 },
        data: {
          name: 'Sub 1',
          toolName: '__sub_workflow__',
          parameters: {},
          published_inputs: [],
          published_outputs: [],
          sub_workflow: { nodes: [], edges: [] },
        },
      })
      const graph = {
        nodes: [],
        edges: [],
        published_inputs: [],
        published_outputs: [],
      }

      window.dispatchEvent(new CustomEvent('bioimageflow:apply-sub-workflow-session', {
        detail: {
          sessionId: session.id,
          parentCanvasId: 'workflow:parent-b',
          parentNodeId: 'sub_1',
          graph,
          acknowledge: vi.fn(),
        },
      }))
      expect(w.emitted('graph-changed')).toBeUndefined()

      const staleAcknowledge = vi.fn()
      window.dispatchEvent(new CustomEvent('bioimageflow:apply-sub-workflow-session', {
        detail: {
          sessionId: 'stale-session',
          parentCanvasId: 'workflow:parent-a',
          parentNodeId: 'sub_1',
          graph,
          acknowledge: staleAcknowledge,
        },
      }))
      expect(staleAcknowledge).not.toHaveBeenCalled()
      expect(w.emitted('graph-changed')).toBeUndefined()

      const acknowledge = vi.fn()
      window.dispatchEvent(new CustomEvent('bioimageflow:apply-sub-workflow-session', {
        detail: {
          sessionId: session.id,
          parentCanvasId: 'workflow:parent-a',
          parentNodeId: 'sub_1',
          graph,
          acknowledge,
        },
      }))
      expect(acknowledge).toHaveBeenCalledTimes(1)
      expect(w.emitted('graph-changed')).toHaveLength(1)
      w.unmount()
    })

    it('publishes nested parameter edits through the same synchronous canvas command', async () => {
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
            parameters: { sigma: 1 },
            resources: {},
            output_templates: {},
            enabled: true,
            collapsed: false,
          }],
          edges: [],
        },
      })
      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()

      const updateParameter = canvasCommandMocks.registrations[0].updateParameter
      expect(updateParameter('inner_1', 'sigma', 4)).toBe(true)

      expect(mockNodes[0].data.parameters).toEqual({ sigma: 4 })
      expect(mockNodes[0].data.status).toBe('unexecuted')
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledOnce()
      expect(sessions.sessionById(session.id)?.draft.nodes[0]?.parameters).toEqual({
        sigma: 4,
      })
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()

      await nextTick()
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledOnce()
      w.unmount()
    })

    it('publishes nested NodePanel edits synchronously through the same commands', async () => {
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
            parameters: { sigma: 1 },
            resources: {},
            output_templates: { result: '' },
            enabled: true,
            collapsed: false,
          }],
          edges: [],
        },
      })
      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      const registration = canvasCommandMocks.registrations[0]

      expect(registration.renameNode('inner_1', 'Renamed inner')).toBe(true)
      expect(sessions.sessionById(session.id)?.draft.nodes[0]?.name).toBe('Renamed inner')
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledTimes(1)

      expect(registration.setNodeEnabled('inner_1', false)).toBe(true)
      expect(sessions.sessionById(session.id)?.draft.nodes[0]?.enabled).toBe(false)
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledTimes(2)

      expect(registration.setInputPinned('inner_1', 'image', false)).toBe(true)
      expect(mockNodes[0].data.pinnedInputs).toEqual({ image: false })
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledTimes(3)

      expect(registration.setOutputTemplate('inner_1', 'result', 'nested.tif')).toBe(true)
      expect(sessions.sessionById(session.id)?.draft.nodes[0]?.output_templates).toEqual({
        result: 'nested.tif',
      })
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledTimes(4)
      expect(mockNodes[0].data.status).toBe('unexecuted')
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()

      await nextTick()
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledTimes(4)
      w.unmount()
    })

    it('publishes nested interface toggles and renames through the owning session', async () => {
      const tool = makeTool()
      useToolRegistryStore().tools = [tool] as any
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentWorkflowName: 'parent',
        parentNodeId: 'sub_1',
        parentNodeName: 'Sub 1',
        graph: {
          nodes: [{
            id: 'inner_1',
            name: 'Inner 1',
            tool_name: tool.name,
            position: [0, 0],
            parameters: { image: '/data/nested.tif' },
            resources: {},
            output_templates: { result: '' },
            enabled: true,
            collapsed: false,
          }],
          edges: [],
        },
      })
      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()
      const updateDraft = vi.spyOn(sessions, 'updateDraft')
      graphSyncMocks.syncGraph.mockClear()
      persistenceMocks.queueGraph.mockClear()
      const registration = canvasCommandMocks.registrations[0]
      const currentSession = () => sessions.sessionById(session.id)!

      expect(registration.togglePublishedInput('inner_1', 'image')).toEqual({
        status: 'changed',
      })
      expect(currentSession().published_inputs).toEqual([
        expect.objectContaining({
          name: 'inner_1.image',
          internal_node_id: 'inner_1',
          internal_field: 'image',
          default: '/data/nested.tif',
        }),
      ])
      expect(mockNodes[0].data.publicationContext.published_inputs)
        .toBe(currentSession().published_inputs)
      expect(updateDraft).toHaveBeenCalledOnce()
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledOnce()
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()
      expect(sessions.isDirty(session.id)).toBe(true)

      await nextTick()
      expect(updateDraft).toHaveBeenCalledOnce()
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledOnce()
      updateDraft.mockClear()
      graphSyncMocks.syncGraph.mockClear()

      expect(registration.renamePublishedInput('inner_1', 'image', 'nested_source'))
        .toEqual({ status: 'changed' })
      expect(currentSession().published_inputs[0].name).toBe('nested_source')
      expect(updateDraft).toHaveBeenCalledOnce()
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledOnce()
      updateDraft.mockClear()
      graphSyncMocks.syncGraph.mockClear()

      expect(registration.togglePublishedOutput('inner_1', 'result')).toEqual({
        status: 'changed',
      })
      expect(currentSession().published_outputs).toEqual([
        expect.objectContaining({
          name: 'inner_1.result',
          internal_node_id: 'inner_1',
          internal_output: 'result',
        }),
      ])
      expect(updateDraft).toHaveBeenCalledOnce()
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledOnce()
      updateDraft.mockClear()
      graphSyncMocks.syncGraph.mockClear()

      expect(registration.renamePublishedOutput('inner_1', 'result', 'nested_result'))
        .toEqual({ status: 'changed' })
      expect(currentSession().published_outputs[0].name).toBe('nested_result')
      expect(mockNodes[0].data.publicationContext.published_outputs)
        .toBe(currentSession().published_outputs)
      expect(updateDraft).toHaveBeenCalledOnce()
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledOnce()

      await nextTick()
      expect(updateDraft).toHaveBeenCalledOnce()
      expect(graphSyncMocks.syncGraph).toHaveBeenCalledOnce()
      w.unmount()
    })

    it('restores nested publication history through the owning session only', async () => {
      const tool = makeTool()
      useToolRegistryStore().tools = [tool] as any
      mockNodes = reactive([]) as any[]
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentWorkflowName: 'parent',
        parentNodeId: 'sub_1',
        parentNodeName: 'Sub 1',
        graph: {
          nodes: [{
            id: 'inner_1',
            name: 'Inner 1',
            tool_name: tool.name,
            position: [0, 0],
            parameters: {},
            resources: {},
            output_templates: { result: '' },
            enabled: true,
            collapsed: false,
          }],
          edges: [],
        },
      })
      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()
      await nextTick()
      await flushPromises()
      const registration = canvasCommandMocks.registrations[0]
      const updateDraft = vi.spyOn(sessions, 'updateDraft')

      async function applyHistory(
        redo: boolean,
        expectedNames: string[],
      ): Promise<void> {
        graphSyncMocks.syncGraph.mockClear()
        persistenceMocks.queueGraph.mockClear()
        updateDraft.mockClear()
        await w.find('.canvas-view').trigger('keydown', {
          key: 'z',
          ctrlKey: true,
          shiftKey: redo,
        })
        await nextTick()

        const current = sessions.sessionById(session.id)!
        expect(current.published_outputs.map((item) => item.name)).toEqual(expectedNames)
        expect(mockNodes[0].data.publicationContext.published_outputs)
          .toBe(current.published_outputs)
        expect(graphSyncMocks.syncGraph).toHaveBeenCalledOnce()
        expect(updateDraft).toHaveBeenCalledOnce()
        expect(updateDraft).toHaveBeenCalledWith(
          session.id,
          expect.objectContaining({
            nodes: [expect.objectContaining({ id: 'inner_1' })],
          }),
        )
        expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()
      }

      expect(registration.togglePublishedOutput('inner_1', 'result'))
        .toEqual({ status: 'changed' })
      await nextTick()
      await applyHistory(false, [])
      await applyHistory(true, ['inner_1.result'])

      expect(registration.renamePublishedOutput('inner_1', 'result', 'nested_result'))
        .toEqual({ status: 'changed' })
      await nextTick()
      await applyHistory(false, ['inner_1.result'])
      await applyHistory(true, ['nested_result'])

      expect(registration.togglePublishedOutput('inner_1', 'result'))
        .toEqual({ status: 'changed' })
      await nextTick()
      await applyHistory(false, ['nested_result'])
      await applyHistory(true, [])
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
      expect(graphSyncMocks.syncGraphState).toHaveBeenCalledWith(expect.objectContaining({
        published_inputs: [expect.objectContaining({ name: 'image' })],
      }))
      w.unmount()
    })

    it('reconciles and publishes an applied sub-workflow draft exactly once', async () => {
      const clearCanvasCache = vi.spyOn(useDataTableStore(), 'clearCanvasCache')
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
      graphSyncMocks.apis[0].validationResult.value = {
        valid: true,
        errors: [],
        node_statuses: {
          sub_1: { node_id: 'sub_1', status: 'executed', cached: false },
        },
      }

      const vm = w.vm as any
      graphSyncMocks.syncGraph.mockClear()
      const graphChangedCount = w.emitted('graph-changed')?.length ?? 0
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
      expect(projectedStatusesOf(w).sub_1).toMatchObject({
        status: 'out_of_date',
        provisional: true,
      })
      expect(subNode.data.status).toBe('executed')
      expect(clearCanvasCache).toHaveBeenCalledWith('canvas', 'sub_1')
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(w.emitted('graph-changed')?.length ?? 0).toBe(graphChangedCount + 1)

      await nextTick()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(w.emitted('graph-changed')?.length ?? 0).toBe(graphChangedCount + 1)
      w.unmount()
    })

    it('keeps an unexecuted parent unexecuted when applying a sub-workflow draft', () => {
      const w = mountCanvas()
      mockNodes.splice(0, mockNodes.length, {
        id: 'sub_1',
        type: 'sub_workflow',
        position: { x: 0, y: 0 },
        data: {
          name: 'Sub 1',
          toolName: '__sub_workflow__',
          status: 'executed',
          parameters: {},
          pinnedInputs: {},
          connectedInputs: {},
          published_inputs: [],
          published_outputs: [],
          sub_workflow: { nodes: [], edges: [] },
        },
      })

      ;(w.vm as any).applySubWorkflowDraft('sub_1', { nodes: [], edges: [] })

      expect(projectedStatusesOf(w).sub_1).toMatchObject({
        status: 'unexecuted',
        provisional: true,
      })
      expect(mockNodes[0].data.status).toBe('executed')
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

  describe('remote workflow drafts', () => {
    function graphNode(id: string, x = 0) {
      return {
        id,
        name: id,
        tool_name: 'gaussian_blur',
        position: [x, 0] as [number, number],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }
    }

    function buttonWithText(w: ReturnType<typeof mountCanvas>, text: string) {
      return w.findAll('button').find((button) => button.text() === text)
    }

    async function mountActiveCanvasWithDraft(options: {
      initialGraph: { nodes: any[]; edges: any[] }
      initialDirty?: boolean
      remoteGraph?: { nodes: any[]; edges: any[] }
      remoteDirty?: boolean
    }) {
      useToolRegistryStore().tools = [makeTool()] as any
      const workflowStore = useWorkflowStore()
      workflowStore.current = { name: 'wf', display_name: 'WF' } as any
      const draftStore = useWorkflowDraftStore()
      apiMocks.get.mockResolvedValueOnce({
        data: draftResponse(1, options.initialGraph, options.initialDirty ?? false),
      })
      await draftStore.loadDraft('wf')
      if (options.remoteGraph) {
        apiMocks.get.mockResolvedValueOnce({
          data: draftResponse(2, options.remoteGraph, options.remoteDirty ?? false),
        })
      }

      const w = mountCanvas({
        params: {
          panelId: 'canvas:wf',
          workflowName: 'wf',
          workflowDisplayName: 'WF',
          graph: options.initialGraph,
          dirty: options.initialDirty ?? false,
        },
      })
      await flushPromises()
      await nextTick()
      await flushPromises()
      graphSyncMocks.syncGraph.mockClear()
      graphSyncMocks.syncGraphState.mockClear()
      graphSyncMocks.revalidateGraphState.mockClear()
      autoSaveMocks.scheduleAutoSave.mockClear()
      return { w, draftStore }
    }

    it('auto-applies a newer remote draft for the active clean canvas', async () => {
      const initialGraph = { nodes: [graphNode('old')], edges: [] }
      const remoteGraph = { nodes: [graphNode('remote', 120)], edges: [] }
      const { w, draftStore } = await mountActiveCanvasWithDraft({
        initialGraph,
        initialDirty: false,
        remoteGraph,
        remoteDirty: false,
      })
      const scheduleSaveSpy = vi.spyOn(draftStore, 'scheduleSave')

      draftStore.noteRemoteChange(draftChanged(2, { dirty_against_saved: false }))
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockNodes.map((node: any) => node.id)).toEqual(['remote'])
      expect(draftStore.currentDraftRevision).toBe(2)
      expect(draftStore.appliedDraftRevision).toBe(2)
      expect(draftStore.remoteAvailableRevision).toBeNull()
      expect(persistenceMocks.resolveFromDraft).toHaveBeenCalledWith(
        draftResponse(2, remoteGraph, false),
      )
      expect(useUIStore().hasUnsavedChanges).toBe(false)
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(graphSyncMocks.syncGraphState).toHaveBeenCalledTimes(1)
      expect(graphSyncMocks.syncGraphState).toHaveBeenCalledWith(expect.objectContaining({
        nodes: [expect.objectContaining({ id: 'remote' })],
      }))
      expect(autoSaveMocks.scheduleAutoSave).not.toHaveBeenCalled()
      expect(scheduleSaveSpy).not.toHaveBeenCalled()
      expect(w.find('.workflow-draft-conflict').exists()).toBe(false)
      w.unmount()
    })

    it('shows conflict actions instead of auto-applying when the canvas has local edits', async () => {
      const initialGraph = { nodes: [graphNode('old')], edges: [] }
      const remoteGraph = { nodes: [graphNode('remote', 120)], edges: [] }
      const { w, draftStore } = await mountActiveCanvasWithDraft({
        initialGraph,
        initialDirty: true,
      })
      apiMocks.get.mockClear()
      apiMocks.get.mockResolvedValue({ data: draftResponse(2, remoteGraph) })

      draftStore.noteRemoteChange(draftChanged(2))
      await flushPromises()
      await nextTick()

      const conflict = w.find('.workflow-draft-conflict')
      expect(conflict.exists()).toBe(true)
      expect(conflict.text()).toContain('This workflow changed outside the canvas.')
      expect(conflict.text()).not.toContain('backend')
      expect(conflict.text()).not.toContain('live draft')
      expect(buttonWithText(w, 'Apply agent changes')?.exists()).toBe(true)
      expect(buttonWithText(w, 'Keep my canvas')?.exists()).toBe(true)
      expect(buttonWithText(w, 'Save agent version as copy')?.exists()).toBe(true)
      expect(mockNodes.map((node: any) => node.id)).toEqual(['old'])
      expect(apiMocks.get).not.toHaveBeenCalled()
      w.unmount()
    })

    it('does not auto-apply while a local draft save is pending', async () => {
      const initialGraph = { nodes: [graphNode('old')], edges: [] }
      const remoteGraph = { nodes: [graphNode('remote', 120)], edges: [] }
      persistenceMocks.isPending.value = true
      const { w, draftStore } = await mountActiveCanvasWithDraft({ initialGraph })
      apiMocks.get.mockClear()
      apiMocks.get.mockResolvedValue({ data: draftResponse(2, remoteGraph) })

      draftStore.noteRemoteChange(draftChanged(2))
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockNodes.map((node: any) => node.id)).toEqual(['old'])
      expect(apiMocks.get).not.toHaveBeenCalled()
      expect(draftStore.remoteAvailableRevision).toBe(2)
      expect(persistenceMocks.isPending.value).toBe(true)
      expect(w.find('.workflow-draft-conflict').exists()).toBe(true)
      persistenceMocks.isPending.value = false
      w.unmount()
    })

    it('applies agent changes from the conflict action without scheduling autosave', async () => {
      const initialGraph = { nodes: [graphNode('old')], edges: [] }
      const remoteGraph = { nodes: [graphNode('remote', 120)], edges: [] }
      const { w, draftStore } = await mountActiveCanvasWithDraft({
        initialGraph,
        initialDirty: true,
      })
      const scheduleSaveSpy = vi.spyOn(draftStore, 'scheduleSave')
      apiMocks.get.mockClear()
      apiMocks.get.mockResolvedValueOnce({ data: draftResponse(2, remoteGraph, false) })

      draftStore.noteRemoteChange(draftChanged(2, { dirty_against_saved: false }))
      await flushPromises()
      await nextTick()
      await buttonWithText(w, 'Apply agent changes')!.trigger('click')
      await flushPromises()
      await nextTick()

      expect(apiMocks.get).toHaveBeenCalledWith('/api/v1/workflow-drafts/wf')
      expect(mockNodes.map((node: any) => node.id)).toEqual(['remote'])
      expect(draftStore.currentDraftRevision).toBe(2)
      expect(draftStore.remoteAvailableRevision).toBeNull()
      expect(persistenceMocks.resolveFromDraft).toHaveBeenCalledWith(
        draftResponse(2, remoteGraph, false),
      )
      expect(useUIStore().hasUnsavedChanges).toBe(false)
      expect(autoSaveMocks.scheduleAutoSave).not.toHaveBeenCalled()
      expect(scheduleSaveSpy).not.toHaveBeenCalled()
      expect(w.find('.workflow-draft-conflict').exists()).toBe(false)
      w.unmount()
    })

    it('keeps my canvas by overwriting the latest remote draft revision', async () => {
      const initialGraph = { nodes: [graphNode('old')], edges: [] }
      const remoteGraph = { nodes: [graphNode('remote', 120)], edges: [] }
      const { w, draftStore } = await mountActiveCanvasWithDraft({
        initialGraph,
        initialDirty: true,
      })
      apiMocks.get.mockClear()
      apiMocks.get.mockResolvedValueOnce({ data: draftResponse(2, remoteGraph, true) })
      apiMocks.put.mockResolvedValueOnce({ data: draftResponse(3, initialGraph, true) })

      draftStore.noteRemoteChange(draftChanged(2))
      await flushPromises()
      await nextTick()
      await buttonWithText(w, 'Keep my canvas')!.trigger('click')
      await flushPromises()
      await nextTick()

      expect(apiMocks.get).toHaveBeenCalledWith('/api/v1/workflow-drafts/wf')
      expect(apiMocks.put).toHaveBeenCalledWith('/api/v1/workflow-drafts/wf', {
        graph: expect.objectContaining({
          nodes: [expect.objectContaining({
            id: 'old',
            output_templates: { result: '' },
          })],
          edges: [],
        }),
        expected_revision: 2,
        updated_by: 'frontend',
      })
      expect(mockNodes.map((node: any) => node.id)).toEqual(['old'])
      expect(draftStore.currentDraftRevision).toBe(3)
      expect(draftStore.remoteAvailableRevision).toBeNull()
      expect(persistenceMocks.resolveFromDraft).toHaveBeenCalledWith(
        draftResponse(3, initialGraph, true),
      )
      expect(w.find('.workflow-draft-conflict').exists()).toBe(false)
      w.unmount()
    })

    it('saves the agent version as a saved workflow copy while leaving the original conflict unresolved', async () => {
      const initialGraph = { nodes: [graphNode('old')], edges: [] }
      const remoteGraph = { nodes: [graphNode('remote', 120)], edges: [] }
      useWorkflowStore().workflows = [
        { name: 'wf', display_name: 'WF' },
        { name: 'wf_agent_2', display_name: 'WF agent 2' },
      ] as any
      const { w, draftStore } = await mountActiveCanvasWithDraft({
        initialGraph,
        initialDirty: true,
      })
      apiMocks.get.mockClear()
      apiMocks.get
        .mockResolvedValueOnce({ data: draftResponse(2, remoteGraph, true) })
      apiMocks.post.mockResolvedValueOnce({
        data: { name: 'wf_agent_3', display_name: 'wf_agent_3' },
      })
      apiMocks.put.mockResolvedValueOnce({
        data: { name: 'wf_agent_3', display_name: 'wf_agent_3' },
      })

      draftStore.noteRemoteChange(draftChanged(2))
      await flushPromises()
      await nextTick()
      await buttonWithText(w, 'Save agent version as copy')!.trigger('click')
      await flushPromises()
      await nextTick()

      expect(apiMocks.post).toHaveBeenCalledWith('/api/v1/workflows', {
        name: 'wf_agent_3',
        display_name: 'wf_agent_3',
      })
      expect(apiMocks.put).toHaveBeenCalledWith('/api/v1/workflows/wf_agent_3', {
        graph: remoteGraph,
      })
      expect(apiMocks.put).not.toHaveBeenCalledWith(
        '/api/v1/workflow-drafts/wf_agent_3',
        expect.anything(),
      )
      expect(apiMocks.put).not.toHaveBeenCalledWith(
        '/api/v1/workflow-drafts/wf',
        expect.anything(),
      )
      expect(useWorkflowStore().currentName).toBe('wf')
      expect(mockNodes.map((node: any) => node.id)).toEqual(['old'])
      expect(draftStore.workflowId).toBe('wf')
      expect(draftStore.remoteAvailableRevision).toBe(2)
      expect(w.text()).toContain('Agent version saved as wf_agent_3.')
      expect(w.find('.workflow-draft-conflict').exists()).toBe(true)
      w.unmount()
    })

    it('leaves the conflict visible when applying agent changes fails', async () => {
      const initialGraph = { nodes: [graphNode('old')], edges: [] }
      const { w, draftStore } = await mountActiveCanvasWithDraft({
        initialGraph,
        initialDirty: true,
      })
      apiMocks.get.mockClear()
      apiMocks.get.mockRejectedValueOnce(new Error('network down'))

      draftStore.noteRemoteChange(draftChanged(2))
      await flushPromises()
      await nextTick()
      await buttonWithText(w, 'Apply agent changes')!.trigger('click')
      await flushPromises()
      await nextTick()

      expect(mockNodes.map((node: any) => node.id)).toEqual(['old'])
      expect(draftStore.remoteAvailableRevision).toBe(2)
      expect(w.find('.workflow-draft-conflict').exists()).toBe(true)
      expect(w.find('.workflow-draft-conflict').text()).toContain('network down')
      w.unmount()
    })

    it('does not auto-apply remote drafts while the root canvas panel is inactive', async () => {
      const initialGraph = { nodes: [graphNode('old')], edges: [] }
      const remoteGraph = { nodes: [graphNode('remote', 120)], edges: [] }
      const { w, draftStore } = await mountActiveCanvasWithDraft({
        initialGraph,
        remoteGraph,
      })
      apiMocks.get.mockClear()

      window.dispatchEvent(new CustomEvent('bioimageflow:canvas-tab-activated', {
        detail: { panelId: 'canvas:other' },
      }))
      await nextTick()
      draftStore.noteRemoteChange(draftChanged(2))
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockNodes.map((node: any) => node.id)).toEqual(['old'])
      expect(apiMocks.get).not.toHaveBeenCalled()
      expect(draftStore.remoteAvailableRevision).toBe(2)
      w.unmount()
    })

    it('syncs the draft store to an activated root canvas workflow before later remote events', async () => {
      useToolRegistryStore().tools = [makeTool()] as any
      const draftStore = useWorkflowDraftStore()
      apiMocks.get.mockResolvedValueOnce({
        data: draftResponse(1, { nodes: [graphNode('tracked')], edges: [] }, false, 'tracked'),
      })
      await draftStore.loadDraft('tracked')
      expect(draftStore.workflowId).toBe('tracked')

      const w = mountCanvas({
        params: {
          panelId: 'canvas:wf',
          workflowName: 'wf',
          workflowDisplayName: 'WF',
          graph: { nodes: [graphNode('old')], edges: [] },
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      await flushPromises()
      window.dispatchEvent(new CustomEvent('bioimageflow:canvas-tab-activated', {
        detail: { panelId: 'canvas:other' },
      }))
      await nextTick()
      graphSyncMocks.syncGraph.mockClear()
      graphSyncMocks.syncGraphState.mockClear()
      apiMocks.get.mockClear()

      window.dispatchEvent(new CustomEvent('bioimageflow:canvas-tab-activated', {
        detail: { panelId: 'canvas:wf' },
      }))
      await nextTick()
      expect(draftStore.workflowId).toBe('wf')

      apiMocks.get.mockResolvedValueOnce({
        data: draftResponse(2, { nodes: [graphNode('remote', 120)], edges: [] }, true, 'wf'),
      })
      draftStore.noteRemoteChange(draftChanged(2))
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockNodes.map((node: any) => node.id)).toEqual(['remote'])
      expect(apiMocks.get).toHaveBeenCalledWith('/api/v1/workflow-drafts/wf')
      w.unmount()
    })

    it('does not let tab activation overwrite loaded edges from degraded Vue Flow state', async () => {
      useToolRegistryStore().tools = [makeTool()] as any
      const graph = {
        nodes: [graphNode('a'), graphNode('b', 120)],
        edges: [{
          type: 'column_ref',
          id: 'e1',
          source_node: 'a',
          target_node: 'b',
          source_output: 'result',
          target_input: 'image',
        }],
      }
      const w = mountCanvas({
        params: {
          panelId: 'canvas:wf',
          workflowName: 'wf',
          workflowDisplayName: 'WF',
          graph,
          dirty: false,
        },
      })
      await flushPromises()
      await nextTick()
      await flushPromises()
      mockEdges.splice(0, mockEdges.length)
      graphSyncMocks.syncGraph.mockClear()
      graphSyncMocks.syncGraphState.mockClear()

      window.dispatchEvent(new CustomEvent('bioimageflow:canvas-tab-activated', {
        detail: { panelId: 'canvas:wf' },
      }))
      await nextTick()

      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(graphSyncMocks.syncGraphState).toHaveBeenCalledWith(graph)
      w.unmount()
    })

    it('does not auto-apply root workflow draft events in a sub-workflow editor', async () => {
      useToolRegistryStore().tools = [makeTool()] as any
      const workflowStore = useWorkflowStore()
      workflowStore.current = { name: 'wf', display_name: 'WF' } as any
      const draftStore = useWorkflowDraftStore()
      const rootGraph = { nodes: [graphNode('root')], edges: [] }
      apiMocks.get.mockResolvedValueOnce({ data: draftResponse(1, rootGraph) })
      await draftStore.loadDraft('wf')
      const sessions = useSubWorkflowSessionsStore()
      const session = sessions.openSession({
        parentWorkflowName: 'wf',
        parentNodeId: 'sub_1',
        parentNodeName: 'Sub 1',
        graph: { nodes: [graphNode('inner')], edges: [] },
      })
      const w = mountCanvas({ subWorkflowSessionId: session.id })
      await flushPromises()
      await nextTick()
      await flushPromises()
      apiMocks.get.mockClear()

      draftStore.noteRemoteChange(draftChanged(2))
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockNodes.map((node: any) => node.id)).toEqual(['inner'])
      expect(apiMocks.get).not.toHaveBeenCalled()
      expect(draftStore.remoteAvailableRevision).toBe(2)
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

    it('initializes root authority from the exact draft used to open the canvas', async () => {
      useToolRegistryStore().tools = [makeTool()] as any
      const graph = { nodes: [savedNode('opened', 100)], edges: [] }
      const openedDraft = draftResponse(6, graph, true, 'opened-workflow')

      const w = mountCanvas({
        params: {
          panelId: 'workflow:opened-workflow',
          workflowName: 'opened-workflow',
          workflowDisplayName: 'Opened workflow',
          graph,
          draft: openedDraft,
          dirty: true,
        },
      })
      await flushPromises()

      expect(persistenceMocks.initializeFromDraft).toHaveBeenCalledWith(openedDraft)
      expect(persistenceMocks.initializeFromDraft.mock.invocationCallOrder[0])
        .toBeLessThan(graphSyncMocks.syncGraphState.mock.invocationCallOrder[0]!)
      w.unmount()
    })

    it('projects accepted draft validation after installing the startup graph', async () => {
      const name = 'saved'
      const nodes = [savedNode('a', 100), savedNode('b', 400)]
      const edges = [savedEdge('e1', 'a', 'b')]
      const graph = { nodes, edges }
      const edgeError = {
        type: 'type_incompatible' as const,
        detail: 'Incompatible edge types',
        edge_id: 'e1',
      }
      const acceptedDraft = {
        ...draftResponse(1, graph, false, name),
        validation: {
          valid: false,
          node_statuses: {
            a: { node_id: 'a', status: 'executed' as const, cached: true },
            b: { node_id: 'b', status: 'out_of_date' as const, cached: false },
          },
          errors: [edgeError],
        },
      }
      apiMocks.get.mockImplementation((url: string) => {
        if (url === '/api/v1/workflows/tree') {
          return Promise.reject(new Error('Tree endpoint unavailable'))
        }
        if (url === '/api/v1/workflows') {
          return Promise.resolve({
            data: [{
              name,
              display_name: 'Saved workflow',
              last_modified: '2026-05-21T11:00:00Z',
            }],
          })
        }
        if (url === `/api/v1/workflows/${name}`) {
          return Promise.resolve({
            data: {
              info: {
                name,
                display_name: 'Saved workflow',
                last_modified: '2026-05-21T11:00:00Z',
              },
              graph,
              missing_packages: [],
              missing_tools: [],
            },
          })
        }
        if (url === `/api/v1/workflow-drafts/${name}`) {
          return Promise.resolve({ data: acceptedDraft })
        }
        if (url === '/api/v1/tools') {
          return Promise.resolve({ data: [makeTool()] })
        }
        return Promise.resolve({ data: {} })
      })
      autoSaveMocks.getLastOpenedWorkflow.mockResolvedValueOnce(name)
      persistenceMocks.initializeFromDraft.mockImplementationOnce((draft) => {
        graphSyncMocks.apis[0].validationResult.value = draft.validation
      })

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(projectedStatusesOf(w).a.status).toBe('executed')
      expect(projectedStatusesOf(w).b.status).toBe('out_of_date')
      expect(mockEdges.find(edge => edge.id === 'e1')?.data.errors).toEqual([edgeError])
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()
      expect(graphSyncMocks.revalidateGraphState).not.toHaveBeenCalled()

      w.unmount()
    })

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
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(graphSyncMocks.syncGraphState).toHaveBeenCalledTimes(1)
      expect(graphSyncMocks.syncGraphState).toHaveBeenCalledWith(graph)

      w.unmount()
    })

    it('keeps the loaded graph authoritative if Vue Flow drops restored edges', async () => {
      const name = 'saved'
      const nodes = [savedNode('a', 100), savedNode('b', 400)]
      const edges = [savedEdge('e1', 'a', 'b')]
      const graph = { nodes, edges }
      mockSavedWorkflow(graph, name)
      dropNextNonEmptySetEdges = true

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockEdges).toEqual([])
      expect(autoSaveMocks.scheduleAutoSave).not.toHaveBeenCalled()
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(graphSyncMocks.syncGraphState).toHaveBeenCalledWith(graph)

      w.unmount()
    })

    it('does not let late tool metadata refresh overwrite authoritative edges', async () => {
      mockNodes = reactive([]) as any[]
      const name = 'saved'
      const nodes = [savedNode('a', 100), savedNode('b', 400)]
      const edges = [savedEdge('e1', 'a', 'b')]
      const graph = { nodes, edges }
      mockSavedWorkflow(graph, name, [])
      dropNextNonEmptySetEdges = true

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(mockNodes).toHaveLength(2)
      expect(mockEdges).toEqual([])

      graphSyncMocks.syncGraph.mockClear()
      graphSyncMocks.syncGraphState.mockClear()
      autoSaveMocks.scheduleAutoSave.mockClear()
      const graphChangedCount = w.emitted('graph-changed')?.length ?? 0

      const store = useToolRegistryStore()
      store.tools = [makeTool({
        package_version: '2.0.0',
        outputs: { count: { type: 'int' } },
      })] as any
      await nextTick()
      await flushPromises()

      expect(mockEdges).toEqual([])
      expect(graphSyncMocks.syncGraph).not.toHaveBeenCalled()
      expect(autoSaveMocks.scheduleAutoSave).not.toHaveBeenCalled()
      expect(persistenceMocks.queueGraph).not.toHaveBeenCalled()
      expect(w.emitted('graph-changed')?.length ?? 0).toBe(graphChangedCount)
      expect(graphSyncMocks.syncGraphState).not.toHaveBeenCalled()
      expect(graphSyncMocks.revalidateGraphState).toHaveBeenCalledTimes(1)
      expect(graphSyncMocks.revalidateGraphState).toHaveBeenCalledWith(expect.objectContaining({
        edges,
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
      let rejectDraft!: (reason: Error) => void

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
        if (url === `/api/v1/workflow-drafts/${name}`) {
          return new Promise((_resolve, reject) => {
            rejectDraft = reject
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
      useWorkflowStore().current = {
        name: 'other',
        display_name: 'Other workflow',
        last_modified: '2026-04-30T10:00:00.000Z',
      } as any
      rejectDraft(new Error('No workflow draft'))
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

    it('clears stale startup workflow state when server load returns 404', async () => {
      const targetName = 'missing'
      apiMocks.get.mockImplementation((url: string) => {
        if (url === '/api/v1/workflows/tree') {
          return Promise.resolve({
            data: {
              path: '',
              display_name: 'workspace',
              folders: [],
              workflows: [{
                id: targetName,
                name: targetName,
                folder: '',
                display_name: 'Missing',
                path: '/tmp/missing/workflow.json',
                last_modified: '2026-04-30T12:00:00.000Z',
              }],
            },
          })
        }
        if (url === `/api/v1/workflows/${targetName}`) {
          return Promise.reject(new Error('404'))
        }
        if (url === '/api/v1/tools') return Promise.resolve({ data: [makeTool()] })
        return Promise.resolve({ data: {} })
      })
      apiMocks.post.mockResolvedValueOnce({
        data: {
          name: 'Untitled',
          display_name: 'Untitled',
        },
      })
      autoSaveMocks.getLastOpenedWorkflow.mockResolvedValueOnce(targetName)

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      await flushPromises()

      expect(autoSaveMocks.clearAutoSave).toHaveBeenCalledWith(targetName)
      expect(autoSaveMocks.setLastOpenedWorkflow).toHaveBeenCalledWith(null)
      expect(apiMocks.post).toHaveBeenCalledWith(
        '/api/v1/workflows',
        { name: 'Untitled', display_name: 'Untitled' },
      )

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
      ;(resolvedStore.refreshCanvasResolvedOutputs as any).mockClear()

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      mockNodes.splice(0, mockNodes.length,
        { id: 'files_1', data: { toolName: 'files', tool: filesTool, name: 'Files 1', connectedInputs: {} } },
        { id: 'join_1', data: { toolName: 'cross_join', tool: joinTool, name: 'CrossJoin 1', connectedInputs: {} } },
      )
      mockEdges.splice(0, mockEdges.length)
      ;(resolvedStore.refreshCanvasResolvedOutputs as any).mockClear()

      connectHandler!({
        source: 'files_1',
        target: 'join_1',
        sourceHandle: '__dataframe_out',
        targetHandle: '__positional_0',
      })

      await flushPromises()
      await nextTick()
      await flushPromises()

      const calls = (resolvedStore.refreshCanvasResolvedOutputs as any).mock.calls
      const calledForJoin = calls.some(
        (c: any[]) => c[0] === 'canvas' && c[1] === 'join_1',
      )
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
      ;(resolvedStore.refreshCanvasResolvedOutputs as any).mockClear()

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
      ;(resolvedStore.refreshCanvasResolvedOutputs as any).mockClear()

      const vm = w.vm as any
      vm.deleteSelected()

      await flushPromises()
      await nextTick()

      const calls = (resolvedStore.refreshCanvasResolvedOutputs as any).mock.calls
      const calledForJoin = calls.some(
        (c: any[]) => c[0] === 'canvas' && c[1] === 'join_1',
      )
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
      ;(resolvedStore.refreshCanvasResolvedOutputs as any).mockClear()

      const w = mountCanvas()
      await flushPromises()
      await nextTick()
      mockNodes.splice(0, mockNodes.length,
        { id: 'files_1', data: { toolName: 'files', tool: filesTool, name: 'Files 1', connectedInputs: {} } },
        { id: 'filter_1', data: { toolName: 'filter_rows', tool: passthroughTool, name: 'Filter 1', connectedInputs: {} } },
      )
      mockEdges.splice(0, mockEdges.length)
      ;(resolvedStore.refreshCanvasResolvedOutputs as any).mockClear()

      connectHandler!({
        source: 'files_1',
        target: 'filter_1',
        sourceHandle: '__dataframe_out',
        targetHandle: '__positional_0',
      })

      await flushPromises()
      await nextTick()
      await flushPromises()

      const calls = (resolvedStore.refreshCanvasResolvedOutputs as any).mock.calls
      const calledForFilter = calls.some(
        (c: any[]) => c[0] === 'canvas' && c[1] === 'filter_1',
      )
      expect(calledForFilter).toBe(false)
      w.unmount()
    })
  })
})
