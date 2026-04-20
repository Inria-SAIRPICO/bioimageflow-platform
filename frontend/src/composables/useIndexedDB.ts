const DB_NAME = 'bioimageflow'
const STORE_NAME = 'workflows'
const DB_VERSION = 1

export interface WorkflowState {
  nodes: any[]
  edges: any[]
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME)
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export function useIndexedDB() {
  async function saveWorkflow(state: WorkflowState): Promise<void> {
    try {
      const db = await openDB()
      const tx = db.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      store.put(state, 'current')
      await new Promise<void>((resolve, reject) => {
        tx.oncomplete = () => resolve()
        tx.onerror = () => reject(tx.error)
      })
      db.close()
    } catch (err) {
      console.warn('[useIndexedDB] Failed to save workflow:', err)
    }
  }

  async function loadWorkflow(): Promise<WorkflowState | null> {
    try {
      const db = await openDB()
      const tx = db.transaction(STORE_NAME, 'readonly')
      const store = tx.objectStore(STORE_NAME)
      const request = store.get('current')
      const result = await new Promise<WorkflowState | null>((resolve, reject) => {
        request.onsuccess = () => resolve(request.result ?? null)
        request.onerror = () => reject(request.error)
      })
      db.close()
      return result
    } catch (err) {
      console.warn('[useIndexedDB] Failed to load workflow:', err)
      return null
    }
  }

  return { saveWorkflow, loadWorkflow }
}
