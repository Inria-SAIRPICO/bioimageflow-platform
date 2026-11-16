import { beforeEach, describe, expect, it, vi } from 'vitest'
import { IDBFactory } from 'fake-indexeddb'
import { useAutoSave, writeAutoSaveEntry, type AutoSaveEntry } from '@/composables/useAutoSave'
import { makeGraph } from '@/test-utils/graphFixtures'

const id = '804dfb8e-20c0-452d-a317-e2115ca94ce8'
const owner = (workspace_path = '/workspace/A', identity_generation = 0) => ({ workspace_path, identity_generation })
const snapshot = (workspace = '/workspace/A', generation = 0, timestamp = 1): AutoSaveEntry => ({
  name: id, ...owner(workspace, generation), graph: makeGraph({ name: 'queued' }), timestamp,
})

async function seedLegacy(entry: AutoSaveEntry): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const request = indexedDB.open('bioimageflow-autosave', 1)
    request.onupgradeneeded = () => {
      request.result.createObjectStore('workflows', { keyPath: 'name' })
      request.result.createObjectStore('preferences')
    }
    request.onsuccess = () => {
      const db = request.result
      const transaction = db.transaction('workflows', 'readwrite')
      transaction.objectStore('workflows').put(entry)
      transaction.oncomplete = () => { db.close(); resolve() }
      transaction.onerror = () => reject(transaction.error)
    }
    request.onerror = () => reject(request.error)
  })
}

describe('durable recovery ownership', () => {
  beforeEach(() => vi.stubGlobal('indexedDB', new IDBFactory()))

  it('keeps copied-workspace UUIDs and later generations independently recoverable', async () => {
    const api = useAutoSave()
    await writeAutoSaveEntry(snapshot('/workspace/A', 0, 1))
    await writeAutoSaveEntry(snapshot('/workspace/B', 0, 2))
    await writeAutoSaveEntry(snapshot('/workspace/A', 1, 3))
    expect(await api.loadAutoSaves()).toHaveLength(3)
    expect(await api.loadAutoSave(id, owner())).toMatchObject({ timestamp: 1 })
    await api.clearAutoSaveStrict(id, owner('/workspace/B'))
    expect(await api.loadAutoSave(id, owner())).toMatchObject({ timestamp: 1 })
    expect(await api.loadAutoSave(id, owner('/workspace/A', 1))).toMatchObject({ timestamp: 3 })
    expect(await api.loadAutoSave(id, owner('/workspace/B'))).toBeNull()
  })

  it('preserves version-one records without assigning an inferred owner', async () => {
    const legacy = { name: id, graph: makeGraph({ name: 'legacy' }), timestamp: 7 }
    await seedLegacy(legacy)
    await writeAutoSaveEntry(snapshot())
    const api = useAutoSave()
    expect(await api.loadAutoSaves()).toContainEqual(legacy)
    await api.clearAutoSaveStrict(id)
    await api.clearAutoSaveStrict(id, owner())
    expect(await api.loadAutoSaves()).toEqual([legacy])
    expect(await api.loadAutoSave(id)).toBeNull()
    await expect(writeAutoSaveEntry(legacy)).rejects.toThrow('requires a workflow UUID')
    expect(await api.loadAutoSaves()).toEqual([legacy])
  })

  it('refuses to clear a newer snapshot written while recovery acceptance was pending', async () => {
    const api = useAutoSave()
    await writeAutoSaveEntry(snapshot())
    const captured = (await api.loadAutoSave(id, owner()))!
    await writeAutoSaveEntry(snapshot('/workspace/A', 0, 2))
    await expect(api.clearAutoSaveEntryStrict(captured)).rejects.toThrow('newer edits are retained')
    expect(await api.loadAutoSave(id, owner())).toMatchObject({ timestamp: 2 })
    await api.clearAutoSaveEntryStrict((await api.loadAutoSave(id, owner()))!)
    expect(await api.loadAutoSaves()).toEqual([])
  })

  it('clears an explicitly accepted legacy snapshot without deleting its new scoped counterpart', async () => {
    const legacy = { name: id, graph: makeGraph({ name: 'legacy' }), timestamp: 7 }
    await seedLegacy(legacy)
    await writeAutoSaveEntry(snapshot())
    await useAutoSave().clearAutoSaveEntryStrict(legacy)
    expect(await useAutoSave().loadAutoSaves()).toEqual([expect.objectContaining({ workspace_path: '/workspace/A' })])
  })
})
