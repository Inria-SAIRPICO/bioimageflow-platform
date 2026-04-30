import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const autoSaveMocks = vi.hoisted(() => ({
  clearAutoSave: vi.fn().mockResolvedValue(undefined),
  setLastOpenedWorkflow: vi.fn().mockResolvedValue(undefined),
  renameWorkflow: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/composables/useAutoSave', () => ({
  useAutoSave: () => autoSaveMocks,
}))

import { api } from '@/api/client'
import { useWorkflowStore } from '../workflow'

describe('workflow store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.patch).mockReset()
    autoSaveMocks.clearAutoSave.mockClear()
    autoSaveMocks.setLastOpenedWorkflow.mockClear()
    autoSaveMocks.renameWorkflow.mockClear()
  })

  it('updates active identity and autosave keys after canonical rename', async () => {
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        name: 'new_workflow',
        display_name: 'New workflow',
        path: '/tmp/new_workflow.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    })
    const store = useWorkflowStore()
    store.workflows = [{
      name: 'Untitled',
      display_name: 'Untitled',
      path: '/tmp/Untitled.json',
      last_modified: '2026-04-30T11:00:00Z',
    }]
    store.current = store.workflows[0]

    const renamed = await store.patchWorkflow('Untitled', {
      action: 'update',
      display_name: 'New workflow',
    })

    expect(renamed.name).toBe('new_workflow')
    expect(store.currentName).toBe('new_workflow')
    expect(store.workflows.map((workflow) => workflow.name)).toEqual(['new_workflow'])
    expect(autoSaveMocks.renameWorkflow).toHaveBeenCalledWith('Untitled', 'new_workflow')
    expect(autoSaveMocks.setLastOpenedWorkflow).toHaveBeenCalledWith('new_workflow')
  })

  it('keeps the source workflow listed when duplicating', async () => {
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        name: 'copy',
        display_name: 'Copy',
        path: '/tmp/copy.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    })
    const store = useWorkflowStore()
    store.workflows = [{
      name: 'source',
      display_name: 'Source',
      path: '/tmp/source.json',
      last_modified: '2026-04-30T11:00:00Z',
    }]
    store.current = store.workflows[0]

    await store.patchWorkflow('source', {
      action: 'duplicate',
      new_name: 'copy',
      display_name: 'Copy',
    })

    expect(store.workflows.map((workflow) => workflow.name).sort()).toEqual(['copy', 'source'])
    expect(autoSaveMocks.renameWorkflow).not.toHaveBeenCalled()
    expect(autoSaveMocks.setLastOpenedWorkflow).toHaveBeenCalledWith('copy')
  })
})
