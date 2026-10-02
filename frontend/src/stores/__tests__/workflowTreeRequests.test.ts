import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import type { WorkflowInfo } from '@/api/types'
import { makeGraph } from '@/test-utils/graphFixtures'
import { canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'

const autoSave = vi.hoisted(() => ({
  clearAutoSave: vi.fn().mockResolvedValue(undefined),
  clearAutoSaveStrict: vi.fn().mockResolvedValue(undefined),
  setLastOpenedWorkflow: vi.fn().mockResolvedValue(undefined),
  loadMostRecentAutoSave: vi.fn().mockResolvedValue(null),
  getLastOpenedWorkflow: vi.fn().mockResolvedValue(null),
}))
vi.mock('@/api/client', () => ({ api: {
  get: vi.fn(), put: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(),
} }))
vi.mock('@/composables/useAutoSave', () => ({ useAutoSave: () => autoSave }))
vi.mock('@/api/workflowFormats', () => ({
  getWorkflowFormatStatus: vi.fn().mockResolvedValue({ notices: [], pending_plan_id: null }),
  applyWorkflowFormatMigrations: vi.fn(),
}))

import { api } from '@/api/client'
import { useWorkflowStore } from '../workflow'
import { resolveStartupWorkflow } from '@/services/startupWorkflow'
import WorkflowsPanel from '@/components/panels/WorkflowsPanel.vue'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function info(displayName = 'Before'): WorkflowInfo {
  return { id: 'analysis', name: 'analysis', folder: '', display_name: displayName,
    path: '/workspace/workflows/analysis/workflow.json',
    results_path: '/workspace/workflows/analysis/results',
    last_modified: displayName, identity_generation: 0 }
}
function tree(workflows: WorkflowInfo[] = []) {
  return { data: { path: '', display_name: 'Workflows', folders: [], workflows } }
}

describe('workflow tree pending request ownership', () => {
  beforeEach(() => {
    canvasSessionRegistry.dispose()
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.put).mockReset()
    vi.clearAllMocks()
  })

  it('shares the actual startup resolver and mounted panel request only while pending', async () => {
    const response = deferred<ReturnType<typeof tree>>()
    vi.mocked(api.get).mockReturnValue(response.promise)
    const pinia = createPinia()
    setActivePinia(pinia)
    const panel = mount(WorkflowsPanel, { global: {
      plugins: [pinia, PrimeVue], stubs: { Button: true, Dialog: true },
    } })
    const startup = resolveStartupWorkflow()
    try {
      expect(api.get).toHaveBeenCalledTimes(1)
      expect(api.get).toHaveBeenCalledWith('/api/v1/workflows/tree')
      expect(useWorkflowStore().isLoading).toBe(true)
      response.resolve(tree())
      expect(await startup).toBeNull()
      await flushPromises()
      expect(useWorkflowStore().isLoading).toBe(false)
      await useWorkflowStore().fetchWorkflowTree()
      expect(api.get).toHaveBeenCalledTimes(2)
    } finally {
      response.resolve(tree())
      await startup
      panel.unmount()
    }
  })

  it('shares a rejection with both consumers and allows a later uncached retry', async () => {
    const response = deferred<ReturnType<typeof tree>>()
    vi.mocked(api.get).mockReturnValueOnce(response.promise).mockReturnValue(response.promise)
    const store = useWorkflowStore()
    const outcomes = Promise.allSettled([store.fetchWorkflowTree(), store.fetchWorkflowTree()])
    const error = new Error('tree unavailable')
    try {
      expect(api.get).toHaveBeenCalledTimes(1)
      response.reject(error)
      expect(await outcomes).toEqual([
        { status: 'rejected', reason: error }, { status: 'rejected', reason: error },
      ])
      expect(store.error).toBe(error.message)
      expect(store.isLoading).toBe(false)
      vi.mocked(api.get).mockResolvedValueOnce(tree([info('After retry')]))
      await store.fetchWorkflowTree()
      expect(api.get).toHaveBeenCalledTimes(2)
      expect(store.workflows[0]?.display_name).toBe('After retry')
      expect(store.error).toBeNull()
    } finally {
      response.reject(error)
      await outcomes
    }
  })

  it('does not join or publish a pre-save tree after accepted same-ID metadata changes', async () => {
    const old = deferred<ReturnType<typeof tree>>()
    const fresh = deferred<ReturnType<typeof tree>>()
    vi.mocked(api.get).mockReturnValueOnce(old.promise).mockReturnValue(fresh.promise)
    vi.mocked(api.put).mockResolvedValueOnce({ data: info('Saved label') })
    const store = useWorkflowStore()
    store.workflows = [info()]
    store.current = info()
    const oldRead = store.fetchWorkflowTree()
    const pending: Promise<unknown>[] = [oldRead]
    try {
      await store.saveWorkflow(makeGraph())
      pending.push(store.fetchWorkflowTree({ fresh: true }))
      old.resolve(tree([info('Old label')]))
      await flushPromises()
      expect(store.workflows[0]?.display_name).toBe('Saved label')
      pending.push(store.fetchWorkflowTree())
      expect(api.get).toHaveBeenCalledTimes(2)
      expect(store.isLoading).toBe(true)
      fresh.resolve(tree([info('Saved label')]))
      await Promise.all(pending)
      expect(store.workflows[0]?.display_name).toBe('Saved label')
    } finally {
      old.resolve(tree())
      fresh.resolve(tree([info('Saved label')]))
      await Promise.allSettled(pending)
    }
  })

  it('does not let an old rejection or finalizer erase the new flight and its loading owner', async () => {
    const old = deferred<ReturnType<typeof tree>>()
    const fresh = deferred<ReturnType<typeof tree>>()
    vi.mocked(api.get).mockReturnValueOnce(old.promise).mockReturnValue(fresh.promise)
    const store = useWorkflowStore()
    const original = new Error('superseded request failed')
    const oldRead = store.fetchWorkflowTree().catch(error => error)
    const newRead = store.fetchWorkflowTree({ fresh: true })
    const pending: Promise<unknown>[] = [oldRead, newRead]
    try {
      old.reject(original)
      expect(await oldRead).toBe(original)
      expect(store.error).toBeNull()
      expect(store.isLoading).toBe(true)
      pending.push(store.fetchWorkflowTree())
      expect(api.get).toHaveBeenCalledTimes(2)
      fresh.resolve(tree([info('Current')]))
      await Promise.all(pending)
      expect(store.error).toBeNull()
      expect(store.isLoading).toBe(false)
    } finally {
      old.reject(original)
      fresh.resolve(tree())
      await Promise.allSettled(pending)
    }
  })

  it.each(['tree', 'flat'] as const)(
    'keeps an older %s request from reverting a newer distinct catalog response',
    async (olderEndpoint) => {
      const old = deferred<{ data: unknown }>()
      const olderIsTree = olderEndpoint === 'tree'
      const accepted = [info('Accepted catalog')]
      vi.mocked(api.get).mockReturnValueOnce(old.promise)
        .mockResolvedValueOnce(olderIsTree ? { data: accepted } : tree(accepted))
        .mockResolvedValueOnce(olderIsTree ? tree(accepted) : { data: accepted })
      const store = useWorkflowStore()
      const oldRead = olderIsTree ? store.fetchWorkflowTree() : store.fetchWorkflows()
      try {
        if (olderIsTree) expect(await store.fetchWorkflows()).toEqual(accepted)
        else await store.fetchWorkflowTree()
        expect(store.isLoading).toBe(true)
        old.resolve(olderIsTree ? tree([info('Old catalog')]) : { data: [info('Old catalog')] })
        await oldRead
        expect(store.workflows[0]?.display_name).toBe('Accepted catalog')
        const first = olderIsTree ? '/api/v1/workflows/tree' : '/api/v1/workflows'
        const newer = olderIsTree ? '/api/v1/workflows' : '/api/v1/workflows/tree'
        expect(vi.mocked(api.get).mock.calls.map(call => call[0])).toEqual([first, newer, first])
        expect(store.isLoading).toBe(false)
      } finally {
        old.resolve(olderIsTree ? tree() : { data: [] })
        await oldRead
      }
    },
  )

  it('keeps each joined callers stale retry bounded and never awaits its own flight', async () => {
    const first = deferred<ReturnType<typeof tree>>()
    const second = deferred<ReturnType<typeof tree>>()
    vi.mocked(api.get).mockReturnValueOnce(first.promise).mockReturnValue(second.promise)
    const store = useWorkflowStore()
    const outcomes = Promise.allSettled([store.fetchWorkflowTree(), store.fetchWorkflowTree()])
    try {
      expect(api.get).toHaveBeenCalledTimes(1)
      store.noteWorkflowStructuralEvent()
      first.resolve(tree([info('Stale first')]))
      await flushPromises()
      expect(api.get).toHaveBeenCalledTimes(2)
      store.noteWorkflowStructuralEvent()
      second.resolve(tree([info('Stale second')]))
      const results = await outcomes
      expect(results.every(result => result.status === 'rejected')).toBe(true)
      expect(api.get).toHaveBeenCalledTimes(2)
      expect(store.workflows).toEqual([])
      expect(store.isLoading).toBe(false)
    } finally {
      first.resolve(tree())
      second.resolve(tree())
      await outcomes
    }
  })
})
