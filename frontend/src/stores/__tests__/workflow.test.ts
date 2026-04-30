import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError } from 'axios'

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
    vi.mocked(api.post).mockReset()
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    })
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: vi.fn(),
    })
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

  it('downloads exported workflows using the server filename', async () => {
    const blob = new Blob(['{}'], { type: 'application/json' })
    const createObjectURL = vi
      .spyOn(window.URL, 'createObjectURL')
      .mockReturnValue('blob:workflow')
    const revokeObjectURL = vi
      .spyOn(window.URL, 'revokeObjectURL')
      .mockImplementation(() => {})
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})
    vi.mocked(api.post).mockResolvedValueOnce({
      data: blob,
      headers: { 'content-disposition': 'attachment; filename="wf.bioimageflow.json"' },
    })
    const store = useWorkflowStore()

    await store.exportWorkflow('wf')

    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/workflows/wf/export',
      undefined,
      { responseType: 'blob' },
    )
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    const anchor = document.querySelector('a[download="wf.bioimageflow.json"]')
    expect(anchor).toBeNull()
    expect(click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:workflow')
  })

  it('uploads import files as FormData and stores missing dependency data', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        info: {
          name: 'imported',
          display_name: 'Imported',
          path: '/tmp/imported.json',
          last_modified: '2026-04-30T12:00:00Z',
        },
        missing_packages: [{
          package_name: 'pkg',
          required_version: '1.0.0',
          installed_versions: [],
          affected_nodes: ['n1'],
        }],
        missing_tools: [{
          node_id: 'n1',
          tool_name: 'Tool',
          installed_versions: [],
        }],
      },
    })
    const store = useWorkflowStore()
    const file = new File(['{}'], 'workflow.bioimageflow.json', {
      type: 'application/json',
    })

    const response = await store.importWorkflow(file, { nameOverride: 'imported' })

    expect(response.info.name).toBe('imported')
    const [url, body, config] = vi.mocked(api.post).mock.calls[0]
    expect(url).toBe('/api/v1/workflows/import')
    expect(body).toBeInstanceOf(FormData)
    expect(config).toBeUndefined()
    expect(store.workflows.map((workflow) => workflow.name)).toEqual(['imported'])
    expect(store.missingPackages[0].package_name).toBe('pkg')
    expect(store.missingTools[0].tool_name).toBe('Tool')
  })

  it('turns import conflicts into WorkflowConflictError', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new AxiosError(
      'conflict',
      undefined,
      undefined,
      undefined,
      {
        status: 409,
        statusText: 'Conflict',
        headers: {},
        config: {} as any,
        data: {
          detail: "Workflow 'wf' already exists",
          suggested_name: 'wf_2',
        },
      },
    ))
    const store = useWorkflowStore()
    const file = new File(['{}'], 'workflow.bioimageflow.json')

    await expect(store.importWorkflow(file)).rejects.toMatchObject({
      name: 'WorkflowConflictError',
      suggestedName: 'wf_2',
    })
  })
})
