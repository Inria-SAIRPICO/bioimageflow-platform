import type { GraphState } from '@/api/types'

const DB_NAME = 'bioimageflow-autosave'
const DB_VERSION = 1
const WORKFLOW_STORE = 'workflows'
const PREFERENCES_STORE = 'preferences'
const LAST_OPENED_KEY = 'last_opened_workflow'
const DEBOUNCE_MS = 500

export interface AutoSaveEntry {
  name: string
  graph: GraphState
  timestamp: number
}

let timer: ReturnType<typeof setTimeout> | null = null
let pendingEntry: AutoSaveEntry | null = null

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(WORKFLOW_STORE)) {
        db.createObjectStore(WORKFLOW_STORE, { keyPath: 'name' })
      }
      if (!db.objectStoreNames.contains(PREFERENCES_STORE)) {
        db.createObjectStore(PREFERENCES_STORE)
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

function waitForTransaction(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error)
  })
}

async function withStore<T>(
  storeName: string,
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => Promise<T> | T,
): Promise<T> {
  const db = await openDB()
  try {
    const tx = db.transaction(storeName, mode)
    const store = tx.objectStore(storeName)
    const result = await fn(store)
    await waitForTransaction(tx)
    return result
  } finally {
    db.close()
  }
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

async function putAutoSave(entry: AutoSaveEntry): Promise<void> {
  await withStore(WORKFLOW_STORE, 'readwrite', (store) => {
    store.put(JSON.parse(JSON.stringify(entry)))
  })
}

export function useAutoSave() {
  function scheduleAutoSave(name: string, graph: GraphState): void {
    pendingEntry = {
      name,
      graph,
      timestamp: Date.now(),
    }
    if (timer !== null) {
      clearTimeout(timer)
    }
    timer = setTimeout(() => {
      void flushAutoSave()
    }, DEBOUNCE_MS)
  }

  async function flushAutoSave(): Promise<void> {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    if (pendingEntry === null) return
    const entry = pendingEntry
    pendingEntry = null
    try {
      await putAutoSave(entry)
    } catch (err) {
      console.warn('[useAutoSave] Failed to save workflow:', err)
    }
  }

  async function loadAutoSave(name: string): Promise<AutoSaveEntry | null> {
    try {
      return await withStore(WORKFLOW_STORE, 'readonly', (store) => (
        requestResult<AutoSaveEntry | undefined>(store.get(name))
      )).then((entry) => entry ?? null)
    } catch (err) {
      console.warn('[useAutoSave] Failed to load workflow auto-save:', err)
      return null
    }
  }

  async function loadMostRecentAutoSave(): Promise<AutoSaveEntry | null> {
    try {
      const entries = await withStore(WORKFLOW_STORE, 'readonly', (store) => (
        requestResult<AutoSaveEntry[]>(store.getAll())
      ))
      return entries.sort((a, b) => b.timestamp - a.timestamp)[0] ?? null
    } catch (err) {
      console.warn('[useAutoSave] Failed to load workflow auto-saves:', err)
      return null
    }
  }

  async function clearAutoSave(name: string): Promise<void> {
    try {
      await withStore(WORKFLOW_STORE, 'readwrite', (store) => {
        store.delete(name)
      })
    } catch (err) {
      console.warn('[useAutoSave] Failed to clear workflow auto-save:', err)
    }
  }

  async function renameWorkflow(oldName: string, newName: string): Promise<void> {
    if (oldName === newName) return
    if (pendingEntry?.name === oldName) {
      pendingEntry = { ...pendingEntry, name: newName }
    }
    await flushAutoSave()
    const entry = await loadAutoSave(oldName)
    let moved = entry === null
    if (entry !== null) {
      try {
        await putAutoSave({ ...entry, name: newName })
        moved = true
      } catch (err) {
        console.warn('[useAutoSave] Failed to move workflow auto-save:', err)
      }
    }
    if (moved) {
      await clearAutoSave(oldName)
    }
    if (await getLastOpenedWorkflow() === oldName) {
      await setLastOpenedWorkflow(newName)
    }
  }

  async function setLastOpenedWorkflow(name: string | null): Promise<void> {
    try {
      await withStore(PREFERENCES_STORE, 'readwrite', (store) => {
        if (name === null) {
          store.delete(LAST_OPENED_KEY)
        } else {
          store.put(name, LAST_OPENED_KEY)
        }
      })
    } catch (err) {
      console.warn('[useAutoSave] Failed to store last-opened workflow:', err)
    }
  }

  async function getLastOpenedWorkflow(): Promise<string | null> {
    try {
      return await withStore(PREFERENCES_STORE, 'readonly', (store) => (
        requestResult<string | undefined>(store.get(LAST_OPENED_KEY))
      )).then((name) => name ?? null)
    } catch (err) {
      console.warn('[useAutoSave] Failed to load last-opened workflow:', err)
      return null
    }
  }

  return {
    scheduleAutoSave,
    flushAutoSave,
    loadAutoSave,
    loadMostRecentAutoSave,
    clearAutoSave,
    renameWorkflow,
    setLastOpenedWorkflow,
    getLastOpenedWorkflow,
  }
}
