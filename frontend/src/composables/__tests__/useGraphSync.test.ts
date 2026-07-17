import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ref, watch } from 'vue'
import type { GraphState, ValidationResult } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import { useWorkflowStore } from '@/stores/workflow'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'
import {
  _resetCanvasPersistenceForTest,
  useCanvasPersistence,
  type CanvasPersistenceTransports,
} from '../useCanvasPersistence'
import {
  activateGraphSyncCanvas,
  useGraphSync,
  serializeGraph,
  _resetGraphSyncForTest,
} from '../useGraphSync'

const fetchDraft = vi.fn<CanvasPersistenceTransports['fetchDraft']>()
const putDraft = vi.fn<CanvasPersistenceTransports['putDraft']>()
const writeRecovery = vi.fn<CanvasPersistenceTransports['writeRecovery']>()
const transports: CanvasPersistenceTransports = {
  fetchDraft,
  putDraft,
  writeRecovery,
}

/**
 * Build a Vue Flow-shaped graph (the format emitGraphChanged produces).
 */
const makeVueFlowGraph = (id = '1') => ({
  nodes: [{
    id,
    type: 'tool',
    position: { x: 10, y: 20 },
    data: {
      name: 'n',
      toolName: 't',
      parameters: {},
      enabled: true,
      collapsed: false,
      output_templates: {},
    },
  }],
  edges: [],
})

/**
 * The backend-format graph that the serializer should produce from makeVueFlowGraph.
 */
const expectedBackendGraph = (id = '1'): GraphState => ({
  nodes: [{
    id,
    name: 'n',
    tool_name: 't',
    position: [10, 20],
    parameters: {},
    resources: {},
    output_templates: {},
    enabled: true,
    collapsed: false,
  }],
  edges: [],
})

type ResolveDraft = (
  value: WorkflowDraftResponse | PromiseLike<WorkflowDraftResponse>
) => void

const makeValidation = (valid = true): ValidationResult => ({
  valid,
  node_statuses: {},
  errors: [],
})

function draftResponse(
  workflowId: string,
  revision: number,
  graph: GraphState,
  validation = makeValidation(),
): WorkflowDraftResponse {
  return {
    draft_version: 1,
    workflow_id: workflowId,
    base_saved_revision: 'sha256:test',
    draft_revision: revision,
    updated_at: `2026-07-16T00:00:0${revision}Z`,
    updated_by: 'frontend',
    dirty_against_saved: true,
    graph,
    validation,
  }
}

function canonicalGraphSync(workflowId = 'test-workflow') {
  const canvasId = canvasIdFromPanelId(`workflow:${workflowId}`)
  const descriptor = { kind: 'root' as const, canvasId, workflowId }
  const getWorkflowId = () => workflowId
  useCanvasPersistence({
    descriptor,
    getWorkflowId,
    transports,
    debounceMs: 250,
  })
  const sync = useGraphSync({ descriptor, getWorkflowId })
  activateGraphSyncCanvas(canvasId)
  return sync
}

describe('useGraphSync', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    fetchDraft.mockReset().mockImplementation(async workflowId => (
      draftResponse(workflowId, 0, { nodes: [], edges: [] })
    ))
    putDraft.mockReset().mockImplementation(async (workflowId, body) => (
      draftResponse(
        workflowId,
        body.expected_revision + 1,
        body.graph,
      )
    ))
    writeRecovery.mockReset().mockResolvedValue(undefined)
    _resetCanvasPersistenceForTest()
    _resetGraphSyncForTest()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('debounces multiple rapid syncGraph calls into one draft PUT', async () => {
    const { syncGraph } = canonicalGraphSync()

    syncGraph(makeVueFlowGraph('1'))
    syncGraph(makeVueFlowGraph('2'))
    syncGraph(makeVueFlowGraph('3'))

    expect(putDraft).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(300)

    expect(putDraft).toHaveBeenCalledTimes(1)
    expect(putDraft).toHaveBeenCalledWith(
      'test-workflow',
      expect.objectContaining({
        graph: expectedBackendGraph('3'),
        expected_revision: 0,
        validate: true,
      }),
    )
  })

  it('joins an in-flight request before sending the newer graph', async () => {
    let resolveFirst!: ResolveDraft
    let resolveSecond!: ResolveDraft

    putDraft
      .mockReturnValueOnce(new Promise(r => { resolveFirst = r }))
      .mockReturnValueOnce(new Promise(r => { resolveSecond = r }))

    const { syncGraph, validationResult } = canonicalGraphSync()

    // First call
    syncGraph(makeVueFlowGraph('1'))
    await vi.advanceTimersByTimeAsync(300)
    expect(putDraft).toHaveBeenCalledTimes(1)

    // A newer graph queues while the first request is in flight.
    syncGraph(makeVueFlowGraph('2'))
    await vi.advanceTimersByTimeAsync(300)
    expect(putDraft).toHaveBeenCalledTimes(1)

    // Resolving the first request starts the queued newer request. Its stale
    // validation is not published while the newer graph remains pending.
    resolveFirst(draftResponse(
      'test-workflow',
      1,
      expectedBackendGraph('1'),
      makeValidation(false),
    ))
    await vi.advanceTimersByTimeAsync(0)
    expect(validationResult.value).toBeNull()
    expect(putDraft).toHaveBeenCalledTimes(2)

    resolveSecond(draftResponse(
      'test-workflow',
      2,
      expectedBackendGraph('2'),
      makeValidation(true),
    ))
    await vi.advanceTimersByTimeAsync(0)
    expect(validationResult.value).toEqual(makeValidation(true))
  })

  it('returns validation result', async () => {
    const { syncGraph, validationResult } = canonicalGraphSync()

    syncGraph(makeVueFlowGraph())
    await vi.advanceTimersByTimeAsync(300)

    expect(validationResult.value).toEqual(makeValidation(true))
  })

  it('ignores an in-flight response after a newer graph is queued', async () => {
    let resolveFirst!: ResolveDraft
    let resolveSecond!: ResolveDraft

    putDraft
      .mockReturnValueOnce(new Promise(r => { resolveFirst = r }))
      .mockReturnValueOnce(new Promise(r => { resolveSecond = r }))

    const { syncGraph, validationResult } = canonicalGraphSync()

    syncGraph(makeVueFlowGraph('old'))
    await vi.advanceTimersByTimeAsync(300)
    expect(putDraft).toHaveBeenCalledTimes(1)

    syncGraph(makeVueFlowGraph('new'))
    resolveFirst(draftResponse(
      'test-workflow',
      1,
      expectedBackendGraph('old'),
      {
        valid: true,
        node_statuses: {
          old: { node_id: 'old', status: 'executed', cached: true },
        },
        errors: [],
      },
    ))
    await vi.advanceTimersByTimeAsync(0)

    expect(validationResult.value).toBeNull()
    await vi.advanceTimersByTimeAsync(300)
    expect(putDraft).toHaveBeenCalledTimes(2)

    resolveSecond(draftResponse(
      'test-workflow',
      2,
      expectedBackendGraph('new'),
      makeValidation(true),
    ))
    await vi.advanceTimersByTimeAsync(0)
    expect(validationResult.value).toEqual(makeValidation(true))
  })

  it('flushNow sends immediately', async () => {
    const { syncGraph, flushNow } = canonicalGraphSync()

    syncGraph(makeVueFlowGraph())
    expect(putDraft).not.toHaveBeenCalled()

    await flushNow()
    expect(putDraft).toHaveBeenCalledTimes(1)
  })

  it('flushNow waits for pending Vue watchers before sending', async () => {
    const { syncGraph, flushNow } = canonicalGraphSync()
    const parameter = ref('old')

    watch(parameter, (value) => {
      const graph = makeVueFlowGraph()
      graph.nodes[0]!.data.parameters = { path: value }
      syncGraph(graph)
    })

    parameter.value = 'new'
    await flushNow()

    expect(putDraft).toHaveBeenCalledWith(
      'test-workflow',
      expect.objectContaining({
        graph: expect.objectContaining({
          nodes: [
            expect.objectContaining({
              parameters: { path: 'new' },
            }),
          ],
        }),
      }),
    )
  })

  it('syncGraphState keeps backend graph state authoritative', async () => {
    const graph = {
      nodes: [{
        id: 'a',
        name: 'A',
        tool_name: 'tool_a',
        position: [1, 2],
        parameters: {},
        resources: {},
        output_templates: {},
        enabled: true,
        collapsed: false,
      }],
      edges: [{
        type: 'column_ref',
        id: 'e1',
        source_node: 'a',
        target_node: 'b',
        source_output: 'result',
        target_input: 'image',
      }],
    } as any
    const { syncGraphState, currentGraph, flushNow } = canonicalGraphSync()

    syncGraphState(graph)
    graph.edges = []

    expect(currentGraph.value.edges).toEqual([expect.objectContaining({ id: 'e1' })])
    await flushNow()

    expect(putDraft).toHaveBeenCalledWith(
      'test-workflow',
      expect.objectContaining({
        graph: expect.objectContaining({
          edges: [expect.objectContaining({ id: 'e1' })],
        }),
      }),
    )
  })

  it('isPending is true while request is in-flight', async () => {
    let resolve!: ResolveDraft
    putDraft.mockReturnValue(new Promise(r => { resolve = r }))

    const { syncGraph, isPending, flushNow } = canonicalGraphSync()

    expect(isPending.value).toBe(false)

    syncGraph(makeVueFlowGraph())
    const flushing = flushNow()

    await vi.advanceTimersByTimeAsync(0)
    expect(isPending.value).toBe(true)

    resolve(draftResponse('test-workflow', 1, expectedBackendGraph()))
    await flushing
    expect(isPending.value).toBe(false)
  })

  it('syncState is "pending" while PUT in flight and "idle" on success', async () => {
    let resolve!: ResolveDraft
    putDraft.mockReturnValue(new Promise(r => { resolve = r }))

    const { syncGraph, syncState, flushNow } = canonicalGraphSync()
    expect(syncState.value).toBe('idle')

    syncGraph(makeVueFlowGraph())
    const flushing = flushNow()
    await vi.advanceTimersByTimeAsync(0)
    expect(syncState.value).toBe('pending')

    resolve(draftResponse('test-workflow', 1, expectedBackendGraph()))
    await flushing
    expect(syncState.value).toBe('idle')
  })

  it('syncState transitions to "error" on PUT failure; validationResult is preserved', async () => {
    const {
      syncGraph,
      flushNow,
      syncState,
      lastError,
      validationResult,
    } = canonicalGraphSync()
    const persistence = useCanvasPersistence()
    syncGraph(makeVueFlowGraph())
    await vi.advanceTimersByTimeAsync(300)
    const previous = validationResult.value

    putDraft.mockRejectedValueOnce({ message: 'network boom', response: { status: 500 } })
    syncGraph(makeVueFlowGraph('2'))
    await expect(flushNow()).rejects.toMatchObject({ message: 'network boom' })

    expect(syncState.value).toBe('error')
    expect(lastError.value).toBe(persistence.persistenceIssue.value)
    expect(lastError.value).toMatchObject({ kind: 'error', source: 'draft' })
    // Previous result is kept visible
    expect(validationResult.value).toEqual(previous)

    syncGraph(makeVueFlowGraph('3'))
    expect(lastError.value).toBeNull()
    await flushNow()
    expect(lastError.value).toBeNull()
  })

  it('keeps the canonical canvas workflow identity when global selection changes', async () => {
    const workflowStore = useWorkflowStore()
    workflowStore.$patch({ current: { name: 'queued-workflow' } as any })
    const { syncGraph, flushNow } = canonicalGraphSync('queued-workflow')

    syncGraph(makeVueFlowGraph())
    workflowStore.$patch({ current: { name: 'later-workflow' } as any })
    await flushNow()

    expect(putDraft).toHaveBeenCalledWith(
      'queued-workflow',
      expect.objectContaining({ graph: expectedBackendGraph() }),
    )
  })

  it('serializeNode round-trips the resources field', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'n1',
        position: { x: 0, y: 0 },
        data: {
          name: 'n', toolName: 't', parameters: {},
          resources: { cpu: 4, gpu: 1 },
        },
      }],
      edges: [],
    })
    expect(result.nodes[0].resources).toEqual({ cpu: 4, gpu: 1 })
  })

  it('serializeNode preserves optional sub-workflow fields for v2 compatibility', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'outer',
        position: { x: 0, y: 0 },
        data: {
          name: 'Outer',
          toolName: '__sub_workflow__',
          parameters: { exposed: 1 },
          sub_workflow: {
            nodes: [{
              id: 'inner',
              name: 'Inner',
              tool_name: 'tool_a',
              position: [0, 0],
              parameters: {},
            }],
            edges: [],
          },
          published_inputs: [{
            name: 'exposed',
            internal_node_id: 'inner',
            internal_field: 'a',
            kind: 'parameter',
          }],
          published_outputs: [{
            name: 'result',
            internal_node_id: 'inner',
            internal_output: 'out',
          }],
          sub_workflow_readonly_reason: null,
        },
      }],
      edges: [],
    })

    expect((result.nodes[0] as any).sub_workflow.nodes[0].id).toBe('inner')
    expect((result.nodes[0] as any).published_inputs[0].name).toBe('exposed')
    expect((result.nodes[0] as any).published_outputs[0].name).toBe('result')
  })

  it('serializeGraph preserves root workflow published interface fields', () => {
    const result = serializeGraph({
      nodes: [],
      edges: [],
      published_inputs: [{
        name: 'input_image',
        internal_node_id: 'load_image',
        internal_field: 'image',
        kind: 'input',
        schema: { type: 'ImageFile', connectable: 'by_default' },
        default: null,
      }],
      published_outputs: [{
        name: 'mask',
        internal_node_id: 'segment',
        internal_output: 'mask',
        schema: { type: 'MaskPath' },
      }],
    } as any)

    expect((result as any).published_inputs).toEqual([expect.objectContaining({
      name: 'input_image',
      internal_node_id: 'load_image',
    })])
    expect((result as any).published_outputs).toEqual([expect.objectContaining({
      name: 'mask',
      internal_node_id: 'segment',
    })])
  })

  it('does not emit empty sub-workflow fields for regular tool nodes', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'regular',
        position: { x: 0, y: 0 },
        data: {
          name: 'Regular',
          toolName: 'tool_a',
          parameters: {},
          sub_workflow: null,
          published_inputs: [],
          published_outputs: [],
          sub_workflow_readonly_reason: null,
        },
      }],
      edges: [],
    })

    expect('sub_workflow' in (result.nodes[0] as any)).toBe(false)
    expect('published_inputs' in (result.nodes[0] as any)).toBe(false)
    expect('published_outputs' in (result.nodes[0] as any)).toBe(false)
    expect('sub_workflow_readonly_reason' in (result.nodes[0] as any)).toBe(false)
  })
})

describe('serializeGraph', () => {
  it('excludes runtime status projection fields from serialized nodes', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'n1',
        position: { x: 0, y: 0 },
        data: {
          name: 'Node 1',
          toolName: 'files',
          parameters: {},
          status: 'failed',
          provisional: true,
          error: 'runtime only',
          traceback: 'runtime only',
        },
      }],
      edges: [],
    })

    expect(result.nodes[0]).not.toHaveProperty('status')
    expect(result.nodes[0]).not.toHaveProperty('provisional')
    expect(result.nodes[0]).not.toHaveProperty('error')
    expect(result.nodes[0]).not.toHaveProperty('traceback')
  })

  it('converts Vue Flow node position {x,y} to backend [x,y]', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'n1',
        position: { x: 100, y: 200 },
        data: {
          name: 'My Node',
          toolName: 'threshold',
          parameters: { level: 0.5 },
          enabled: true,
          collapsed: false,
          output_templates: { mask: '{input}_mask' },
        },
      }],
      edges: [],
    })
    expect(result.nodes).toEqual([{
      id: 'n1',
      name: 'My Node',
      tool_name: 'threshold',
      position: [100, 200],
      parameters: { level: 0.5 },
      resources: {},
      output_templates: { mask: '{input}_mask' },
      enabled: true,
      collapsed: false,
    }])
  })

  it('serializes column_ref edges', () => {
    const result = serializeGraph({
      nodes: [],
      edges: [{
        id: 'e1',
        source: 'n1',
        target: 'n2',
        sourceHandle: 'image',
        targetHandle: 'input_image',
        type: 'column_ref',
      }],
    })
    expect(result.edges).toEqual([{
      type: 'column_ref',
      id: 'e1',
      source_node: 'n1',
      target_node: 'n2',
      source_output: 'image',
      target_input: 'input_image',
    }])
  })

  it('serializes positional edges, extracting index from handle name', () => {
    const result = serializeGraph({
      nodes: [],
      edges: [{
        id: 'e2',
        source: 'n1',
        target: 'n2',
        sourceHandle: 'output',
        targetHandle: '__positional_3',
        type: 'positional',
      }],
    })
    expect(result.edges).toEqual([{
      type: 'positional',
      id: 'e2',
      source_node: 'n1',
      target_node: 'n2',
      positional_index: 3,
    }])
  })

  it('defaults positional_index to 0 when handle has no valid index', () => {
    const result = serializeGraph({
      nodes: [],
      edges: [{
        id: 'e3',
        source: 'n1',
        target: 'n2',
        sourceHandle: null,
        targetHandle: null,
        type: 'positional',
      }],
    })
    expect(result.edges[0]).toMatchObject({
      type: 'positional',
      positional_index: 0,
    })
  })

  it('preserves optional sub-workflow graph fields', () => {
    const result = serializeGraph({
      nodes: [{
        id: 'outer',
        type: 'sub_workflow',
        position: { x: 100, y: 200 },
        data: {
          name: 'Outer',
          toolName: '__sub_workflow__',
          parameters: { image: '/tmp/input.tif' },
          sub_workflow: {
            nodes: [{
              id: 'inner',
              name: 'Inner',
              tool_name: 'TProcTool',
              position: [1, 2],
              parameters: { diameter: 7 },
              resources: {},
              output_templates: {},
              enabled: true,
              collapsed: false,
            }],
            edges: [],
          },
          published_inputs: [{
            name: 'image',
            internal_node_id: 'inner',
            internal_field: 'input_image',
            kind: 'input',
            schema: { type: 'Path' },
            default: null,
          }],
          published_outputs: [{
            name: 'mask',
            internal_node_id: 'inner',
            internal_output: 'mask',
            schema: { type: 'Path' },
          }],
          sub_workflow_readonly_reason: null,
        },
      }],
      edges: [],
    })

    expect(result.nodes[0]).toMatchObject({
      tool_name: '__sub_workflow__',
      sub_workflow: {
        nodes: [expect.objectContaining({ id: 'inner' })],
        edges: [],
      },
      published_inputs: [expect.objectContaining({ name: 'image' })],
      published_outputs: [expect.objectContaining({ name: 'mask' })],
      sub_workflow_readonly_reason: null,
    })
  })
})
