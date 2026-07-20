import { setActivePinia, createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const toastAdd = vi.fn()
vi.mock('primevue/usetoast', () => ({
  useToast: () => ({ add: toastAdd, removeAllGroups: vi.fn() }),
}))

vi.mock('vue', async importOriginal => {
  const original = await importOriginal<typeof import('vue')>()
  return { ...original, hasInjectionContext: () => true }
})

import { useErrorReporting, __resetErrorReportingForTests } from '@/composables/useErrorReporting'
import { useErrorStore } from '@/stores/errors'

describe('useErrorReporting', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    toastAdd.mockReset()
    __resetErrorReportingForTests()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('graph_sync_error: forwards to errorStore.report', () => {
    const store = useErrorStore()
    const { reportError } = useErrorReporting()
    const id = reportError({ kind: 'graph_sync_error', detail: 'down' })
    expect(store.errors).toHaveLength(1)
    expect(store.errors[0]!.kind).toBe('graph_sync_error')
    expect(id).toBe(store.errors[0]!.id)
  })

  it('graph_sync_error: shows a warn toast only on the first occurrence per session', () => {
    const { reportError } = useErrorReporting()
    reportError({ kind: 'graph_sync_error', detail: 'first' })
    reportError({ kind: 'graph_sync_error', detail: 'second' })
    expect(toastAdd).toHaveBeenCalledTimes(1)
    expect(toastAdd.mock.calls[0]![0]).toMatchObject({ severity: 'warn' })
  })

  it('graph_sync_error: command feedback does not consume background deduplication', () => {
    const { reportError } = useErrorReporting()
    reportError({ kind: 'graph_sync_error', detail: 'command 1', alwaysToast: true })
    reportError({ kind: 'graph_sync_error', detail: 'background' })
    reportError({ kind: 'graph_sync_error', detail: 'command 2', alwaysToast: true })
    expect(toastAdd).toHaveBeenCalledTimes(3)
  })

  it('websocket_error: does not show a toast but records history', () => {
    const store = useErrorStore()
    const { reportError } = useErrorReporting()
    reportError({ kind: 'websocket_error', detail: 'closed' })
    expect(toastAdd).not.toHaveBeenCalled()
    expect(store.errors).toHaveLength(1)
  })

  it('log_subscription_failed: shows a single toast per session', () => {
    const { reportError } = useErrorReporting()
    reportError({ kind: 'log_subscription_failed', detail: 'a' })
    reportError({ kind: 'log_subscription_failed', detail: 'b' })
    expect(toastAdd).toHaveBeenCalledTimes(1)
    expect(toastAdd.mock.calls[0]![0]).toMatchObject({ severity: 'warn' })
  })

  it('execution_failed: shows an error toast every time', () => {
    const { reportError } = useErrorReporting()
    reportError({ kind: 'execution_failed', detail: '1', nodeId: 'a' })
    reportError({ kind: 'execution_failed', detail: '2', nodeId: 'b' })
    expect(toastAdd).toHaveBeenCalledTimes(2)
    expect(toastAdd.mock.calls[0]![0]).toMatchObject({ severity: 'error' })
  })

  it('network_unreachable: history only, no toast', () => {
    const store = useErrorStore()
    const { reportError } = useErrorReporting()
    reportError({ kind: 'network_unreachable', detail: 'no route' })
    expect(toastAdd).not.toHaveBeenCalled()
    expect(store.errors).toHaveLength(1)
  })

  it('edge_rejected: shows a warn toast and is NOT recorded in history', () => {
    const store = useErrorStore()
    const { reportError } = useErrorReporting()
    const id = reportError({ kind: 'edge_rejected', detail: 'incompatible' })
    expect(toastAdd).toHaveBeenCalledTimes(1)
    expect(toastAdd.mock.calls[0]![0]).toMatchObject({ severity: 'warn' })
    expect(store.errors).toHaveLength(0)
    expect(id).toBeUndefined()
  })

  it('dataset_upload_rejected: shows an error toast and records history', () => {
    const store = useErrorStore()
    const { reportError } = useErrorReporting()
    reportError({ kind: 'dataset_upload_rejected', detail: 'Folders are unsupported' })
    expect(toastAdd).toHaveBeenCalledOnce()
    expect(toastAdd.mock.calls[0]![0]).toMatchObject({
      severity: 'error',
      summary: 'Dataset upload rejected',
    })
    expect(store.errors).toHaveLength(1)
  })

  it('a toast provider failure does not crash reportError', () => {
    toastAdd.mockImplementationOnce(() => {
      throw new Error('no provider')
    })
    const store = useErrorStore()
    const { reportError } = useErrorReporting()
    expect(() =>
      reportError({ kind: 'graph_sync_error', detail: 'first' }),
    ).not.toThrow()
    // History entry was still recorded even if toast emission failed.
    expect(store.errors).toHaveLength(1)
  })

  it('__resetErrorReportingForTests clears toasted-kinds dedup set', () => {
    const { reportError } = useErrorReporting()
    reportError({ kind: 'graph_sync_error', detail: 'first' })
    expect(toastAdd).toHaveBeenCalledTimes(1)
    __resetErrorReportingForTests()
    reportError({ kind: 'graph_sync_error', detail: 'after-reset' })
    expect(toastAdd).toHaveBeenCalledTimes(2)
  })

  it('reportError forwards optional fields onto the entry', () => {
    const store = useErrorStore()
    const { reportError } = useErrorReporting()
    reportError({
      kind: 'execution_failed',
      detail: 'fail',
      nodeId: 'n1',
      status: 500,
      field: 'parameters',
    })
    const entry = store.errors[0]!
    expect(entry.nodeId).toBe('n1')
    expect(entry.status).toBe(500)
    expect(entry.field).toBe('parameters')
  })

  it('unknown kind falls back to history-only info', () => {
    const store = useErrorStore()
    const { reportError } = useErrorReporting()
    reportError({ kind: 'unknown', detail: 'mystery' })
    expect(store.errors).toHaveLength(1)
    expect(toastAdd).not.toHaveBeenCalled()
  })
})
