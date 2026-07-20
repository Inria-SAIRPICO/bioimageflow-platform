import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { GraphState } from '@/api/types'
import { makeGraph, requireToolNode } from '@/test-utils/graphFixtures'
import { canvasIdFromPanelId } from '../canvasSessionRegistry'
import {
  RecoveryPersistenceCoordinatorDisposedError,
  clearRecoveryPersistenceKeyStrict,
  createRecoveryPersistenceCoordinator,
  type RecoveryPersistenceRequest,
} from '../recoveryPersistenceCoordinator'

function graph(value: string): GraphState {
  return makeGraph({
    nodes: [{
      type: 'tool',
      id: 'node',
      name: 'Node',
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

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('recovery persistence coordinator', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('keeps two workflow snapshots queued inside one debounce window', async () => {
    const requests: RecoveryPersistenceRequest[] = []
    const transport = vi.fn(async (request: RecoveryPersistenceRequest) => {
      requests.push(request)
    })
    const coordinator = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      transport,
      now: () => 1234,
    })
    const first = graph('first')

    coordinator.queue('folder/first', first)
    coordinator.queue('folder/second', graph('second'))
    requireToolNode(first).parameters = { value: 'mutated-after-queue' }

    expect(coordinator.isPending.value).toBe(true)
    await vi.advanceTimersByTimeAsync(500)

    expect(requests).toHaveLength(2)
    expect(requests).toEqual(expect.arrayContaining([
      expect.objectContaining({
        canvasId: canvasIdFromPanelId('workflow:a'),
        recoveryKey: 'folder/first',
        timestamp: 1234,
        graph: expect.objectContaining({
          nodes: [expect.objectContaining({ parameters: { value: 'first' } })],
        }),
      }),
      expect.objectContaining({ recoveryKey: 'folder/second' }),
    ]))
    expect(coordinator.isPending.value).toBe(false)
  })

  it('joins an active write and drains an edit made during the flush', async () => {
    const first = deferred<void>()
    const second = deferred<void>()
    const transport = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const coordinator = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:a'),
      transport,
    })

    coordinator.queue('workflow-a', graph('old'))
    const flushing = coordinator.flushLatest()
    await vi.advanceTimersByTimeAsync(0)
    coordinator.queue('workflow-a', graph('new'))
    const joiningFlush = coordinator.flushLatest()
    expect(transport).toHaveBeenCalledTimes(1)

    first.resolve()
    await vi.advanceTimersByTimeAsync(0)
    expect(transport).toHaveBeenCalledTimes(2)
    expect(transport.mock.calls[1]?.[0]).toMatchObject({
      recoveryKey: 'workflow-a',
      graph: expect.objectContaining({
        nodes: [expect.objectContaining({ parameters: { value: 'new' } })],
      }),
    })

    second.resolve()
    await Promise.all([flushing, joiningFlush])
    expect(coordinator.isPending.value).toBe(false)
  })

  it('serializes same-key canvas writes so a slow older write cannot finish last', async () => {
    const olderWrite = deferred<void>()
    const order: string[] = []
    const olderTransport = vi.fn(async () => {
      await olderWrite.promise
      order.push('older')
    })
    const newerTransport = vi.fn(async () => {
      order.push('newer')
    })
    const older = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:older'),
      transport: olderTransport,
    })
    const newer = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:newer'),
      transport: newerTransport,
    })

    older.queue('shared-workflow', graph('older'))
    const flushingOlder = older.flushLatest()
    await vi.advanceTimersByTimeAsync(0)
    newer.queue('shared-workflow', graph('newer'))
    const flushingNewer = newer.flushLatest()
    await vi.advanceTimersByTimeAsync(0)

    expect(olderTransport).toHaveBeenCalledOnce()
    expect(newerTransport).not.toHaveBeenCalled()

    olderWrite.resolve()
    await Promise.all([flushingOlder, flushingNewer])
    expect(order).toEqual(['older', 'newer'])
  })

  it('reports a failed older same-key write as skipped once a newer canvas owns it', async () => {
    const olderWrite = deferred<void>()
    const onOlderError = vi.fn()
    const older = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:older-failure'),
      transport: vi.fn(() => olderWrite.promise),
      onOperationalError: onOlderError,
    })
    const newerTransport = vi.fn(async () => {})
    const newer = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:newer-owner'),
      transport: newerTransport,
    })

    older.queue('shared-workflow', graph('older'))
    const flushingOlder = older.flushLatest()
    await vi.advanceTimersByTimeAsync(0)
    newer.queue('shared-workflow', graph('newer'))
    const flushingNewer = newer.flushLatest()
    olderWrite.reject(new Error('older storage failure'))

    await expect(flushingOlder).resolves.toMatchObject({ persisted: false })
    await expect(flushingNewer).resolves.toMatchObject({ persisted: true })
    expect(newerTransport).toHaveBeenCalledOnce()
    expect(onOlderError).not.toHaveBeenCalled()
    expect(older.lastError.value).toBeNull()
  })

  it('skips an older same-key snapshot flushed after a newer snapshot was accepted', async () => {
    const olderTransport = vi.fn(async () => {})
    const newerTransport = vi.fn(async () => {})
    const older = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:delayed-older'),
      transport: olderTransport,
    })
    const newer = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:accepted-newer'),
      transport: newerTransport,
    })

    older.queue('same-key', graph('older'))
    newer.queue('same-key', graph('newer'))
    await newer.flushLatest()
    const acceptance = await older.flushLatest()

    expect(newerTransport).toHaveBeenCalledOnce()
    expect(olderTransport).not.toHaveBeenCalled()
    expect(acceptance).toMatchObject({ persisted: false })
  })

  it('rejects a failed critical flush and retries the retained snapshot', async () => {
    const failure = new Error('indexeddb unavailable')
    const transport = vi.fn()
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(undefined)
    const coordinator = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:retry'),
      transport,
    })
    coordinator.queue('workflow-retry', graph('retry'))

    await expect(coordinator.flushLatest()).rejects.toBe(failure)
    expect(coordinator.syncState.value).toBe('error')
    expect(coordinator.isPending.value).toBe(true)

    await expect(coordinator.flushLatest()).resolves.toMatchObject({
      recoveryKey: 'workflow-retry',
      persisted: true,
    })
    expect(transport).toHaveBeenCalledTimes(2)
  })

  it('does not expose a superseded failure while the newer recovery is pending', async () => {
    const oldWrite = deferred<void>()
    const newWrite = deferred<void>()
    const onOperationalError = vi.fn()
    const transport = vi.fn()
      .mockReturnValueOnce(oldWrite.promise)
      .mockReturnValueOnce(newWrite.promise)
    const coordinator = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:retry-newer'),
      transport,
      onOperationalError,
    })

    coordinator.queue('workflow-a', graph('old'))
    const flushing = coordinator.flushLatest()
    await vi.advanceTimersByTimeAsync(0)
    coordinator.queue('workflow-a', graph('new'))

    oldWrite.reject(new Error('superseded failure'))
    await vi.advanceTimersByTimeAsync(0)

    expect(transport).toHaveBeenCalledTimes(2)
    expect(coordinator.syncState.value).toBe('pending')
    expect(coordinator.lastError.value).toBeNull()
    expect(onOperationalError).not.toHaveBeenCalled()

    newWrite.resolve()
    await expect(flushing).resolves.toMatchObject({ queueRevision: 2 })
  })

  it('disposing one canvas cancels its queue without affecting another canvas', async () => {
    const transportA = vi.fn(async () => {})
    const transportB = vi.fn(async () => {})
    const a = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:dispose-a'),
      transport: transportA,
    })
    const b = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:dispose-b'),
      transport: transportB,
    })
    a.queue('workflow-a', graph('a'))
    b.queue('workflow-b', graph('b'))

    a.dispose()
    await vi.advanceTimersByTimeAsync(500)

    expect(transportA).not.toHaveBeenCalled()
    expect(transportB).toHaveBeenCalledOnce()
    await expect(a.flushLatest()).rejects.toBeInstanceOf(
      RecoveryPersistenceCoordinatorDisposedError,
    )
  })

  it('disposal releases both inflight and replacement ownership for the same key', async () => {
    const waitingTransport = vi.fn(async () => {})
    const waiting = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:waiting-owner'),
      transport: waitingTransport,
    })
    const disposed = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:disposed-owner'),
      transport: vi.fn(({ signal }) => new Promise<void>((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(new Error('aborted')), {
          once: true,
        })
      })),
    })

    waiting.queue('shared-key', graph('waiting'))
    disposed.queue('shared-key', graph('inflight'))
    const disposedFlush = disposed.flushLatest()
    await vi.advanceTimersByTimeAsync(0)
    disposed.queue('shared-key', graph('replacement'))
    disposed.dispose()

    await expect(disposedFlush).rejects.toBeInstanceOf(
      RecoveryPersistenceCoordinatorDisposedError,
    )
    await expect(waiting.flushLatest()).resolves.toMatchObject({ persisted: true })
    expect(waitingTransport).toHaveBeenCalledOnce()
  })

  it('serializes a strict clear after an in-flight write and fences its queued replacement', async () => {
    const writeGate = deferred<void>()
    const persisted = new Map<string, GraphState>()
    const order: string[] = []
    const transport = vi.fn(async (request: RecoveryPersistenceRequest) => {
      await writeGate.promise
      persisted.set(request.recoveryKey, request.graph)
      order.push('write')
    })
    const coordinator = createRecoveryPersistenceCoordinator({
      canvasId: canvasIdFromPanelId('workflow:remote-delete'),
      transport,
    })

    coordinator.queue('remote-delete', graph('in-flight'))
    const flushing = coordinator.flushLatest()
    const flushingOutcome = flushing.then(
      value => ({ value, error: null }),
      error => ({ value: null, error }),
    )
    await vi.advanceTimersByTimeAsync(0)
    coordinator.queue('remote-delete', graph('queued-after-write'))
    coordinator.dispose()

    const clearing = clearRecoveryPersistenceKeyStrict('remote-delete', async () => {
      persisted.delete('remote-delete')
      order.push('clear')
    })
    await vi.advanceTimersByTimeAsync(0)
    expect(order).toEqual([])

    writeGate.resolve()
    expect((await flushingOutcome).error).toBeInstanceOf(
      RecoveryPersistenceCoordinatorDisposedError,
    )
    await clearing
    await vi.advanceTimersByTimeAsync(500)

    expect(order).toEqual(['write', 'clear'])
    expect(transport).toHaveBeenCalledOnce()
    expect(persisted.has('remote-delete')).toBe(false)
  })
})
