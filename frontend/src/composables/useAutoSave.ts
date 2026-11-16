import type { GraphState } from '@/api/types'
import { recoveryOwnerKey, type AutoSaveOwner } from '@/sessions/recoveryIdentity'
export { recoveryEntryId, recoveryOwnerKey, type AutoSaveOwner } from '@/sessions/recoveryIdentity'

const DB_NAME = 'bioimageflow-autosave'
const DB_VERSION = 2
const WORKFLOW_STORE = 'workflows'
const OWNED_WORKFLOW_STORE = 'owned-workflows'
const PREFERENCES_STORE = 'preferences'
const LAST_OPENED_KEY = 'last_opened_workflow'

export interface AutoSaveEntry {
  name: string
  graph: GraphState
  timestamp: number
  workspace_path?: string
  identity_generation?: number
  /** Opaque storage identity; absent on retained version-one recovery records. */
  recovery_key?: string
}

function ownedEntryKey(entry: AutoSaveEntry): string | null {
  if (!entry.workspace_path || !Number.isInteger(entry.identity_generation)
    || entry.identity_generation! < 0
    || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(entry.name)) return null
  return recoveryOwnerKey(entry.name, entry as AutoSaveEntry & AutoSaveOwner)
}

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
      if (!db.objectStoreNames.contains(OWNED_WORKFLOW_STORE)) {
        db.createObjectStore(OWNED_WORKFLOW_STORE, { keyPath: 'recovery_key' })
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

export async function writeAutoSaveEntry(entry: AutoSaveEntry): Promise<void> {
  const recoveryKey = ownedEntryKey(entry)
  if (recoveryKey === null) throw new Error('Browser recovery requires a workflow UUID, workspace and identity generation.')
  await withStore(OWNED_WORKFLOW_STORE, 'readwrite', (store) => {
    store.put(JSON.parse(JSON.stringify({ ...entry, recovery_key: recoveryKey })))
  })
}

async function deleteAutoSaveEntry(name: string, owner?: AutoSaveOwner): Promise<void> {
  // A name alone is never authority to erase another workspace or legacy owner.
  if (!owner) return
  await withStore(OWNED_WORKFLOW_STORE, 'readwrite', (store) => {
    store.delete(recoveryOwnerKey(name, owner))
  })
}

export function useAutoSave() {
  async function loadAutoSaves(): Promise<AutoSaveEntry[]> {
    const [legacy, owned] = await Promise.all([
      withStore(WORKFLOW_STORE, 'readonly', store => requestResult<AutoSaveEntry[]>(store.getAll())),
      withStore(OWNED_WORKFLOW_STORE, 'readonly', store => requestResult<AutoSaveEntry[]>(store.getAll())),
    ])
    return [...legacy, ...owned]
  }
  async function loadAutoSave(name: string, owner?: AutoSaveOwner): Promise<AutoSaveEntry | null> {
    if (!owner) return null
    try {
      return await withStore(OWNED_WORKFLOW_STORE, 'readonly', (store) => (
        requestResult<AutoSaveEntry | undefined>(store.get(recoveryOwnerKey(name, owner)))
      )).then((entry) => entry ?? null)
    } catch (err) {
      console.warn('[useAutoSave] Failed to load workflow auto-save:', err)
      return null
    }
  }

  async function loadMostRecentAutoSave(): Promise<AutoSaveEntry | null> {
    try {
      const entries = await loadAutoSaves()
      return entries.sort((a, b) => b.timestamp - a.timestamp)[0] ?? null
    } catch (err) {
      console.warn('[useAutoSave] Failed to load workflow auto-saves:', err)
      return null
    }
  }

  async function clearAutoSave(name: string, owner?: AutoSaveOwner): Promise<void> {
    try {
      await deleteAutoSaveEntry(name, owner)
    } catch (err) {
      console.warn('[useAutoSave] Failed to clear workflow auto-save:', err)
    }
  }

  async function clearAutoSaveStrict(name: string, owner?: AutoSaveOwner): Promise<void> {
    await deleteAutoSaveEntry(name, owner)
  }

  async function clearAutoSaveEntryStrict(entry: AutoSaveEntry): Promise<void> {
    const storeName = entry.recovery_key ? OWNED_WORKFLOW_STORE : WORKFLOW_STORE
    const key = entry.recovery_key ?? entry.name
    await withStore(storeName, 'readwrite', async (store) => {
      const current = await requestResult<AutoSaveEntry | undefined>(store.get(key))
      if (current === undefined) return
      if (JSON.stringify(current) !== JSON.stringify(entry)) {
        throw new Error('The browser recovery changed while it was being restored. Its newer edits are retained.')
      }
      store.delete(key)
    })
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
    loadAutoSaves,
    loadAutoSave,
    loadMostRecentAutoSave,
    clearAutoSave,
    clearAutoSaveStrict,
    clearAutoSaveEntryStrict,
    setLastOpenedWorkflow,
    getLastOpenedWorkflow,
  }
}
