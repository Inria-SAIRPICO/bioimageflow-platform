import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'

vi.mock('@/utils/nativeDialogs', () => ({
  isDesktop: vi.fn(),
  selectFile: vi.fn(),
  selectFiles: vi.fn(),
  selectFolder: vi.fn(),
}))

import { isDesktop, selectFiles } from '@/utils/nativeDialogs'
import NodePanel from '../NodePanel.vue'
import type { ToolMetadata } from '@/api/types'
import { useGraphSync, _resetGraphSyncForTest } from '@/composables/useGraphSync'
import {
  _resetCanvasPersistenceForTest,
  useCanvasPersistence,
} from '@/composables/useCanvasPersistence'
import { useDatasetsStore } from '@/stores/datasets'
import { useUIStore } from '@/stores/ui'
import { canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { registerRootCanvas } from '@/test-utils/canvasFixtures'
import {
  createInMemoryCanvasPersistence,
  makeWorkflowDraft,
} from '@/test-utils/persistenceFixtures'

const mockedIsDesktop = vi.mocked(isDesktop)
const mockedSelectFiles = vi.mocked(selectFiles)

const filesTool: ToolMetadata = {
  name: 'Files',
  display_name: 'Files',
  package: 'bioimageflow_common_tools',
  package_version: '1.0.0',
  tool_type: 'DataFrameTool',
  accepts_upstream: false,
  dynamic_outputs: false,
  dataframe_output: true,
  documentation: '',
  tags: [],
  categories: [],
  inputs: {
    path: {
      type: 'Path',
      required: false,
      nullable: true,
      connectable: 'never',
      default: null,
      display_name: 'Directory',
      path_picker: 'folder',
    },
    files: {
      type: 'list',
      required: false,
      nullable: true,
      connectable: 'never',
      default: null,
      display_name: 'Files',
    },
  },
  outputs: {},
  environment: null,
  source_kind: 'package',
  editable: false,
}

function mountFilesNode() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const workflowId = 'node-panel-path-pickers'
  const canvas = registerRootCanvas(workflowId)
  const draft = makeWorkflowDraft({ workflow_id: workflowId })
  const persistence = createInMemoryCanvasPersistence(draft)
  const canvasPersistence = useCanvasPersistence({
    descriptor: canvas.descriptor,
    getWorkflowId: () => workflowId,
    transports: persistence.transports,
  })
  canvasPersistence.initializeFromDraft(draft)
  useGraphSync({
    descriptor: canvas.descriptor,
    getWorkflowId: () => workflowId,
  })

  const uiStore = useUIStore()
  uiStore.setCanvasGraphNodes(canvas.canvasId, [{
    id: 'files_1',
    data: {
      name: 'Input files',
      toolName: 'Files',
      tool: filesTool,
      status: 'unexecuted',
      parameters: { path: '', files: null },
      collapsed: false,
      enabled: true,
      connectedInputs: {},
      pinnedInputs: {},
      output_templates: {},
    },
  }])
  uiStore.setCanvasSelectedNodes(canvas.canvasId, ['files_1'])

  return mount(NodePanel, {
    global: { plugins: [pinia, PrimeVue] },
  })
}

describe('NodePanel Files source pickers', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    canvasSessionRegistry.dispose()
    _resetGraphSyncForTest()
    _resetCanvasPersistenceForTest()
    vi.clearAllMocks()
  })

  it('activates the Datasets panel in browser mode without entering picker mode', async () => {
    mockedIsDesktop.mockReturnValue(false)
    const wrapper = mountFilesNode()
    const button = wrapper.get('[data-testid="select-files-source"]')

    expect(button.text()).toContain('Select in Datasets panel')
    expect(wrapper.find('[data-testid="select-folder-path"]').exists()).toBe(false)

    await button.trigger('click')

    const datasets = useDatasetsStore()
    expect(datasets.activationRequest).toBe(1)
    expect(datasets.picker).toBeNull()
  })

  it('offers native multi-file and folder actions in desktop mode', async () => {
    mockedIsDesktop.mockReturnValue(true)
    mockedSelectFiles.mockResolvedValue(['/data/a.tif', '/data/b.tif'])
    const wrapper = mountFilesNode()
    const button = wrapper.get('[data-testid="select-files-source"]')

    expect(button.text()).toContain('Select files')
    expect(wrapper.find('[data-testid="select-folder-path"]').exists()).toBe(true)

    await button.trigger('click')
    await flushPromises()

    expect(mockedSelectFiles).toHaveBeenCalledWith('Select files for: files', [])
  })
})
