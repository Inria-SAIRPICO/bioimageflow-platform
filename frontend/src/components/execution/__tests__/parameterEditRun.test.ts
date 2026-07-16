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
  acknowledgeAcceptedDraft: vi.fn(),
}))

vi.mock('@/stores/workflowDraft', () => ({
  useWorkflowDraftStore: () => workflowDraftMocks,
}))

import NodePanel from '@/components/panels/NodePanel.vue'
import RunButton from '@/components/execution/RunButton.vue'
import { api } from '@/api/client'
import {
  _resetGraphSyncForTest,
  serializeGraph,
  useGraphSync,
} from '@/composables/useGraphSync'
import {
  _resetCanvasCommandsForTest,
  useCanvasCommands,
} from '@/composables/useCanvasCommands'
import {
  _resetCanvasPersistenceForTest,
  useCanvasPersistence,
} from '@/composables/useCanvasPersistence'
import { useUIStore } from '@/stores/ui'
import { useWorkflowStore } from '@/stores/workflow'
import type { GraphState, ToolMetadata } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
} from '@/sessions/canvasSessionRegistry'

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
    _resetCanvasPersistenceForTest()
    _resetCanvasCommandsForTest()
    vi.clearAllMocks()
    workflowDraftMocks.ensureFreshForCriticalOperation.mockResolvedValue(true)
    mockedApi.put.mockResolvedValue({
      data: { valid: true, node_statuses: {}, errors: [] },
    })
    mockedApi.post.mockResolvedValue({
      data: {
        status: 'started',
        execution_id: 'exec-parameter-edit',
        workflow_id: 'parameter_edit',
        draft_revision: 2,
      },
    })
  })

  it('submits the parameter emitted by the real NodePanel field', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useWorkflowStore().current = {
      name: 'parameter_edit',
      display_name: 'Parameter edit',
      description: null,
      storage_path: '/tmp/workflows/parameter_edit',
      path: '/tmp/workflows/parameter_edit.json',
      last_modified: '2026-01-01T00:00:00Z',
    }
    const canvasId = canvasIdFromPanelId('workflow:parameter_edit')
    const descriptor = {
      kind: 'root' as const,
      canvasId,
      workflowId: 'parameter_edit',
    }
    let persistedDraft: WorkflowDraftResponse = {
      draft_version: 1,
      workflow_id: 'parameter_edit',
      base_saved_revision: 'sha256:test',
      draft_revision: 1,
      updated_at: '2026-01-01T00:00:00Z',
      updated_by: 'frontend',
      dirty_against_saved: false,
      graph,
      validation: { valid: true, node_statuses: {}, errors: [] },
    }
    const putDraft = vi.fn(async (
      _workflowId: string,
      body: {
        graph: GraphState
        expected_revision: number
        validate?: boolean
      },
    ) => {
      persistedDraft = {
        ...persistedDraft,
        draft_revision: body.expected_revision + 1,
        dirty_against_saved: true,
        graph: body.graph,
        validation: { valid: true, node_statuses: {}, errors: [] },
      }
      return persistedDraft
    })
    const writeRecovery = vi.fn(async () => {})
    const canvasPersistence = useCanvasPersistence({
      descriptor,
      getWorkflowId: () => 'parameter_edit',
      transports: {
        fetchDraft: async () => persistedDraft,
        putDraft,
        writeRecovery,
      },
    })
    canvasPersistence.initializeFromDraft(persistedDraft)
    const graphSync = useGraphSync({
      descriptor,
      getWorkflowId: () => 'parameter_edit',
    })
    canvasSessionRegistry.activate(canvasId)

    const nodeData = {
      name: 'Files',
      toolName: 'files',
      tool,
      status: 'executed',
      provisional: undefined as boolean | undefined,
      parameters: { path: '/data/old' },
      resources: {},
      output_templates: {},
      collapsed: false,
      enabled: true,
      connectedInputs: {},
      pinnedInputs: {},
    }
    const ui = useUIStore()
    const untouchedNodeData = {
      ...nodeData,
      name: 'Untouched',
      status: 'executed',
      parameters: { path: '/data/untouched' },
    }
    const canvasNodes = [
      { id: 'files', data: nodeData, position: { x: 0, y: 0 } },
      { id: 'untouched', data: untouchedNodeData, position: { x: 100, y: 0 } },
    ]
    ui.setCanvasGraphNodes(canvasId, [
      canvasNodes[0],
      canvasNodes[1],
    ])
    ui.setCanvasSelectedNodes(canvasId, ['files'])
    ui.setCanvasWorkflow(canvasId, 'parameter_edit', 'Parameter edit')
    const canvasCommands = useCanvasCommands({
      descriptor,
      renameNode: () => false,
      setNodeEnabled: () => false,
      setInputPinned: () => false,
      setOutputTemplate: () => false,
      togglePublishedInput: () => ({ status: 'unchanged' }),
      togglePublishedOutput: () => ({ status: 'unchanged' }),
      renamePublishedInput: () => ({ status: 'unchanged' }),
      renamePublishedOutput: () => ({ status: 'unchanged' }),
      updateParameter: (nodeId, key, value) => {
        const selected = canvasNodes.find(node => node.id === nodeId)
        if (!selected?.data) return false
        const parameters = { ...selected.data.parameters, [key]: value }
        selected.data.parameters = parameters
        selected.data.status = 'unexecuted'
        for (const node of canvasNodes) node.data.provisional = true
        canvasPersistence.queueGraph(serializeGraph({ nodes: canvasNodes, edges: [] }))
        return true
      },
    })
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

    expect(nodeData.status).toBe('unexecuted')
    expect(nodeData.provisional).toBe(true)
    expect(untouchedNodeData.status).toBe('executed')
    expect(untouchedNodeData.provisional).toBe(true)
    expect(graphSync.currentGraph.value.nodes[0]?.parameters).toEqual({
      path: '/data/new',
    })

    await runButton.find('[data-testid="run-workflow-button"]').trigger('click')
    await flushPromises()

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/api/v1/execution/run',
      expect.objectContaining({
        draft_revision: 2,
        graph: expect.objectContaining({
          nodes: expect.arrayContaining([
            expect.objectContaining({ parameters: { path: '/data/new' } }),
          ]),
        }),
      }),
    )
    expect(putDraft).toHaveBeenCalledOnce()
    expect(putDraft).toHaveBeenCalledWith(
      'parameter_edit',
      expect.objectContaining({
        graph: expect.objectContaining({
          nodes: expect.arrayContaining([
            expect.objectContaining({ parameters: { path: '/data/new' } }),
          ]),
        }),
        validate: true,
      }),
    )
    expect(writeRecovery).toHaveBeenCalledOnce()
    expect(mockedApi.put).not.toHaveBeenCalled()

    panel.unmount()
    runButton.unmount()
    canvasCommands.dispose()
  })
})
