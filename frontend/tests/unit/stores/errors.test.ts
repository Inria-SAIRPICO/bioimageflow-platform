import { setActivePinia, createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useErrorStore } from '@/stores/errors'
import { useLoggerStore } from '@/stores/logger'

describe('useErrorStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts with no errors and unreadCount=0', () => {
    const store = useErrorStore()
    expect(store.errors).toEqual([])
    expect(store.unreadCount).toBe(0)
    expect(store.hasErrors).toBe(false)
  })

  it('report() appends an entry with synthesized id and timestamp', () => {
    const store = useErrorStore()
    const before = Date.now()
    const id = store.report({ kind: 'graph_sync_error', detail: 'Network down' })
    const after = Date.now()

    expect(store.errors).toHaveLength(1)
    const entry = store.errors[0]!
    expect(typeof entry.id).toBe('string')
    expect(entry.id.length).toBeGreaterThan(0)
    expect(entry.kind).toBe('graph_sync_error')
    expect(entry.detail).toBe('Network down')
    expect(entry.timestamp).toBeGreaterThanOrEqual(before)
    expect(entry.timestamp).toBeLessThanOrEqual(after)
    expect(entry.dismissed).toBeFalsy()
    expect(id).toBe(entry.id)
  })

  it('report() preserves all optional fields', () => {
    const store = useErrorStore()
    store.report({
      kind: 'graph_sync_error',
      detail: 'failed',
      field: 'graph',
      status: 500,
      nodeId: 'n1',
    })
    const entry = store.errors[0]!
    expect(entry.field).toBe('graph')
    expect(entry.status).toBe(500)
    expect(entry.nodeId).toBe('n1')
  })

  it('report() mirrors the full error detail to the logger', () => {
    const store = useErrorStore()
    const logger = useLoggerStore()

    store.report({
      kind: 'execution_failed',
      detail: 'node failed',
      fullDetail: 'node failed\nTraceback line 1\nTraceback line 2',
      nodeId: 'n1',
      status: 500,
      field: 'image',
    })

    expect(logger.entries).toHaveLength(1)
    expect(logger.entries[0]).toMatchObject({
      level: 'ERROR',
      message: 'node failed\nTraceback line 1\nTraceback line 2',
      nodeId: 'n1',
    })
  })

  it('report() with the same kind twice produces two entries', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'first' })
    store.report({ kind: 'graph_sync_error', detail: 'second' })
    expect(store.errors).toHaveLength(2)
    expect(store.errors[0]!.detail).toBe('first')
    expect(store.errors[1]!.detail).toBe('second')
  })

  it('hasErrors and unreadCount reflect entries', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'a' })
    store.report({ kind: 'websocket_error', detail: 'b' })
    expect(store.unreadCount).toBe(2)
    expect(store.hasErrors).toBe(true)
  })

  it('dismiss(id) sets dismissed=true and removes from unreadCount', () => {
    const store = useErrorStore()
    const id = store.report({ kind: 'graph_sync_error', detail: 'oops' })
    store.report({ kind: 'graph_sync_error', detail: 'still here' })
    store.dismiss(id)
    expect(store.errors).toHaveLength(2)
    expect(store.errors[0]!.dismissed).toBe(true)
    expect(store.unreadCount).toBe(1)
  })

  it('dismiss with unknown id is a no-op', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'x' })
    expect(() => store.dismiss('unknown-id')).not.toThrow()
    expect(store.errors).toHaveLength(1)
    expect(store.errors[0]!.dismissed).toBeFalsy()
  })

  it('dismissAll marks every entry dismissed', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: '1' })
    store.report({ kind: 'graph_sync_error', detail: '2' })
    store.report({ kind: 'graph_sync_error', detail: '3' })
    store.dismissAll()
    expect(store.errors.every((e) => e.dismissed)).toBe(true)
    expect(store.unreadCount).toBe(0)
    expect(store.hasErrors).toBe(false)
  })

  it('clear() empties the array entirely', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'a' })
    store.report({ kind: 'graph_sync_error', detail: 'b' })
    store.clear()
    expect(store.errors).toEqual([])
    expect(store.unreadCount).toBe(0)
  })

  it('autoDismissMs schedules auto-dismissal after the given delay', () => {
    vi.useFakeTimers()
    const store = useErrorStore()
    const id = store.report({
      kind: 'websocket_error',
      detail: 'reconnecting',
      autoDismissMs: 3000,
    })
    expect(store.errors[0]!.dismissed).toBeFalsy()

    vi.advanceTimersByTime(2999)
    expect(store.errors[0]!.dismissed).toBeFalsy()

    vi.advanceTimersByTime(1)
    expect(store.errors[0]!.dismissed).toBe(true)
    expect(id).toBe(store.errors[0]!.id)
  })

  it('manual dismiss before timer fires does not throw later', () => {
    vi.useFakeTimers()
    const store = useErrorStore()
    const id = store.report({
      kind: 'websocket_error',
      detail: 'reconnecting',
      autoDismissMs: 3000,
    })
    store.dismiss(id)
    expect(() => vi.advanceTimersByTime(5000)).not.toThrow()
    expect(store.errors[0]!.dismissed).toBe(true)
  })

  it('clear() while autoDismiss timer is pending does not throw when timer fires', () => {
    vi.useFakeTimers()
    const store = useErrorStore()
    store.report({
      kind: 'websocket_error',
      detail: 'reconnecting',
      autoDismissMs: 3000,
    })
    store.clear()
    expect(() => vi.advanceTimersByTime(5000)).not.toThrow()
    expect(store.errors).toEqual([])
  })

  it('id values are unique across many reports', () => {
    const store = useErrorStore()
    for (let i = 0; i < 100; i += 1) {
      store.report({ kind: 'graph_sync_error', detail: String(i) })
    }
    const ids = new Set(store.errors.map((e) => e.id))
    expect(ids.size).toBe(100)
  })

  it('errors are appended in chronological (call) order', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'first' })
    store.report({ kind: 'graph_sync_error', detail: 'second' })
    store.report({ kind: 'graph_sync_error', detail: 'third' })
    expect(store.errors.map((e) => e.detail)).toEqual([
      'first',
      'second',
      'third',
    ])
  })

  it('legacy {kind, detail}-only call shape still works', () => {
    const store = useErrorStore()
    expect(() =>
      store.report({ kind: 'websocket_error', detail: 'closed' }),
    ).not.toThrow()
    expect(store.errors).toHaveLength(1)
  })

  it('passing kind="unknown" stores it and is renderable', () => {
    const store = useErrorStore()
    store.report({ kind: 'unknown', detail: 'mystery' })
    expect(store.errors[0]!.kind).toBe('unknown')
  })
})
