import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { api } from '@/api/client'
import { useWorkflowStore } from '@/stores/workflow'
import WorkflowsPanel from '../WorkflowsPanel.vue'
import type { WorkflowInfo } from '@/api/types'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

const workflows: WorkflowInfo[] = [
  {
    id: 'alpha_api',
    name: 'alpha_api',
    folder: '',
    display_name: 'Alpha Workflow',
    description: 'Segment nuclei and measure intensities.',
    path: '/library/workflows/alpha_api/workflow.json',
    storage_path: '/library/workflows/alpha_api',
    last_modified: '2026-04-30T12:34:56Z',
  },
  {
    id: 'beta_api',
    name: 'beta_api',
    folder: '',
    display_name: 'Beta Workflow',
    description: null,
    path: '/library/workflows/beta_api/workflow.json',
    storage_path: '/library/workflows/beta_api',
    last_modified: '2026-05-01T08:00:00Z',
  },
]


function cloneTree<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function removeNode(nodes: any[], key: string): any | null {
  const index = nodes.findIndex((node) => node.key === key)
  if (index !== -1) {
    return nodes.splice(index, 1)[0]
  }
  for (const node of nodes) {
    const removed = removeNode(node.children ?? [], key)
    if (removed) return removed
  }
  return null
}

function findNode(nodes: any[], key: string): any | null {
  for (const node of nodes) {
    if (node.key === key) return node
    const child = findNode(node.children ?? [], key)
    if (child) return child
  }
  return null
}

async function dropTreeNode(wrapper: ReturnType<typeof mount>, dragKey: string, buildValue: (nodes: any[], dragNode: any) => any[]): Promise<void> {
  const vm = wrapper.vm as any
  const nodes = cloneTree(vm.treeNodes)
  const dragNode = removeNode(nodes, dragKey)
  if (!dragNode) throw new Error(`Missing drag node ${dragKey}`)
  await vm.onTreeNodeDrop({
    value: buildValue(nodes, dragNode),
    dragNode,
  } as any)
}

function mountPanel(items: WorkflowInfo[] = workflows) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useWorkflowStore()
  store.workflows = [...items]
  store.current = items[0] ?? null

  return mount(WorkflowsPanel, {
    global: {
      plugins: [pinia, PrimeVue],
      stubs: {
        Button: true,
        Dialog: {
          props: ['visible'],
          template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
        },
      },
    },
  })
}

describe('WorkflowsPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.get).mockReset()
    vi.mocked(api.post).mockReset()
    vi.mocked(api.patch).mockReset()
    vi.mocked(api.delete).mockReset()
  })

  it('renders compact workflow rows with display name and modified time only', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    const row = wrapper.find('[data-testid="workflow-row-alpha_api"]')
    expect(row.text()).toContain('Alpha Workflow')
    expect(row.find('[data-testid="workflow-row-time-alpha_api"]').text()).not.toBe('')
    expect(row.text()).not.toContain('alpha_api')
    expect(row.text()).not.toContain('/library/workflows/alpha_api')
    expect(row.text()).not.toContain('Segment nuclei')
  })

  it('shows selected workflow details with description, API name, file path, and storage path', async () => {
    const wrapper = mountPanel()
    await wrapper.find('[data-testid="workflow-row-beta_api"]').trigger('click')

    expect(wrapper.emitted('select-workflow')?.[0]).toEqual(['beta_api'])
    expect(wrapper.find('[data-testid="workflow-detail-description"]').text()).toContain(
      'No description.',
    )
    expect(wrapper.find('[data-testid="workflow-detail-api-name"]').text()).toContain('beta_api')
    expect(wrapper.find('[data-testid="workflow-detail-path"]').text()).toContain(
      '/library/workflows/beta_api/workflow.json',
    )
    expect(wrapper.find('[data-testid="workflow-detail-storage-path"]').text()).toContain(
      '/library/workflows/beta_api',
    )
  })

  it('selects full workflow ids when duplicate leaf names live in different folders', async () => {
    const duplicateWorkflows: WorkflowInfo[] = [
      {
        id: 'A/nuclei',
        name: 'nuclei',
        folder: 'A',
        display_name: 'Nuclei A',
        description: null,
        path: '/library/workflows/A/nuclei/workflow.json',
        last_modified: '2026-04-30T12:34:56Z',
      },
      {
        id: 'B/nuclei',
        name: 'nuclei',
        folder: 'B',
        display_name: 'Nuclei B',
        description: null,
        path: '/library/workflows/B/nuclei/workflow.json',
        last_modified: '2026-05-01T08:00:00Z',
      },
    ]
    const wrapper = mountPanel(duplicateWorkflows)
    const store = useWorkflowStore()
    store.workflowFolders = [
      { id: 'A', name: 'A', parentId: null },
      { id: 'B', name: 'B', parentId: null },
    ]
    store.workflowFolderIds = {
      'A/nuclei': 'A',
      'B/nuclei': 'B',
    }
    await flushPromises()

    await wrapper.find('[data-testid="workflow-row-B_nuclei"]').trigger('click')

    expect(wrapper.emitted('select-workflow')?.[0]).toEqual(['B/nuclei'])
    expect(wrapper.find('[data-testid="workflow-detail-api-name"]').text()).toContain('B/nuclei')
  })

  it('emits toolbar workflow actions using the selected workflow when required', async () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')
    const wrapper = mountPanel()
    await wrapper.find('[data-testid="workflow-row-beta_api"]').trigger('click')

    await wrapper.find('[data-testid="workflow-new-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-save-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-duplicate-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-import-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-export-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-delete-btn"]').trigger('click')

    expect(wrapper.emitted('new-workflow')).toHaveLength(1)
    expect(wrapper.emitted('save-workflow')).toHaveLength(1)
    expect(wrapper.emitted('duplicate-workflow')?.[0]).toEqual(['beta_api'])
    expect(wrapper.emitted('import-workflow')).toHaveLength(1)
    expect(wrapper.emitted('export-workflow')?.[0]).toEqual(['beta_api'])
    expect(wrapper.emitted('delete-workflow')?.[0]).toEqual(['beta_api'])
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({
      type: 'bioimageflow:workflow-command',
    }))
    dispatchSpy.mockRestore()
  })

  it('dispatches new workflow with the selected folder context', async () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')
    const wrapper = mountPanel()
    const store = useWorkflowStore()
    store.workflowFolders = [{
      id: 'Analysis Results',
      name: 'Analysis Results',
      parentId: null,
    }]
    await flushPromises()

    ;(wrapper.vm as any).onNodeSelect({
      data: {
        type: 'folder',
        id: 'Analysis Results',
        name: 'Analysis Results',
        hasChildren: false,
      },
    } as any)
    await wrapper.find('[data-testid="workflow-new-btn"]').trigger('click')

    expect(wrapper.emitted('new-workflow')?.[0]).toEqual(['Analysis Results'])
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({
      type: 'bioimageflow:workflow-command',
      detail: {
        action: 'new',
        folderId: 'Analysis Results',
      },
    }))
    dispatchSpy.mockRestore()
  })

  it('keeps workflow toolbar actions targeted at a workflow inside a folder', async () => {
    const nestedWorkflow: WorkflowInfo = {
      id: 'Analysis Results/beta_api',
      name: 'beta_api',
      folder: 'Analysis Results',
      display_name: 'Beta Workflow',
      description: null,
      path: '/library/workflows/Analysis Results/beta_api/workflow.json',
      storage_path: '/library/workflows/Analysis Results/beta_api',
      last_modified: '2026-05-01T08:00:00Z',
    }
    const wrapper = mountPanel([nestedWorkflow])
    const store = useWorkflowStore()
    store.workflowFolders = [{
      id: 'Analysis Results',
      name: 'Analysis Results',
      parentId: null,
    }]
    store.workflowFolderIds = {
      'Analysis Results/beta_api': 'Analysis Results',
    }
    await flushPromises()

    await wrapper.find('[data-testid="workflow-row-Analysis_Results_beta_api"]').trigger('click')
    expect(wrapper.find('[data-testid="workflow-rename-folder-btn"]').attributes('disabled')).toBeDefined()

    await wrapper.find('[data-testid="workflow-delete-btn"]').trigger('click')

    expect(wrapper.emitted('delete-workflow')?.[0]).toEqual(['Analysis Results/beta_api'])
    expect(wrapper.find('[data-testid="workflow-folder-delete-dialog"]').exists()).toBe(false)
  })

  it('opens the selected workflow on double click, Enter, and Open', async () => {
    const wrapper = mountPanel()

    await wrapper.find('[data-testid="workflow-row-alpha_api"]').trigger('dblclick')
    await wrapper.find('[data-testid="workflow-row-beta_api"]').trigger('click')
    await wrapper.find('[data-testid="workflow-row-beta_api"]').trigger('keydown.enter')
    await wrapper.find('[data-testid="workflow-open-btn"]').trigger('click')

    expect(wrapper.emitted('open-workflow')).toEqual([
      ['alpha_api'],
      ['beta_api'],
      ['beta_api'],
    ])
  })

  it('only sets the workflow drag MIME type from the drag handle', async () => {
    const wrapper = mountPanel()
    const setData = vi.fn()
    const dataTransfer = { setData }

    expect(wrapper.find('[data-testid="workflow-row-alpha_api"]').attributes('draggable')).toBeUndefined()
    await wrapper.find('[data-testid="workflow-drag-alpha_api"]').trigger('dragstart', {
      dataTransfer,
    })

    expect(setData).toHaveBeenCalledTimes(1)
    expect(setData).toHaveBeenCalledWith('application/bioimageflow-workflow', 'alpha_api')
    expect(setData).not.toHaveBeenCalledWith('text/plain', expect.any(String))
  })

  it('creates, renames, and deletes the selected folder from the toolbar', async () => {
    const promptSpy = vi.spyOn(window, 'prompt')
    const confirmSpy = vi.spyOn(window, 'confirm')
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
            workflows: [],
          }],
          workflows,
        },
      })
      .mockResolvedValueOnce({
        data: {
          path: '',
          display_name: 'workspace',
          folders: [],
          workflows,
        },
      })
    vi.mocked(api.delete).mockResolvedValueOnce({ data: { deleted: true } })
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        name: 'beta_api',
        id: 'beta_api',
        folder: 'Analysis',
        display_name: 'Beta Workflow',
        description: null,
        path: '/library/workflows/Analysis/beta_api/workflow.json',
        storage_path: '/library/workflows/Analysis/beta_api',
        last_modified: '2026-05-01T08:00:00Z',
      },
    })
    const wrapper = mountPanel()

    await wrapper.find('[data-testid="workflow-new-folder-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-folder-name-input"]').setValue('Analysis')
    await wrapper.find('[data-testid="workflow-folder-dialog-submit"]').trigger('click')
    await flushPromises()
    const store = useWorkflowStore()
    const folder = store.workflowFolders[0]
    expect(folder.name).toBe('Analysis')
    expect(wrapper.find(`[data-testid="workflow-folder-${folder.id}"]`).text()).toContain(
      'Analysis',
    )
    expect(wrapper.find(`[data-testid="workflow-folder-rename-${folder.id}"]`).exists()).toBe(false)
    expect(wrapper.find(`[data-testid="workflow-folder-delete-${folder.id}"]`).exists()).toBe(false)

    await wrapper.find('[data-testid="workflow-rename-folder-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-folder-name-input"]').setValue('Published')
    await wrapper.find('[data-testid="workflow-folder-dialog-submit"]').trigger('click')
    await flushPromises()
    expect(store.workflowFolders[0].name).toBe('Published')

    await wrapper.find('[data-testid="workflow-delete-btn"]').trigger('click')
    await wrapper.find('[data-testid="workflow-folder-delete-confirm"]').trigger('click')
    await flushPromises()
    expect(promptSpy).not.toHaveBeenCalled()
    expect(confirmSpy).not.toHaveBeenCalled()
    expect(api.delete).toHaveBeenCalledWith(
      '/api/v1/workflows/folders/Published',
      { data: { policy: 'empty' } },
    )
    expect(store.workflowFolders).toEqual([])
    promptSpy.mockRestore()
    confirmSpy.mockRestore()
  })

  it('offers delete-all and move-up policies when deleting a folder with children', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        path: 'Analysis',
        display_name: 'Analysis',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.delete).mockResolvedValueOnce({ data: { deleted: true } })
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        name: 'beta_api',
        id: 'beta_api',
        folder: 'Analysis',
        display_name: 'Beta Workflow',
        description: null,
        path: '/library/workflows/Analysis/beta_api/workflow.json',
        storage_path: '/library/workflows/Analysis/beta_api',
        last_modified: '2026-05-01T08:00:00Z',
      },
    })
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        path: '',
        display_name: 'workspace',
        folders: [],
        workflows,
      },
    })
    const wrapper = mountPanel()
    const store = useWorkflowStore()
    const folder = await store.createWorkflowFolder('Analysis')
    await store.moveWorkflowToFolder('beta_api', folder.id)
    await flushPromises()

    ;(wrapper.vm as any).selectFolder(folder.id)
    await flushPromises()

    await wrapper.find('[data-testid="workflow-delete-btn"]').trigger('click')
    expect(wrapper.find('[data-testid="workflow-folder-delete-move-up"]').exists()).toBe(true)

    await wrapper.find('[data-testid="workflow-folder-delete-move-up"]').trigger('click')
    await flushPromises()

    expect(api.delete).toHaveBeenCalledWith(
      '/api/v1/workflows/folders/Analysis',
      { data: { policy: 'move_children_up' } },
    )
  })

  it('moves a dragged workflow into a folder and keeps flattened selection behavior', async () => {
    const wrapper = mountPanel()
    const store = useWorkflowStore()
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
        name: 'beta_api',
        id: 'beta_api',
        folder: 'Analysis',
        display_name: 'Beta Workflow',
        description: null,
        path: '/library/workflows/Analysis/beta_api/workflow.json',
        storage_path: '/library/workflows/Analysis/beta_api',
        last_modified: '2026-05-01T08:00:00Z',
      },
    })
    const folder = await store.createWorkflowFolder('Analysis')
    await flushPromises()

    await dropTreeNode(wrapper, 'workflow-tree-workflow_beta_api', (nodes, dragNode) => {
      const targetFolder = findNode(nodes, 'workflow-tree-folder_Analysis')
      targetFolder.children = [...(targetFolder.children ?? []), dragNode]
      return nodes
    })
    await flushPromises()

    expect(store.workflowFolderIds.beta_api).toBe(folder.id)
    expect(store.flattenedWorkflows.map((workflow) => workflow.name)).toEqual([
      'beta_api',
      'alpha_api',
    ])
    await wrapper.find('[data-testid="workflow-row-beta_api"]').trigger('click')
    const emitted = wrapper.emitted('select-workflow') ?? []
    expect(emitted[emitted.length - 1]).toEqual(['beta_api'])
  })

  it('moves a dragged folder into another folder', async () => {
    const wrapper = mountPanel()
    const store = useWorkflowStore()
    store.workflowFolders = [
      { id: 'A', name: 'A', parentId: null },
      { id: 'B', name: 'B', parentId: null },
    ]
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        path: 'B/A',
        display_name: 'A',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        path: '',
        display_name: 'workspace',
        folders: [{
          path: 'B',
          display_name: 'B',
          folders: [{
            path: 'B/A',
            display_name: 'A',
            folders: [],
            workflows: [],
          }],
          workflows: [],
        }],
        workflows,
      },
    })
    await flushPromises()

    await dropTreeNode(wrapper, 'workflow-tree-folder_A', (nodes, dragNode) => {
      const targetFolder = findNode(nodes, 'workflow-tree-folder_B')
      targetFolder.children = [...(targetFolder.children ?? []), dragNode]
      return nodes
    })
    await flushPromises()

    expect(api.patch).toHaveBeenCalledWith(
      '/api/v1/workflows/folders/A',
      { new_path: 'B/A' },
    )
    expect(store.workflowFolders).toContainEqual({ id: 'B/A', name: 'A', parentId: 'B' })
  })

  it('keeps folder selection current after moving a selected folder', async () => {
    const wrapper = mountPanel()
    const store = useWorkflowStore()
    store.workflowFolders = [
      { id: 'A', name: 'A', parentId: null },
      { id: 'B Folder', name: 'B Folder', parentId: null },
    ]
    vi.mocked(api.patch).mockResolvedValueOnce({
      data: {
        path: 'B Folder/A',
        display_name: 'A',
        folders: [],
        workflows: [],
      },
    })
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        path: '',
        display_name: 'workspace',
        folders: [{
          path: 'B Folder',
          display_name: 'B Folder',
          folders: [{
            path: 'B Folder/A',
            display_name: 'A',
            folders: [],
            workflows: [],
          }],
          workflows: [],
        }],
        workflows,
      },
    })
    await flushPromises()

    ;(wrapper.vm as any).selectFolder('A')
    await dropTreeNode(wrapper, 'workflow-tree-folder_A', (nodes, dragNode) => {
      const targetFolder = findNode(nodes, 'workflow-tree-folder_B_Folder')
      targetFolder.children = [...(targetFolder.children ?? []), dragNode]
      return nodes
    })
    await flushPromises()
    await wrapper.find('[data-testid="workflow-new-btn"]').trigger('click')

    expect(api.patch).toHaveBeenCalledWith(
      '/api/v1/workflows/folders/A',
      { new_path: 'B Folder/A' },
    )
    const newWorkflowEvents = wrapper.emitted('new-workflow') ?? []
    expect(newWorkflowEvents[newWorkflowEvents.length - 1]).toEqual(['B Folder/A'])
  })

  it('reorders workflow ids by dropping onto another workflow row', async () => {
    const wrapper = mountPanel()
    const store = useWorkflowStore()

    await dropTreeNode(wrapper, 'workflow-tree-workflow_beta_api', (nodes, dragNode) => [
      dragNode,
      ...nodes,
    ])

    expect(store.flattenedWorkflows.map((workflow) => workflow.name)).toEqual([
      'beta_api',
      'alpha_api',
    ])
  })
})
