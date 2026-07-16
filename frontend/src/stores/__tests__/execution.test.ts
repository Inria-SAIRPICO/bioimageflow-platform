import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

import { useExecutionStore } from '../execution'
import { useLoggerStore } from '../logger'
import { useErrorStore } from '../errors'
import { useUIStore } from '../ui'
import { api } from '@/api/client'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'
import { deferred } from '@/test-utils/asyncFixtures'
import { makeGraph } from '@/test-utils/graphFixtures'

const EXECUTION_CONTEXT = {
  execution_id: 'exec-test',
  workflow_id: 'wf_a',
  draft_revision: 7,
} as const

function establishRunningExecution(
  execution: ReturnType<typeof useExecutionStore>,
): void {
  execution.applyStatusSnapshot({
    ...EXECUTION_CONTEXT,
    state: 'running',
    last_result: null,
    progress: null,
    node_statuses: {},
  })
}

describe('execution store', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    vi.mocked(api.post).mockReset()
  })

  it('preserves execution failure details without duplicating backend logger entries', () => {
    const execution = useExecutionStore()
    const logger = useLoggerStore()
    const errors = useErrorStore()
    logger.addEntry({
      level: 'ERROR',
      nodeId: 'node_a',
      message: 'Node node_a failed: segmentation failed\nTraceback...\nValueError: bad image',
      timestamp: 1,
    })

    establishRunningExecution(execution)
    execution.applyExecutionComplete({
      ...EXECUTION_CONTEXT,
      success: false,
      errors: [{ type: 'RuntimeError', detail: 'top-level failure' }],
      node_statuses: {
        node_a: {
          node_id: 'node_a',
          status: 'failed',
          cached: false,
          error: 'segmentation failed',
          traceback: 'Traceback...\nValueError: bad image',
        },
      },
    })

    expect(logger.entries).toHaveLength(1)
    expect(logger.entries[0]!.message).toContain('ValueError: bad image')
    expect(errors.errors[0]).toMatchObject({
      kind: 'execution_failed',
      detail: 'node_a: segmentation failed',
      nodeId: 'node_a',
      fullDetail: expect.stringContaining('ValueError: bad image'),
    })
  })

  it('captures environment delete recovery actions from execution failures', () => {
    const execution = useExecutionStore()

    establishRunningExecution(execution)
    execution.applyExecutionComplete({
      ...EXECUTION_CONTEXT,
      success: false,
      errors: [{
        type: 'EnvironmentReuseError',
        detail: 'Environment recipe mismatch',
        recovery_action: {
          kind: 'delete_environment',
          env_name: 'cellpose-env',
          path: '/wetlands/pixi/workspaces/cellpose-env/pixi.toml',
          existing_hash: 'sha256:old',
          requested_hash: 'sha256:new',
        },
      }],
      node_statuses: {
        cellpose_1: {
          node_id: 'cellpose_1',
          status: 'failed',
          cached: false,
          error: 'Environment recipe mismatch',
        },
      },
    })

    expect(execution.environmentRecoveryAction).toEqual({
      kind: 'delete_environment',
      envName: 'cellpose-env',
      path: '/wetlands/pixi/workspaces/cellpose-env/pixi.toml',
      existingHash: 'sha256:old',
      requestedHash: 'sha256:new',
      nodeId: 'cellpose_1',
    })
    expect(execution.isEnvironmentRecoveryDialogVisible).toBe(true)
  })

  it('dismisses and clears environment recovery actions when a new run starts', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        status: 'started',
        execution_id: 'exec-new',
        workflow_id: 'wf_a',
        draft_revision: null,
      },
    })
    const execution = useExecutionStore()
    establishRunningExecution(execution)
    execution.applyExecutionComplete({
      ...EXECUTION_CONTEXT,
      success: false,
      errors: [{
        detail: 'Environment recipe mismatch',
        recovery_action: {
          kind: 'delete_environment',
          env_name: 'cellpose-env',
        },
      }],
      node_statuses: {},
    })

    execution.dismissEnvironmentRecovery()
    expect(execution.isEnvironmentRecoveryDialogVisible).toBe(false)

    await execution.run({ nodes: [], edges: [] }, undefined, 'wf_a')

    expect(execution.environmentRecoveryAction).toBeNull()
    expect(execution.isEnvironmentRecoveryDialogVisible).toBe(false)
  })

  it('posts workflow_name when starting execution', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        status: 'started',
        execution_id: 'exec-post',
        workflow_id: 'wf_a',
        draft_revision: null,
      },
    })
    const execution = useExecutionStore()
    const graph = makeGraph()

    await execution.run(graph, undefined, 'wf_a')

    expect(api.post).toHaveBeenCalledWith('/api/v1/execution/run', {
      graph,
      nodes: undefined,
      workflow_name: 'wf_a',
    })
  })

  it('captures root execution identity and sends the accepted draft revision', async () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        status: 'started',
        execution_id: 'exec-123',
        workflow_id: 'wf_a',
        draft_revision: 7,
      },
    })
    const execution = useExecutionStore()
    const graph = makeGraph()

    await execution.run(graph, undefined, 'wf_a', {
      canvasId,
      draftRevision: 7,
    })

    expect(api.post).toHaveBeenCalledWith('/api/v1/execution/run', {
      graph,
      nodes: undefined,
      workflow_name: 'wf_a',
      draft_revision: 7,
    })
    expect(execution.executionId).toBe('exec-123')
    expect(execution.executionWorkflowId).toBe('wf_a')
    expect(execution.executionDraftRevision).toBe(7)
    expect(execution.originCanvasId).toBe(canvasId)
    expect(execution.originGraph).toEqual(graph)
  })

  it.each(['draft_revision_conflict', 'draft_graph_mismatch'])(
    'retains the machine-readable Run conflict code %s',
    async (errorCode) => {
      vi.mocked(api.post).mockRejectedValueOnce({
        response: {
          status: 409,
          data: { error: errorCode, detail: 'Execution input is stale' },
        },
      })
      const execution = useExecutionStore()

      await expect(
        execution.run({ nodes: [], edges: [] }, undefined, 'wf_a'),
      ).rejects.toBeTruthy()

      expect(execution.isConflict).toBe(true)
      expect(execution.conflictCode).toBe(errorCode)
    },
  )

  it('accepts a matching WebSocket event before the Run response', async () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const response = deferred<{ data: Record<string, unknown> }>()
    vi.mocked(api.post).mockReturnValueOnce(response.promise as never)
    const execution = useExecutionStore()
    const graph = makeGraph()

    const run = execution.run(graph, undefined, 'wf_a', {
      canvasId,
      draftRevision: 7,
    })
    execution.applyNodeState({
      type: 'node_state',
      execution_id: 'exec-123',
      workflow_id: 'wf_a',
      draft_revision: 7,
      node_id: 'same',
      status: 'running',
      cached: false,
    })

    expect(execution.executionId).toBe('exec-123')
    expect(execution.originCanvasId).toBe(canvasId)
    expect(execution.nodeStatuses.same?.status).toBe('running')
    response.resolve({
      data: {
        status: 'started',
        execution_id: 'exec-123',
        workflow_id: 'wf_a',
        draft_revision: 7,
      },
    })
    await run

    expect(execution.state).toBe('running')
    expect(execution.nodeStatuses.same?.status).toBe('running')
  })

  it('keeps the discovered WebSocket run active when later IDs mismatch', async () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const response = deferred<{ data: Record<string, unknown> }>()
    vi.mocked(api.post).mockReturnValueOnce(response.promise as never)
    const execution = useExecutionStore()

    const run = execution.run({ nodes: [], edges: [] }, undefined, 'wf_a', {
      canvasId,
      draftRevision: 7,
    })
    execution.applyNodeState({
      execution_id: 'exec-accepted',
      workflow_id: 'wf_a',
      draft_revision: 7,
      node_id: 'same',
      status: 'running',
      cached: false,
    })
    execution.applyNodeState({
      execution_id: 'exec-mismatch',
      workflow_id: 'wf_a',
      draft_revision: 7,
      node_id: 'same',
      status: 'failed',
      cached: false,
      error: 'wrong run',
    })
    response.resolve({
      data: {
        status: 'started',
        execution_id: 'exec-mismatch',
        workflow_id: 'wf_a',
        draft_revision: 7,
      },
    })

    await expect(run).rejects.toThrow('mismatched context')
    expect(execution.executionId).toBe('exec-accepted')
    expect(execution.state).toBe('running')
    expect(execution.nodeStatuses.same?.status).toBe('running')
    expect(execution.isMutationLocked).toBe(true)
  })

  it('ignores contextless execution messages for a context-aware root run', async () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const response = deferred<{ data: Record<string, unknown> }>()
    vi.mocked(api.post).mockReturnValueOnce(response.promise as never)
    const execution = useExecutionStore()

    const run = execution.run({ nodes: [], edges: [] }, undefined, 'wf_a', {
      canvasId,
      draftRevision: 7,
    })
    execution.applyNodeState({
      node_id: 'legacy',
      status: 'failed',
      cached: false,
      error: 'unscoped',
    } as never)
    response.resolve({
      data: {
        status: 'started',
        execution_id: 'exec-accepted',
        workflow_id: 'wf_a',
        draft_revision: 7,
      },
    })
    await run
    execution.applyExecutionComplete({
      success: true,
      errors: [],
      node_statuses: {},
    } as never)

    expect(execution.nodeStatuses.legacy).toBeUndefined()
    expect(execution.executionId).toBe('exec-accepted')
    expect(execution.state).toBe('running')
  })

  it('accepts contextless idle startup snapshots but rejects contextless running snapshots', () => {
    const execution = useExecutionStore()

    execution.applyStatusSnapshot({
      state: 'idle',
      last_result: null,
      progress: null,
      node_statuses: {},
    })
    execution.applyStatusSnapshot({
      state: 'running',
      last_result: null,
      progress: { node_id: 'legacy', row: 1, total_rows: 2 },
      node_statuses: {
        legacy: { node_id: 'legacy', status: 'running', cached: false },
      },
    })

    expect(execution.state).toBe('idle')
    expect(execution.progress).toBeNull()
    expect(execution.nodeStatuses).toEqual({})
    expect(execution.executionId).toBeNull()
  })

  it('keeps a matching completion that arrives before the Run response', async () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const response = deferred<{ data: Record<string, unknown> }>()
    vi.mocked(api.post).mockReturnValueOnce(response.promise as never)
    const execution = useExecutionStore()

    const run = execution.run({ nodes: [], edges: [] }, undefined, 'wf_a', {
      canvasId,
      draftRevision: 7,
    })
    execution.applyExecutionComplete({
      type: 'execution_complete',
      execution_id: 'exec-fast',
      workflow_id: 'wf_a',
      draft_revision: 7,
      success: true,
      errors: [],
      node_statuses: {},
    })
    response.resolve({
      data: {
        status: 'started',
        execution_id: 'exec-fast',
        workflow_id: 'wf_a',
        draft_revision: 7,
      },
    })
    await run

    expect(execution.state).toBe('idle')
    expect(execution.lastResult?.success).toBe(true)
    expect(execution.executionId).toBe('exec-fast')
  })

  it('keeps a completed WebSocket run fenced when the Run response is mismatched', async () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const response = deferred<{ data: Record<string, unknown> }>()
    vi.mocked(api.post).mockReturnValueOnce(response.promise as never)
    const execution = useExecutionStore()

    const run = execution.run({ nodes: [], edges: [] }, undefined, 'wf_a', {
      canvasId,
      draftRevision: 7,
    })
    execution.applyExecutionComplete({
      type: 'execution_complete',
      execution_id: 'exec-fast',
      workflow_id: 'wf_a',
      draft_revision: 7,
      success: true,
      errors: [],
      node_statuses: {},
    })
    response.resolve({
      data: {
        status: 'started',
        execution_id: 'exec-mismatch',
        workflow_id: 'wf_a',
        draft_revision: 7,
      },
    })

    await expect(run).rejects.toThrow('mismatched context')

    execution.applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-fast',
      workflow_id: 'wf_a',
      draft_revision: 7,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {},
    })

    expect(execution.state).toBe('idle')
    expect(execution.executionId).toBe('exec-fast')
    expect(execution.lastResult?.success).toBe(true)
  })

  it('keeps a matching idle snapshot that arrives before the Run response', async () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    const response = deferred<{ data: Record<string, unknown> }>()
    vi.mocked(api.post).mockReturnValueOnce(response.promise as never)
    const execution = useExecutionStore()

    const run = execution.run({ nodes: [], edges: [] }, undefined, 'wf_a', {
      canvasId,
      draftRevision: 7,
    })
    execution.applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-fast',
      workflow_id: 'wf_a',
      draft_revision: 7,
      state: 'idle',
      progress: null,
      last_result: { success: true, errors: [], node_statuses: {} },
      node_statuses: {},
    })
    response.resolve({
      data: {
        status: 'started',
        execution_id: 'exec-fast',
        workflow_id: 'wf_a',
        draft_revision: 7,
      },
    })
    await run

    expect(execution.state).toBe('idle')
    expect(execution.lastResult?.success).toBe(true)
  })

  it('rejects late events from an older execution id', () => {
    const execution = useExecutionStore()
    execution.applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-new',
      workflow_id: 'wf_a',
      draft_revision: 8,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {
        same: { node_id: 'same', status: 'running', cached: false },
      },
    })

    execution.applyNodeState({
      type: 'node_state',
      execution_id: 'exec-old',
      workflow_id: 'wf_a',
      draft_revision: 7,
      node_id: 'same',
      status: 'failed',
      cached: false,
      error: 'late failure',
    })

    expect(execution.executionId).toBe('exec-new')
    expect(execution.nodeStatuses.same?.status).toBe('running')
  })

  it('routes reconnect identity to one matching open root canvas', () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'wf_a' })
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'wf_b' })
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasA, 'wf_a', 'Workflow A')
    ui.setCanvasWorkflow(canvasB, 'wf_b', 'Workflow B')
    canvasSessionRegistry.activate(canvasB)
    const execution = useExecutionStore()

    execution.applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-123',
      workflow_id: 'wf_a',
      draft_revision: 7,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {},
    })

    expect(execution.originCanvasId).toBe(canvasA)
    expect(execution.appliesToCanvas(canvasA)).toBe(true)
    expect(execution.appliesToCanvas(canvasB)).toBe(false)
    expect(execution.isMutationLocked).toBe(true)
  })

  it('resolves a reconnect origin when its root canvas registers later', () => {
    const execution = useExecutionStore()
    const canvasId = canvasIdFromPanelId('workflow:a')
    execution.applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-123',
      workflow_id: 'wf_a',
      draft_revision: 7,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {},
    })
    expect(execution.originCanvasId).toBeNull()

    canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'wf_a' })
    useUIStore().setCanvasWorkflow(canvasId, 'wf_a', 'Workflow A')

    expect(execution.appliesToCanvas(canvasId)).toBe(true)
    expect(execution.originCanvasId).toBe(canvasId)
  })

  it('does not infer a root execution origin from an active nested canvas', () => {
    const rootCanvas = canvasIdFromPanelId('workflow:a')
    const nestedCanvas = canvasIdFromPanelId('sub-workflow:nested')
    canvasSessionRegistry.register({
      kind: 'root',
      canvasId: rootCanvas,
      workflowId: 'wf_a',
    })
    canvasSessionRegistry.register({
      kind: 'nested',
      canvasId: nestedCanvas,
      sessionId: 'nested',
      parentCanvasId: rootCanvas,
    })
    const ui = useUIStore()
    ui.setCanvasWorkflow(rootCanvas, 'wf_a', 'Workflow A')
    ui.setCanvasWorkflow(nestedCanvas, 'wf_a', 'Nested editor')
    canvasSessionRegistry.activate(nestedCanvas)

    const execution = useExecutionStore()
    execution.applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-123',
      workflow_id: 'wf_a',
      draft_revision: 7,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {},
    })

    expect(execution.originCanvasId).toBe(rootCanvas)
    expect(execution.appliesToCanvas(rootCanvas)).toBe(true)
    expect(execution.appliesToCanvas(nestedCanvas)).toBe(false)
  })

  it('uses the active root to disambiguate duplicate workflow canvases', () => {
    const canvasA = canvasIdFromPanelId('workflow:a-copy-1')
    const canvasB = canvasIdFromPanelId('workflow:a-copy-2')
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'wf_a' })
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'wf_a' })
    const ui = useUIStore()
    ui.setCanvasWorkflow(canvasA, 'wf_a', 'Workflow A')
    ui.setCanvasWorkflow(canvasB, 'wf_a', 'Workflow A')
    canvasSessionRegistry.activate(canvasB)

    const execution = useExecutionStore()
    execution.applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-123',
      workflow_id: 'wf_a',
      draft_revision: 7,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {},
    })

    expect(execution.originCanvasId).toBe(canvasB)
    expect(execution.appliesToCanvas(canvasA)).toBe(false)
    expect(execution.appliesToCanvas(canvasB)).toBe(true)
  })

  it('stops applying to a disposed origin until that canvas registers again', () => {
    const canvasId = canvasIdFromPanelId('workflow:a')
    canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'wf_a' })
    useUIStore().setCanvasWorkflow(canvasId, 'wf_a', 'Workflow A')
    const execution = useExecutionStore()
    execution.applyStatusSnapshot({
      type: 'status_snapshot',
      execution_id: 'exec-123',
      workflow_id: 'wf_a',
      draft_revision: 7,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {},
    })
    expect(execution.appliesToCanvas(canvasId)).toBe(true)

    canvasSessionRegistry.unregister(canvasId)
    expect(execution.appliesToCanvas(canvasId)).toBe(false)
    expect(execution.isMutationLocked).toBe(true)

    useUIStore().releaseCanvasPresentation(canvasId)
    canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'wf_b' })
    useUIStore().setCanvasWorkflow(canvasId, 'wf_b', 'Workflow B')
    expect(execution.appliesToCanvas(canvasId)).toBe(false)

    canvasSessionRegistry.unregister(canvasId)
    useUIStore().releaseCanvasPresentation(canvasId)
    canvasSessionRegistry.register({ kind: 'root', canvasId, workflowId: 'wf_a' })
    useUIStore().setCanvasWorkflow(canvasId, 'wf_a', 'Workflow A')
    expect(execution.appliesToCanvas(canvasId)).toBe(true)
  })

  it('rejects anonymous execution state without assigning it to any canvas', () => {
    const canvasA = canvasIdFromPanelId('workflow:a')
    const canvasB = canvasIdFromPanelId('workflow:b')
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasA, workflowId: 'wf_a' })
    canvasSessionRegistry.register({ kind: 'root', canvasId: canvasB, workflowId: 'wf_b' })
    const execution = useExecutionStore()

    canvasSessionRegistry.activate(canvasA)
    execution.applyNodeState({
      node_id: 'same',
      status: 'running',
      cached: false,
    } as never)
    expect(execution.nodeStatuses.same).toBeUndefined()
    expect(execution.appliesToCanvas(canvasA)).toBe(false)
    expect(execution.appliesToCanvas(canvasB)).toBe(false)

    canvasSessionRegistry.activate(canvasB)
    expect(execution.appliesToCanvas(canvasA)).toBe(false)
    expect(execution.appliesToCanvas(canvasB)).toBe(false)

    execution.applyNodeState({
      node_id: 'same',
      status: 'executed',
      cached: false,
    } as never)
    expect(execution.appliesToCanvas(canvasA)).toBe(false)
    expect(execution.appliesToCanvas(canvasB)).toBe(false)

    canvasSessionRegistry.activate(null)
    execution.applyNodeState({
      node_id: 'same',
      status: 'unexecuted',
      cached: false,
    } as never)
    expect(execution.appliesToCanvas(canvasA)).toBe(false)
    expect(execution.appliesToCanvas(canvasB)).toBe(false)

    canvasSessionRegistry.unregister(canvasB)
    expect(execution.appliesToCanvas(canvasA)).toBe(false)
  })

  it('lets a newer running reconnect snapshot replace a terminal context', () => {
    const execution = useExecutionStore()
    execution.applyStatusSnapshot({
      execution_id: 'exec-old',
      workflow_id: 'wf_a',
      draft_revision: 7,
      state: 'idle',
      last_result: { success: true, errors: [], node_statuses: {} },
      progress: null,
      node_statuses: {},
    })

    execution.applyStatusSnapshot({
      execution_id: 'exec-new',
      workflow_id: 'wf_a',
      draft_revision: 8,
      state: 'running',
      last_result: null,
      progress: null,
      node_statuses: {},
    })

    expect(execution.executionId).toBe('exec-new')
    expect(execution.state).toBe('running')
  })

  it('keeps the prior terminal context when a new start is rejected', async () => {
    const execution = useExecutionStore()
    const canvasId = canvasIdFromPanelId('workflow:a')
    execution.applyStatusSnapshot({
      execution_id: 'exec-old',
      workflow_id: 'wf_a',
      draft_revision: 7,
      state: 'idle',
      last_result: { success: true, errors: [], node_statuses: {} },
      progress: null,
      node_statuses: {},
    })
    vi.mocked(api.post).mockRejectedValueOnce({
      response: { status: 422, data: { errors: [] } },
      message: 'rejected',
    })

    await expect(execution.run(
      { nodes: [], edges: [] },
      undefined,
      'wf_a',
      { canvasId, draftRevision: 8 },
    )).rejects.toMatchObject({ message: 'rejected' })

    expect(execution.executionId).toBe('exec-old')
    expect(execution.executionDraftRevision).toBe(7)
    expect(execution.lastResult?.success).toBe(true)
  })

  it('posts workflow_name when clearing cache', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { node_statuses: {} } })
    const execution = useExecutionStore()
    const graph = { nodes: [], edges: [] }

    await execution.clear(graph, ['n1'], 'wf_a')

    expect(api.post).toHaveBeenCalledWith('/api/v1/execution/clear', {
      graph,
      nodes: ['n1'],
      workflow_name: 'wf_a',
    })
  })
})
