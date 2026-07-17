import { describe, expect, it, vi } from 'vitest'
import type { GraphState, ValidationResult } from '@/api/types'
import type { NestedWorkflowSnapshotResponse } from '@/api/nestedWorkflowSnapshots'
import { canvasIdFromPanelId } from '../canvasSessionRegistry'
import {
  createNestedSnapshotPersistence,
  NestedSnapshotPersistenceConflictError,
  type NestedSnapshotPersistenceTransport,
} from '../nestedSnapshotPersistence'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function graph(nodeId: string, publishedName = 'image'): GraphState {
  return {
    nodes: [{
      id: nodeId,
      name: nodeId,
      tool_name: 'tool',
      position: [0, 0],
      parameters: {},
      resources: {},
      output_templates: {},
      enabled: true,
      collapsed: false,
    }],
    edges: [],
    published_inputs: [{
      name: publishedName,
      internal_node_id: nodeId,
      internal_field: 'image',
      kind: 'input',
      schema: { type: 'Path' },
      default: null,
    }],
    published_outputs: [],
  }
}

function validation(nodeId: string): ValidationResult {
  return {
    valid: true,
    node_statuses: {
      [nodeId]: { node_id: nodeId, status: 'unexecuted', cached: false },
    },
    errors: [],
  }
}

function response(
  revision: number,
  acceptedGraph: GraphState,
): NestedWorkflowSnapshotResponse {
  return {
    snapshot_version: 1,
    session_id: 'f16fd9d4-18e5-4d73-a9df-b7675ef44c9e',
    owner: { kind: 'root', canvas_id: 'canvas', workflow_id: null },
    parent_node_id: 'sub_1',
    snapshot_revision: revision,
    updated_at: `2026-07-16T00:00:0${revision}Z`,
    graph: acceptedGraph,
    validation: validation(acceptedGraph.nodes[0]!.id),
  }
}

describe('nested snapshot persistence', () => {
  it('joins an in-flight write and returns the newest exact accepted document', async () => {
    const first = deferred<NestedWorkflowSnapshotResponse>()
    const second = deferred<NestedWorkflowSnapshotResponse>()
    const transport: NestedSnapshotPersistenceTransport = {
      get: vi.fn(),
      put: vi.fn()
        .mockReturnValueOnce(first.promise)
        .mockReturnValueOnce(second.promise),
      delete: vi.fn(),
    }
    const accepted = vi.fn()
    const resource = createNestedSnapshotPersistence({
      canvasId: canvasIdFromPanelId('sub-workflow:session'),
      initialSnapshot: response(4, graph('initial')),
      transport,
      debounceMs: 60_000,
      onAccepted: accepted,
    })
    const graphA = graph('a', 'source_a')
    const graphB = graph('b', 'source_b')

    resource.queue(graphA)
    const flushing = resource.flushLatest()
    await Promise.resolve()
    expect(transport.put).toHaveBeenCalledWith(expect.objectContaining({
      expectedRevision: 4,
      graph: graphA,
    }))

    resource.queue(graphB)
    first.resolve(response(5, graphA))
    await vi.waitFor(() => {
    expect(transport.put).toHaveBeenCalledWith(expect.objectContaining({
      expectedRevision: 5,
      graph: graphB,
    }))
    })

    const normalizedGraphB = graph('b', 'source_b')
    normalizedGraphB.nodes[0]!.name = 'server-normalized-b'
    second.resolve(response(6, normalizedGraphB))
    await expect(flushing).resolves.toEqual({
      graph: normalizedGraphB,
      validation: validation('b'),
      snapshotRevision: 6,
    })
    expect(resource.validationResult.value).toEqual(validation('b'))
    expect(accepted).toHaveBeenLastCalledWith(response(6, normalizedGraphB))
  })

  it('deletes only after flushing and uses the newest accepted revision', async () => {
    const transport: NestedSnapshotPersistenceTransport = {
      get: vi.fn(),
      put: vi.fn().mockResolvedValue(response(3, graph('changed'))),
      delete: vi.fn().mockResolvedValue(undefined),
    }
    const resource = createNestedSnapshotPersistence({
      canvasId: canvasIdFromPanelId('sub-workflow:session'),
      initialSnapshot: response(2, graph('initial')),
      transport,
      debounceMs: 60_000,
    })

    resource.queue(graph('changed'))
    await resource.deleteLatest()

    expect(transport.delete).toHaveBeenCalledWith(expect.objectContaining({
      sessionId: 'f16fd9d4-18e5-4d73-a9df-b7675ef44c9e',
      expectedRevision: 3,
    }))
  })

  it('holds a revision conflict and rebases the latest local graph only after an explicit action', async () => {
    const rawConflict = {
      response: {
        status: 409,
        data: {
          detail: 'Nested snapshot revision conflict: expected 4, current is 5',
          expected_revision: 4,
          current_revision: 5,
        },
      },
    }
    const remote = response(5, graph('remote'))
    const latestLocal = graph('latest-local')
    const transport: NestedSnapshotPersistenceTransport = {
      get: vi.fn().mockResolvedValue(remote),
      put: vi.fn()
        .mockRejectedValueOnce(rawConflict)
        .mockResolvedValueOnce(response(6, latestLocal)),
      delete: vi.fn(),
    }
    const accepted = vi.fn()
    const resource = createNestedSnapshotPersistence({
      canvasId: canvasIdFromPanelId('sub-workflow:session'),
      initialSnapshot: response(4, graph('initial')),
      transport,
      debounceMs: 60_000,
      onAccepted: accepted,
    })

    resource.queue(graph('conflicting-local'))
    const firstFlush = resource.flushLatest()
    await expect(firstFlush).rejects.toMatchObject({
      expectedRevision: 4,
      currentRevision: 5,
    })
    const conflict = resource.coordinator.lastError.value
    expect(conflict).toBeInstanceOf(NestedSnapshotPersistenceConflictError)
    expect(resource.coordinator.syncState.value).toBe('conflict')

    await expect(resource.flushLatest()).rejects.toBe(conflict)
    expect(transport.put).toHaveBeenCalledOnce()

    resource.queue(latestLocal)
    expect(resource.coordinator.syncState.value).toBe('conflict')
    expect(transport.put).toHaveBeenCalledOnce()

    await expect(resource.resolveConflictKeepingLocal()).resolves.toEqual({
      graph: latestLocal,
      validation: validation('latest-local'),
      snapshotRevision: 6,
    })
    expect(transport.get).toHaveBeenCalledWith({
      sessionId: 'f16fd9d4-18e5-4d73-a9df-b7675ef44c9e',
      signal: expect.any(AbortSignal),
    })
    expect(transport.put).toHaveBeenLastCalledWith(expect.objectContaining({
      expectedRevision: 5,
      graph: latestLocal,
    }))
    expect(accepted).toHaveBeenNthCalledWith(1, remote)
    expect(accepted).toHaveBeenLastCalledWith(response(6, latestLocal))
    expect(resource.coordinator.syncState.value).toBe('idle')
    expect(resource.coordinator.lastError.value).toBeNull()
  })

  it('replaces conflicted local work with the explicitly selected latest snapshot without another PUT', async () => {
    const rawConflict = {
      response: {
        status: 409,
        data: { detail: 'revision conflict', current_revision: 5 },
      },
    }
    const remote = response(5, graph('remote'))
    const transport: NestedSnapshotPersistenceTransport = {
      get: vi.fn().mockResolvedValue(remote),
      put: vi.fn().mockRejectedValueOnce(rawConflict),
      delete: vi.fn(),
    }
    const accepted = vi.fn()
    const resource = createNestedSnapshotPersistence({
      canvasId: canvasIdFromPanelId('sub-workflow:session'),
      initialSnapshot: response(4, graph('initial')),
      transport,
      debounceMs: 60_000,
      onAccepted: accepted,
    })

    resource.queue(graph('discarded-local'))
    await expect(resource.flushLatest()).rejects.toBeInstanceOf(
      NestedSnapshotPersistenceConflictError,
    )
    const conflict = resource.coordinator.lastError.value
    await expect(resource.flushLatest()).rejects.toBe(conflict)
    expect(transport.put).toHaveBeenCalledOnce()

    await expect(resource.resolveConflictUsingRemote()).resolves.toEqual({
      graph: remote.graph,
      validation: remote.validation,
      snapshotRevision: 5,
    })
    expect(resource.currentGraph.value).toEqual(remote.graph)
    expect(resource.validationResult.value).toEqual(remote.validation)
    expect(resource.coordinator.syncState.value).toBe('idle')
    expect(resource.coordinator.isPending.value).toBe(false)
    expect(resource.coordinator.lastError.value).toBeNull()
    await expect(resource.flushLatest()).resolves.toEqual({
      graph: remote.graph,
      validation: remote.validation,
      snapshotRevision: 5,
    })
    expect(transport.put).toHaveBeenCalledOnce()
    expect(accepted).toHaveBeenCalledOnce()
    expect(accepted).toHaveBeenCalledWith(remote)
  })
})
