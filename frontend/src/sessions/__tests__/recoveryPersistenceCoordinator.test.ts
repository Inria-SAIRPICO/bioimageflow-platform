import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { GraphState } from '@/api/types'
import { canvasIdFromPanelId } from '../canvasSessionRegistry'
import {
  RecoveryPersistenceCoordinatorDisposedError,
  createRecoveryPersistenceCoordinator,
  type RecoveryPersistenceRequest,
} from '../recoveryPersistenceCoordinator'

function graph(value: string): GraphState {
  return {
    nodes: [{
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
  }
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
    first.nodes[0]!.parameters = { value: 'mutated-after-queue' }

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
})
