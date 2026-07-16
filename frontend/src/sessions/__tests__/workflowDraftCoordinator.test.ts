import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import { canvasIdFromPanelId } from '../canvasSessionRegistry'
import {
  WorkflowDraftCoordinatorDisposedError,
  createWorkflowDraftCoordinator,
  type WorkflowDraftWriteRequest,
} from '../workflowDraftCoordinator'
import {
  makeGraph,
  makeGraphNode,
  makeValidationResult,
} from '@/test-utils/graphFixtures'
import { makeWorkflowDraft } from '@/test-utils/persistenceFixtures'
import { deferred } from '@/test-utils/asyncFixtures'

function graph(value: string) {
  return makeGraph({
    nodes: [makeGraphNode({ parameters: { value } })],
  })
}

function response(
  draftRevision: number,
  value = `revision-${draftRevision}`,
  workflowId = 'workflow-a',
): WorkflowDraftResponse {
  return makeWorkflowDraft({
    workflow_id: workflowId,
    base_saved_revision: 'sha256:base',
    draft_revision: draftRevision,
    updated_at: '2026-07-15T12:00:00Z',
    dirty_against_saved: true,
    graph: graph(value),
    validation: makeValidationResult(),
  })
}

describe('workflow draft coordinator', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('captures canvas, workflow, and a cloned graph when queued', async () => {
    const requests: WorkflowDraftWriteRequest[] = []
    const coordinator = createWorkflowDraftCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'folder/workflow-a',
      initialDraftRevision: 4,
      transport: vi.fn(async (request) => {
        requests.push(request)
        return response(5, 'saved', request.workflowId)
      }),
    })
    const queued = graph('queued')

    coordinator.queue(queued)
    queued.nodes[0]!.parameters = { value: 'mutated-after-queue' }

    expect(coordinator.isPending.value).toBe(true)
    await coordinator.flushLatest()

    expect(requests[0]).toMatchObject({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'folder/workflow-a',
      queueRevision: 1,
      expectedDraftRevision: 4,
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'queued' } })],
      }),
    })
    expect(coordinator.isPending.value).toBe(false)
  })

  it('serializes writes, coalesces edits, and chains accepted backend revisions', async () => {
    const first = deferred<WorkflowDraftResponse>()
    const second = deferred<WorkflowDraftResponse>()
    let activeWrites = 0
    let maxActiveWrites = 0
    const transport = vi.fn((request: WorkflowDraftWriteRequest) => {
      activeWrites += 1
      maxActiveWrites = Math.max(maxActiveWrites, activeWrites)
      const pending = transport.mock.calls.length === 1 ? first : second
      return pending.promise.finally(() => {
        activeWrites -= 1
      })
    })
    const coordinator = createWorkflowDraftCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'workflow-a',
      initialDraftRevision: 1,
      transport,
    })

    coordinator.queue(graph('old'))
    const flushing = coordinator.flushLatest()
    await vi.advanceTimersByTimeAsync(0)
    expect(transport).toHaveBeenCalledTimes(1)

    coordinator.queue(graph('middle'))
    coordinator.queue(graph('newest'))
    const joiningFlush = coordinator.flushLatest()
    expect(transport).toHaveBeenCalledTimes(1)

    first.resolve(response(2, 'old'))
    await vi.advanceTimersByTimeAsync(0)
    expect(transport).toHaveBeenCalledTimes(2)
    expect(transport.mock.calls[1]?.[0]).toMatchObject({
      queueRevision: 3,
      expectedDraftRevision: 2,
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'newest' } })],
      }),
    })

    second.resolve(response(3, 'newest'))
    const [firstResult, secondResult] = await Promise.all([flushing, joiningFlush])

    expect(firstResult).toMatchObject({ queueRevision: 3, draftRevision: 3 })
    expect(secondResult).toEqual(firstResult)
    expect(maxActiveWrites).toBe(1)
    expect(coordinator.currentDraftRevision.value).toBe(3)
    expect(coordinator.isPending.value).toBe(false)
  })

  it('rejects a current operational failure and retries the retained snapshot', async () => {
    const failure = new Error('offline')
    const transport = vi.fn()
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(response(2, 'retry'))
    const coordinator = createWorkflowDraftCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'workflow-a',
      initialDraftRevision: 1,
      transport,
    })
    coordinator.queue(graph('retry'))

    await expect(coordinator.flushLatest()).rejects.toBe(failure)
    expect(coordinator.syncState.value).toBe('error')
    expect(coordinator.isPending.value).toBe(true)

    await expect(coordinator.flushLatest()).resolves.toMatchObject({
      queueRevision: 1,
      draftRevision: 2,
    })
    expect(transport).toHaveBeenCalledTimes(2)
    expect(transport.mock.calls[1]?.[0]).toMatchObject({
      expectedDraftRevision: 1,
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'retry' } })],
      }),
    })
  })

  it('does not expose a superseded failure while the newer draft is pending', async () => {
    const oldWrite = deferred<WorkflowDraftResponse>()
    const newWrite = deferred<WorkflowDraftResponse>()
    const onOperationalError = vi.fn()
    const transport = vi.fn()
      .mockReturnValueOnce(oldWrite.promise)
      .mockReturnValueOnce(newWrite.promise)
    const coordinator = createWorkflowDraftCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'workflow-a',
      initialDraftRevision: 1,
      transport,
      onOperationalError,
    })

    coordinator.queue(graph('old'))
    const flushing = coordinator.flushLatest()
    await vi.advanceTimersByTimeAsync(0)
    coordinator.queue(graph('new'))

    oldWrite.reject(new Error('superseded failure'))
    await vi.advanceTimersByTimeAsync(0)

    expect(transport).toHaveBeenCalledTimes(2)
    expect(coordinator.syncState.value).toBe('pending')
    expect(coordinator.lastError.value).toBeNull()
    expect(onOperationalError).not.toHaveBeenCalled()

    newWrite.resolve(response(2, 'new'))
    await expect(flushing).resolves.toMatchObject({ queueRevision: 2 })
  })

  it('surfaces same-workflow revision conflicts without dropping queued state', async () => {
    let backendRevision = 1
    const transport = vi.fn(async (request: WorkflowDraftWriteRequest) => {
      if (request.expectedDraftRevision !== backendRevision) {
        throw {
          response: {
            status: 409,
            data: { current_revision: backendRevision },
          },
        }
      }
      backendRevision += 1
      return response(backendRevision, 'accepted')
    })
    const first = createWorkflowDraftCoordinator({
      canvasId: canvasIdFromPanelId('workflow:first'),
      workflowId: 'workflow-a',
      initialDraftRevision: 1,
      transport,
    })
    const second = createWorkflowDraftCoordinator({
      canvasId: canvasIdFromPanelId('workflow:second'),
      workflowId: 'workflow-a',
      initialDraftRevision: 1,
      transport,
    })

    first.queue(graph('first'))
    await first.flushLatest()
    second.queue(graph('second-latest'))

    await expect(second.flushLatest()).rejects.toMatchObject({
      response: { status: 409 },
    })
    expect(second.syncState.value).toBe('conflict')
    expect(second.conflictDraftRevision.value).toBe(2)
    expect(second.isPending.value).toBe(true)
    expect(second.currentGraph.value.nodes[0]?.parameters).toEqual({
      value: 'second-latest',
    })
  })

  it('retains newer edits in conflict without automatically retrying them', async () => {
    const held = deferred<WorkflowDraftResponse>()
    const conflict = {
      response: {
        status: 409,
        data: { current_revision: 7 },
      },
    }
    const transport = vi.fn(() => held.promise)
    const coordinator = createWorkflowDraftCoordinator({
      canvasId: canvasIdFromPanelId('workflow:conflict'),
      workflowId: 'workflow-a',
      initialDraftRevision: 1,
      transport,
    })

    coordinator.queue(graph('inflight'))
    const flushing = coordinator.flushLatest()
    await vi.advanceTimersByTimeAsync(0)
    coordinator.queue(graph('queued-during-write'))
    held.reject(conflict)

    await expect(flushing).rejects.toBe(conflict)
    expect(coordinator.syncState.value).toBe('conflict')
    expect(coordinator.conflictDraftRevision.value).toBe(7)
    expect(coordinator.currentGraph.value.nodes[0]?.parameters).toEqual({
      value: 'queued-during-write',
    })

    await vi.advanceTimersByTimeAsync(500)
    expect(transport).toHaveBeenCalledOnce()
    await expect(coordinator.flushLatest()).rejects.toBe(conflict)
    expect(transport).toHaveBeenCalledOnce()

    coordinator.queue(graph('edited-after-conflict'))
    expect(coordinator.syncState.value).toBe('conflict')
    expect(coordinator.currentGraph.value.nodes[0]?.parameters).toEqual({
      value: 'edited-after-conflict',
    })
    await vi.advanceTimersByTimeAsync(500)
    expect(transport).toHaveBeenCalledOnce()
  })

  it('disposing one canvas rejects its write without affecting another canvas', async () => {
    const held = deferred<WorkflowDraftResponse>()
    const a = createWorkflowDraftCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      workflowId: 'workflow-a',
      initialDraftRevision: 1,
      transport: vi.fn(() => held.promise),
    })
    const b = createWorkflowDraftCoordinator({
      canvasId: canvasIdFromPanelId('workflow:b'),
      workflowId: 'workflow-b',
      initialDraftRevision: 7,
      transport: vi.fn(async () => response(8, 'b', 'workflow-b')),
    })

    a.queue(graph('a'))
    const flushingA = a.flushLatest()
    b.queue(graph('b'))
    a.dispose()

    await expect(flushingA).rejects.toBeInstanceOf(
      WorkflowDraftCoordinatorDisposedError,
    )
    await expect(b.flushLatest()).resolves.toMatchObject({ draftRevision: 8 })
    expect(b.syncState.value).toBe('idle')
  })
})
