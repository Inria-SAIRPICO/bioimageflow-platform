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
import type { WorkflowInfo } from '@/api/types'

describe('workflow store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.patch).mockReset()
    vi.mocked(api.post).mockReset()
    vi.mocked(api.put).mockReset()
    vi.mocked(api.delete).mockReset()
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
    const blob = new Blob(['zip'], { type: 'application/zip' })
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
      headers: { 'content-disposition': 'attachment; filename="wf.bioimageflow.zip"' },
    })
    const store = useWorkflowStore()

    await store.exportWorkflow('wf')

    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/workflows/wf/export',
      undefined,
      { responseType: 'blob' },
    )
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    const anchor = document.querySelector('a[download="wf.bioimageflow.zip"]')
    expect(anchor).toBeNull()
    expect(click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:workflow')
  })

  it('falls back to a BioImageFlow zip archive filename when export has no server filename', async () => {
    const blob = new Blob(['zip'], { type: 'application/zip' })
    vi.spyOn(window.URL, 'createObjectURL').mockReturnValue('blob:workflow')
    vi.spyOn(window.URL, 'revokeObjectURL').mockImplementation(() => {})
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})
    vi.mocked(api.post).mockResolvedValueOnce({
      data: blob,
      headers: {},
    })
    const store = useWorkflowStore()

    await store.exportWorkflow('wf')

    expect(document.querySelector('a[download="wf.bioimageflow.zip"]')).toBeNull()
    expect(click).toHaveBeenCalled()
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
    const file = new File(['zip'], 'workflow.bioimageflow.zip', {
      type: 'application/zip',
    })

    const response = await store.importWorkflow(file, { nameOverride: 'imported' })

    expect(response.info.name).toBe('imported')
    const [url, body, config] = vi.mocked(api.post).mock.calls[0]
    expect(url).toBe('/api/v1/workflows/import')
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get('file')).toBe(file)
    expect((body as FormData).get('name_override')).toBe('imported')
    expect(config).toBeUndefined()
    expect(store.workflows.map((workflow) => workflow.name)).toEqual(['imported'])
    expect(store.missingPackages[0].package_name).toBe('pkg')
    expect(store.missingTools[0].tool_name).toBe('Tool')
  })

  it('fetches the backend workflow tree and keeps a compatible flat list', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        path: '',
        display_name: 'Workflows',
        folders: [{
          path: 'Analysis',
          display_name: 'Analysis',
          folders: [],
          workflows: [{
            name: 'analysis/beta',
            folder: 'Analysis',
            display_name: 'Beta',
            path: '/tmp/Analysis/beta.json',
            last_modified: '2026-04-30T12:00:00Z',
          }],
        }],
        workflows: [{
          name: 'alpha',
          folder: '',
          display_name: 'Alpha',
          path: '/tmp/alpha.json',
          last_modified: '2026-04-30T11:00:00Z',
        }],
      },
    })
    const store = useWorkflowStore()

    await store.fetchWorkflowTree()

    expect(api.get).toHaveBeenCalledWith('/api/v1/workflows/tree')
    expect(store.workflowFolders).toEqual([{
      id: 'Analysis',
      name: 'Analysis',
      parentId: null,
    }])
    expect(store.workflowFolderIds['analysis/beta']).toBe('Analysis')
    expect(store.workflows.map((workflow) => workflow.name).sort()).toEqual([
      'alpha',
      'analysis/beta',
    ])
    expect(store.flattenedWorkflows.map((workflow) => workflow.name)).toEqual([
      'alpha',
      'analysis/beta',
    ])
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
    const file = new File(['zip'], 'workflow.bioimageflow.zip', {
      type: 'application/zip',
    })

    await expect(store.importWorkflow(file)).rejects.toMatchObject({
      name: 'WorkflowConflictError',
      suggestedName: 'wf_2',
    })
  })

  it('organizes workflows into folders while exposing a flattened workflow list', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        path: 'Analysis',
        display_name: 'Analysis',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        name: 'beta',
        folder: 'Analysis',
        display_name: 'Beta',
        path: '/tmp/Analysis/beta.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    })
    const store = useWorkflowStore()
    store.workflows = [
      {
        name: 'alpha',
        display_name: 'Alpha',
        path: '/tmp/alpha.json',
        last_modified: '2026-04-30T11:00:00Z',
      },
      {
        name: 'beta',
        display_name: 'Beta',
        path: '/tmp/beta.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    ]

    const folder = await store.createWorkflowFolder('Analysis')
    await store.moveWorkflowToFolder('beta', folder.id)

    expect(store.workflowTree[1]).toMatchObject({
      type: 'folder',
      id: folder.id,
      name: 'Analysis',
    })
    expect(store.flattenedWorkflows.map((workflow) => workflow.name)).toEqual([
      'alpha',
      'beta',
    ])
  })

  it('keeps returned workflow ids when moving a workflow into a folder with spaces', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        path: 'Analysis Results',
        display_name: 'Analysis Results',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        id: 'Analysis Results/beta',
        name: 'beta',
        folder: 'Analysis Results',
        display_name: 'Beta',
        path: '/tmp/Analysis Results/beta/workflow.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    })
    const store = useWorkflowStore()
    store.workflows = [
      {
        id: 'beta',
        name: 'beta',
        display_name: 'Beta',
        path: '/tmp/beta/workflow.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    ]

    const folder = await store.createWorkflowFolder('Analysis Results')
    await store.moveWorkflowToFolder('beta', folder.id)

    expect(api.post).toHaveBeenCalledWith('/api/v1/workflows/folders', {
      path: 'Analysis Results',
    })
    expect(api.patch).toHaveBeenCalledWith(
      '/api/v1/workflows/beta',
      { action: 'update', folder: 'Analysis Results' },
    )
    expect(store.workflowFolderIds).toEqual({
      'Analysis Results/beta': 'Analysis Results',
    })
    expect(store.flattenedWorkflows.map((workflow) => (
      (workflow as WorkflowInfo & { id?: string }).id || workflow.name
    ))).toEqual(['Analysis Results/beta'])
  })

  it('updates the active workflow identity when moving it into a folder', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        path: 'Analysis Results',
        display_name: 'Analysis Results',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        id: 'Analysis Results/beta',
        name: 'beta',
        folder: 'Analysis Results',
        display_name: 'Beta',
        path: '/tmp/Analysis Results/beta/workflow.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    })
    vi.mocked(api.put).mockResolvedValueOnce({
      data: {
        id: 'Analysis Results/beta',
        name: 'beta',
        folder: 'Analysis Results',
        display_name: 'Beta',
        path: '/tmp/Analysis Results/beta/workflow.json',
        last_modified: '2026-04-30T12:01:00Z',
      },
    })
    const store = useWorkflowStore()
    const workflow: WorkflowInfo = {
      id: 'beta',
      name: 'beta',
      display_name: 'Beta',
      path: '/tmp/beta/workflow.json',
      last_modified: '2026-04-30T12:00:00Z',
    }
    store.workflows = [workflow]
    store.current = workflow

    const folder = await store.createWorkflowFolder('Analysis Results')
    await store.moveWorkflowToFolder('beta', folder.id)
    await store.saveWorkflow({ nodes: [], edges: [] })

    expect(store.currentName).toBe('Analysis Results/beta')
    expect(autoSaveMocks.renameWorkflow).toHaveBeenCalledWith(
      'beta',
      'Analysis Results/beta',
    )
    expect(autoSaveMocks.setLastOpenedWorkflow).toHaveBeenCalledWith(
      'Analysis Results/beta',
    )
    expect(api.put).toHaveBeenCalledWith(
      '/api/v1/workflows/Analysis%20Results/beta',
      { graph: { nodes: [], edges: [] } },
    )
  })

  it('renames and deletes workflow folders without deleting workflows', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        path: 'Drafts',
        display_name: 'Drafts',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.patch)
      .mockResolvedValueOnce({
        data: {
          name: 'alpha',
          folder: 'Drafts',
          display_name: 'Alpha',
          path: '/tmp/Drafts/alpha.json',
          last_modified: '2026-04-30T11:00:00Z',
        },
      })
      .mockResolvedValueOnce({
        data: {
          path: 'Published',
          display_name: 'Published',
          folders: [],
          workflows: [],
        },
      })
    vi.mocked(api.get)
      .mockResolvedValueOnce({
        data: {
          path: '',
          display_name: 'workspace',
          folders: [{
            path: 'Published',
            display_name: 'Published',
            folders: [],
            workflows: [{
              name: 'alpha',
              folder: 'Published',
              display_name: 'Alpha',
              path: '/tmp/Published/alpha.json',
              last_modified: '2026-04-30T11:00:00Z',
            }],
          }],
          workflows: [],
        },
      })
      .mockResolvedValueOnce({
        data: {
          path: '',
          display_name: 'workspace',
          folders: [],
          workflows: [{
            name: 'alpha',
            folder: '',
            display_name: 'Alpha',
            path: '/tmp/alpha.json',
            last_modified: '2026-04-30T11:00:00Z',
          }],
        },
      })
    vi.mocked(api.delete).mockResolvedValueOnce({ data: { deleted: true } })
    const store = useWorkflowStore()
    store.workflows = [{
      name: 'alpha',
      display_name: 'Alpha',
      path: '/tmp/alpha.json',
      last_modified: '2026-04-30T11:00:00Z',
    }]
    const folder = await store.createWorkflowFolder('Drafts')
    await store.moveWorkflowToFolder('alpha', folder.id)

    await store.renameWorkflowFolder(folder.id, 'Published')
    expect(store.workflowFolders[0].name).toBe('Published')

    await store.deleteWorkflowFolder('Published', 'move_children_up')
    expect(store.workflowFolders).toEqual([])
    expect(store.workflowFolderIds.alpha).toBeNull()
    expect(store.flattenedWorkflows.map((workflow) => workflow.name)).toEqual(['alpha'])
  })

  it('moves nested folders with spaces and remaps active workflow identity', async () => {
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        path: 'Archive 2026/Quality Control',
        display_name: 'Quality Control',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        path: '',
        display_name: 'workspace',
        folders: [{
          path: 'Archive 2026',
          display_name: 'Archive 2026',
          folders: [{
            path: 'Archive 2026/Quality Control',
            display_name: 'Quality Control',
            folders: [],
            workflows: [{
              id: 'Archive 2026/Quality Control/beta',
              name: 'beta',
              folder: 'Archive 2026/Quality Control',
              display_name: 'Beta',
              path: '/tmp/Archive 2026/Quality Control/beta/workflow.json',
              last_modified: '2026-04-30T12:00:00Z',
            }],
          }],
          workflows: [],
        }],
        workflows: [],
      },
    })
    const store = useWorkflowStore()
    const workflow: WorkflowInfo = {
      id: 'Analysis Results/Quality Control/beta',
      name: 'beta',
      folder: 'Analysis Results/Quality Control',
      display_name: 'Beta',
      path: '/tmp/Analysis Results/Quality Control/beta/workflow.json',
      last_modified: '2026-04-30T12:00:00Z',
    }
    store.workflowFolders = [
      { id: 'Analysis Results', name: 'Analysis Results', parentId: null },
      {
        id: 'Analysis Results/Quality Control',
        name: 'Quality Control',
        parentId: 'Analysis Results',
      },
      { id: 'Archive 2026', name: 'Archive 2026', parentId: null },
    ]
    store.workflows = [workflow]
    store.workflowFolderIds = {
      'Analysis Results/Quality Control/beta': 'Analysis Results/Quality Control',
    }
    store.workflowOrder = ['Analysis Results/Quality Control/beta']
    store.current = workflow

    await store.moveWorkflowFolder('Analysis Results/Quality Control', 'Archive 2026')

    expect(api.patch).toHaveBeenCalledWith(
      '/api/v1/workflows/folders/Analysis%20Results/Quality%20Control',
      { new_path: 'Archive 2026/Quality Control' },
    )
    expect(autoSaveMocks.renameWorkflow).toHaveBeenCalledWith(
      'Analysis Results/Quality Control/beta',
      'Archive 2026/Quality Control/beta',
    )
    expect(store.currentName).toBe('Archive 2026/Quality Control/beta')
    expect(store.workflowFolders).toContainEqual({
      id: 'Archive 2026/Quality Control',
      name: 'Quality Control',
      parentId: 'Archive 2026',
    })
  })

  it('sorts workflows and folders alphabetically within each folder', async () => {
    const store = useWorkflowStore()
    store.workflowFolders = [
      { id: 'Z Folder', name: 'Z Folder', parentId: null },
    ]
    store.workflows = [
      {
        name: 'alpha',
        display_name: 'Alpha',
        path: '/tmp/alpha.json',
        last_modified: '2026-04-30T11:00:00Z',
      },
      {
        name: 'beta',
        display_name: 'Beta',
        path: '/tmp/beta.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    ]

    expect(store.workflowTree.map((node) => (
      node.type === 'folder' ? node.name : node.workflow.display_name
    ))).toEqual(['Alpha', 'Beta', 'Z Folder'])
  })

  it('keeps alphabetical workflow order even when workflow ids are moved before another id', async () => {
    const store = useWorkflowStore()
    store.workflows = [
      {
        name: 'alpha',
        display_name: 'Alpha',
        path: '/tmp/alpha.json',
        last_modified: '2026-04-30T11:00:00Z',
      },
      {
        name: 'beta',
        display_name: 'Beta',
        path: '/tmp/beta.json',
        last_modified: '2026-04-30T12:00:00Z',
      },
    ]

    await store.moveWorkflowBefore('beta', 'alpha')

    expect(store.flattenedWorkflows.map((workflow) => workflow.name)).toEqual([
      'alpha',
      'beta',
    ])
  })
})
