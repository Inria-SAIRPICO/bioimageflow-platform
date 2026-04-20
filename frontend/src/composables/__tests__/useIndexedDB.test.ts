import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useIndexedDB } from '../useIndexedDB'
import type { WorkflowState } from '../useIndexedDB'

/**
 * Minimal fake-indexeddb implementation for jsdom.
 * Only supports the subset of the API that useIndexedDB uses.
 */
function createFakeIndexedDB() {
  const stores: Record<string, Map<string, any>> = {}

  function fakeOpen(_name: string, _version?: number) {
    const request: any = {}
    const db: any = {
      objectStoreNames: {
        contains: (name: string) => name in stores,
      },
      createObjectStore: (name: string) => {
        stores[name] = new Map()
      },
      transaction: (storeName: string, _mode?: string) => {
        const tx: any = {}
        tx.objectStore = (_name: string) => ({
          put: (value: any, key: string) => {
            stores[storeName].set(key, structuredClone(value))
          },
          get: (key: string) => {
            const getReq: any = {}
            getReq.result = stores[storeName].has(key)
              ? structuredClone(stores[storeName].get(key))
              : undefined
            // onsuccess is called synchronously via microtask
            Promise.resolve().then(() => getReq.onsuccess?.())
            return getReq
          },
        })
        // oncomplete fires on next microtask
        Promise.resolve().then(() => tx.oncomplete?.())
        return tx
      },
      close: vi.fn(),
    }

    // Fire onupgradeneeded then onsuccess
    Promise.resolve().then(() => {
      request.result = db
      request.onupgradeneeded?.()
      request.onsuccess?.()
    })

    return request
  }

  return { open: fakeOpen, stores }
}

describe('useIndexedDB', () => {
  let fakeIDB: ReturnType<typeof createFakeIndexedDB>

  beforeEach(() => {
    fakeIDB = createFakeIndexedDB()
    vi.stubGlobal('indexedDB', { open: fakeIDB.open })
  })

  it('saveWorkflow stores data and loadWorkflow retrieves it', async () => {
    const { saveWorkflow, loadWorkflow } = useIndexedDB()

    const state: WorkflowState = {
      nodes: [{ id: 'n1', position: { x: 10, y: 20 }, data: { name: 'test' } }],
      edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
    }

    await saveWorkflow(state)
    const loaded = await loadWorkflow()

    expect(loaded).toEqual(state)
  })

  it('loadWorkflow returns null when nothing is saved', async () => {
    const { loadWorkflow } = useIndexedDB()
    const loaded = await loadWorkflow()
    expect(loaded).toBeNull()
  })

  it('saveWorkflow overwrites previous data', async () => {
    const { saveWorkflow, loadWorkflow } = useIndexedDB()

    await saveWorkflow({ nodes: [{ id: 'a' }], edges: [] })
    await saveWorkflow({ nodes: [{ id: 'b' }], edges: [] })

    const loaded = await loadWorkflow()
    expect(loaded!.nodes).toEqual([{ id: 'b' }])
  })

  it('handles IndexedDB errors gracefully on save', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    // Stub indexedDB.open to fail
    vi.stubGlobal('indexedDB', {
      open: () => {
        const req: any = {}
        Promise.resolve().then(() => {
          req.error = new Error('DB error')
          req.onerror?.()
        })
        return req
      },
    })

    const { saveWorkflow } = useIndexedDB()
    // Should not throw
    await saveWorkflow({ nodes: [], edges: [] })

    expect(warnSpy).toHaveBeenCalledWith(
      '[useIndexedDB] Failed to save workflow:',
      expect.any(Error),
    )
    warnSpy.mockRestore()
  })

  it('handles IndexedDB errors gracefully on load', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    vi.stubGlobal('indexedDB', {
      open: () => {
        const req: any = {}
        Promise.resolve().then(() => {
          req.error = new Error('DB error')
          req.onerror?.()
        })
        return req
      },
    })

    const { loadWorkflow } = useIndexedDB()
    const result = await loadWorkflow()

    expect(result).toBeNull()
    expect(warnSpy).toHaveBeenCalledWith(
      '[useIndexedDB] Failed to load workflow:',
      expect.any(Error),
    )
    warnSpy.mockRestore()
  })
})
