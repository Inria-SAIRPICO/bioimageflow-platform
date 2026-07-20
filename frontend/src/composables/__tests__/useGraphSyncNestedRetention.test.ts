import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { GraphState } from '@/api/types'
import type { NestedWorkflowSnapshotResponse } from '@/api/nestedWorkflowSnapshots'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'
import { makeGraph } from '@/test-utils/graphFixtures'

const snapshotApiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/nestedWorkflowSnapshots', () => ({
  getNestedWorkflowSnapshot: snapshotApiMocks.get,
  putNestedWorkflowSnapshot: snapshotApiMocks.put,
  deleteNestedWorkflowSnapshot: snapshotApiMocks.delete,
}))

import {
  _resetGraphSyncForTest,
  activateGraphSyncCanvas,
  forgetRetainedNestedSnapshot,
  flushRetainedNestedSnapshot,
  useGraphSync,
} from '../useGraphSync'
import { NestedSnapshotPersistenceConflictError } from '@/sessions/nestedSnapshotPersistence'

function graph(value: string): GraphState {
  return makeGraph({
    nodes: [{
      type: 'tool',
      id: 'inner',
      name: 'Inner',
      tool_name: 'tool',
      position: [0, 0],
      parameters: { value },
      resources: {},
      output_templates: {},
      enabled: true,
      collapsed: false,
    }],
    edges: [],
  })
}

function snapshot(
  revision: number,
  acceptedGraph: GraphState,
): NestedWorkflowSnapshotResponse {
  return {
    snapshot_version: 1,
    session_id: '00000000-0000-4000-8000-000000000001',
    owner: {
      kind: 'root',
      canvas_id: 'workflow:parent',
      workflow_id: 'parent',
    },
    parent_node_id: 'sub_1',
    snapshot_revision: revision,
    updated_at: `2026-07-16T00:00:0${revision}Z`,
    graph: acceptedGraph,
    validation: { valid: true, node_statuses: {}, errors: [] },
  }
}

describe('retained nested snapshot graph sync', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    snapshotApiMocks.put.mockReset()
    snapshotApiMocks.get.mockReset()
    snapshotApiMocks.delete.mockReset()
    _resetGraphSyncForTest()
  })

  afterEach(() => {
    _resetGraphSyncForTest()
  })

  it('flushes the retained durable writer by session identity', async () => {
    const sessionId = '00000000-0000-4000-8000-000000000001'
    const changed = graph('changed')
    snapshotApiMocks.put.mockResolvedValueOnce(snapshot(2, changed))
    const sync = useGraphSync({
      descriptor: {
        kind: 'nested',
        canvasId: canvasIdFromPanelId(`nested-workflow:${sessionId}`),
        sessionId,
        parentCanvasId: canvasIdFromPanelId('workflow:parent'),
      },
      getWorkflowId: () => 'parent',
      nestedSnapshot: { initialSnapshot: snapshot(1, graph('initial')) },
    })
    sync.syncGraphState(changed)

    await flushRetainedNestedSnapshot(sessionId)

    expect(snapshotApiMocks.put).toHaveBeenCalledWith(
      sessionId,
      { expected_revision: 1, graph: changed },
      expect.any(AbortSignal),
    )
  })

  it('is a no-op when the nested writer is not mounted', async () => {
    await expect(flushRetainedNestedSnapshot('missing-session')).resolves.toBeUndefined()
    expect(snapshotApiMocks.put).not.toHaveBeenCalled()
  })

  it('retains a writer across ordinary tab disposal but forgets it after root deletion', async () => {
    const sessionId = '00000000-0000-4000-8000-000000000001'
    const canvasId = canvasIdFromPanelId(`nested-workflow:${sessionId}`)
    const sync = useGraphSync({
      descriptor: {
        kind: 'nested',
        canvasId,
        sessionId,
        parentCanvasId: canvasIdFromPanelId('workflow:parent'),
      },
      getWorkflowId: () => 'parent',
      nestedSnapshot: { initialSnapshot: snapshot(1, graph('initial')) },
    })

    sync.dispose()
    snapshotApiMocks.put.mockResolvedValueOnce(snapshot(2, graph('retained')))
    const reopened = useGraphSync({
      descriptor: {
        kind: 'nested',
        canvasId,
        sessionId,
        parentCanvasId: canvasIdFromPanelId('workflow:parent'),
      },
      getWorkflowId: () => 'parent',
      nestedSnapshot: { initialSnapshot: snapshot(1, graph('stale-reopen')) },
    })
    reopened.syncGraphState(graph('retained'))
    await flushRetainedNestedSnapshot(sessionId)
    expect(snapshotApiMocks.put).toHaveBeenCalledOnce()

    expect(forgetRetainedNestedSnapshot(sessionId)).toBe(true)
    expect(forgetRetainedNestedSnapshot(sessionId)).toBe(false)
    await expect(flushRetainedNestedSnapshot(sessionId)).resolves.toBeUndefined()
  })

  it('exposes only the latest nested persistence failure through fixed and active APIs', async () => {
    const sessionId = '00000000-0000-4000-8000-000000000001'
    const canvasId = canvasIdFromPanelId(`nested-workflow:${sessionId}`)
    const failure = new Error('nested snapshot unavailable')
    const recovered = graph('recovered')
    snapshotApiMocks.put
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(snapshot(2, recovered))
    const sync = useGraphSync({
      descriptor: {
        kind: 'nested',
        canvasId,
        sessionId,
        parentCanvasId: canvasIdFromPanelId('workflow:parent'),
      },
      getWorkflowId: () => 'parent',
      nestedSnapshot: { initialSnapshot: snapshot(1, graph('initial')) },
    })
    const active = useGraphSync()
    activateGraphSyncCanvas(canvasId)

    sync.syncGraphState(graph('failed'))
    await expect(sync.flushNow()).rejects.toBe(failure)

    expect(sync.lastError.value).toBe(failure)
    expect(active.lastError.value).toBe(failure)

    sync.syncGraphState(recovered)
    expect(sync.lastError.value).toBeNull()
    expect(active.lastError.value).toBeNull()

    await expect(sync.flushNow()).resolves.toMatchObject({
      graph: recovered,
      snapshotRevision: 2,
    })
    expect(sync.lastError.value).toBeNull()
    expect(active.lastError.value).toBeNull()
  })

  it('routes an explicit nested conflict resolution through the fixed and active APIs', async () => {
    const sessionId = '00000000-0000-4000-8000-000000000001'
    const canvasId = canvasIdFromPanelId(`nested-workflow:${sessionId}`)
    const conflict = {
      response: {
        status: 409,
        data: { detail: 'revision conflict', current_revision: 2 },
      },
    }
    const latest = graph('latest-local')
    snapshotApiMocks.put
      .mockRejectedValueOnce(conflict)
      .mockResolvedValueOnce(snapshot(3, latest))
    snapshotApiMocks.get.mockResolvedValueOnce(snapshot(2, graph('remote')))
    const sync = useGraphSync({
      descriptor: {
        kind: 'nested',
        canvasId,
        sessionId,
        parentCanvasId: canvasIdFromPanelId('workflow:parent'),
      },
      getWorkflowId: () => 'parent',
      nestedSnapshot: { initialSnapshot: snapshot(1, graph('initial')) },
    })
    const active = useGraphSync()
    activateGraphSyncCanvas(canvasId)

    sync.syncGraphState(graph('conflicting'))
    await expect(sync.flushNow()).rejects.toBeInstanceOf(
      NestedSnapshotPersistenceConflictError,
    )
    expect(sync.syncState.value).toBe('conflict')
    expect(active.syncState.value).toBe('conflict')
    await expect(active.flushNow()).rejects.toBe(sync.lastError.value)
    expect(snapshotApiMocks.put).toHaveBeenCalledOnce()

    sync.syncGraphState(latest)
    await expect(active.resolveConflictKeepingLocal()).resolves.toMatchObject({
      graph: latest,
      snapshotRevision: 3,
    })
    expect(snapshotApiMocks.get).toHaveBeenCalledWith(
      sessionId,
      expect.any(AbortSignal),
    )
    expect(snapshotApiMocks.put).toHaveBeenLastCalledWith(
      sessionId,
      { expected_revision: 2, graph: latest },
      expect.any(AbortSignal),
    )
    expect(sync.syncState.value).toBe('idle')
    expect(active.lastError.value).toBeNull()
  })

  it('rejects a nested canvas without an accepted durable snapshot', () => {
    expect(() => useGraphSync({
      descriptor: {
        kind: 'nested',
        canvasId: canvasIdFromPanelId('nested-workflow:missing'),
        sessionId: 'missing',
        parentCanvasId: canvasIdFromPanelId('workflow:parent'),
      },
      getWorkflowId: () => 'parent',
    })).toThrow('Nested graph sync requires an accepted durable snapshot')
  })
})
