import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { GraphState } from '@/api/types'
import type { NestedWorkflowSnapshotResponse } from '@/api/nestedWorkflowSnapshots'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'

const snapshotApiMocks = vi.hoisted(() => ({
  put: vi.fn(),
  delete: vi.fn(),
}))

vi.mock('@/api/nestedWorkflowSnapshots', () => ({
  putNestedWorkflowSnapshot: snapshotApiMocks.put,
  deleteNestedWorkflowSnapshot: snapshotApiMocks.delete,
}))

import {
  _resetGraphSyncForTest,
  forgetRetainedNestedSnapshot,
  flushRetainedNestedSnapshot,
  useGraphSync,
} from '../useGraphSync'

function graph(value: string): GraphState {
  return {
    nodes: [{
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
  }
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
        canvasId: canvasIdFromPanelId(`sub-workflow:${sessionId}`),
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
    const canvasId = canvasIdFromPanelId(`sub-workflow:${sessionId}`)
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

  it('rejects a nested canvas without an accepted durable snapshot', () => {
    expect(() => useGraphSync({
      descriptor: {
        kind: 'nested',
        canvasId: canvasIdFromPanelId('sub-workflow:missing'),
        sessionId: 'missing',
        parentCanvasId: canvasIdFromPanelId('workflow:parent'),
      },
      getWorkflowId: () => 'parent',
    })).toThrow('Nested graph sync requires an accepted durable snapshot')
  })
})
