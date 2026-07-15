import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import InputText from 'primevue/inputtext'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() },
}))

const workflowDraftMocks = vi.hoisted(() => ({
  ensureFreshForCriticalOperation: vi.fn().mockResolvedValue(true),
}))

vi.mock('@/stores/workflowDraft', () => ({
  useWorkflowDraftStore: () => workflowDraftMocks,
}))

import NodePanel from '@/components/panels/NodePanel.vue'
import RunButton from '@/components/execution/RunButton.vue'
import { api } from '@/api/client'
import {
  _resetGraphSyncForTest,
  useGraphSync,
} from '@/composables/useGraphSync'
import { useUIStore } from '@/stores/ui'
import type { GraphState, ToolMetadata } from '@/api/types'

const mockedApi = api as unknown as {
  post: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
}

const graph: GraphState = {
  nodes: [{
    id: 'files',
    name: 'Files',
    tool_name: 'files',
    position: [0, 0],
    parameters: { path: '/data/old' },
    resources: {},
    output_templates: {},
    enabled: true,
    collapsed: false,
  }],
  edges: [],
}

const tool = {
  name: 'files',
  display_name: 'Files',
  package: 'bioimageflow-core',
  package_version: '1.0.0',
  tool_type: 'ProcessingTool',
  accepts_upstream: false,
  dynamic_outputs: false,
  documentation: '',
  tags: [],
  categories: [],
  inputs: {
    path: {
      type: 'Path',
      required: true,
      nullable: false,
      connectable: 'never',
    },
  },
  outputs: {},
  environment: null,
} as ToolMetadata

describe('parameter edit followed immediately by Run', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    _resetGraphSyncForTest()
    vi.clearAllMocks()
    workflowDraftMocks.ensureFreshForCriticalOperation.mockResolvedValue(true)
    mockedApi.put.mockResolvedValue({
      data: { valid: true, node_statuses: {}, errors: [] },
    })
    mockedApi.post.mockResolvedValue({ data: {} })
  })

  it('submits the parameter emitted by the real NodePanel field', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const graphSync = useGraphSync()
    graphSync.syncGraphState(graph)

    const nodeData = {
      name: 'Files',
      toolName: 'files',
      tool,
      status: 'executed',
      parameters: { path: '/data/old' },
      resources: {},
      output_templates: {},
      collapsed: false,
      enabled: true,
      connectedInputs: {},
      pinnedInputs: {},
    }
    const ui = useUIStore()
    ui.setGraphNodes([{ id: 'files', data: nodeData }])
    ui.setSelectedNodes(['files'])

    const panel = mount(NodePanel, {
      global: { plugins: [[PrimeVue, { theme: { preset: Aura } }], pinia] },
    })
    const runButton = mount(RunButton, {
      props: {
        graph,
        graphSync,
        syncPending: false,
      },
      global: {
        plugins: [[PrimeVue, { theme: { preset: Aura } }], pinia],
        stubs: {
          Dialog: {
            template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
            props: ['visible'],
          },
        },
      },
    })

    panel
      .find('[data-testid="path-input-path"]')
      .findComponent(InputText)
      .vm.$emit('update:modelValue', '/data/new')
    await runButton.find('[data-testid="run-workflow-button"]').trigger('click')
    await flushPromises()

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/api/v1/execution/run',
      expect.objectContaining({
        graph: expect.objectContaining({
          nodes: [expect.objectContaining({ parameters: { path: '/data/new' } })],
        }),
      }),
    )

    panel.unmount()
    runButton.unmount()
  })
})
