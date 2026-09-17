import { describe, it, expect, beforeEach, vi } from 'vitest'
import { openNodeWithEditor } from '@/api/editor'
import { useSettingsStore } from '@/stores/settings'
vi.mock('@/api/editor', () => ({ openNodeWithEditor: vi.fn().mockResolvedValue({}) }))
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import NodePanel from '../NodePanel.vue'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useGraphSync, _resetGraphSyncForTest } from '@/composables/useGraphSync'
import {
  _resetCanvasPersistenceForTest,
  useCanvasPersistence,
} from '@/composables/useCanvasPersistence'
import { registerRootCanvas } from '@/test-utils/canvasFixtures'
import {
  createInMemoryCanvasPersistence,
  makeWorkflowDraft,
} from '@/test-utils/persistenceFixtures'
import type { ToolMetadata, ValidationResult } from '@/api/types'
import { encodeEndpointHandle } from '@/utils/endpointHandles'
import { useCanvasCommands } from '@/composables/useCanvasCommands'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
  type CanvasSessionDescriptor,
} from '@/sessions/canvasSessionRegistry'

function registerPanelCommands(
  descriptor: CanvasSessionDescriptor,
  canClearNodeOutputs: boolean,
  clearFailure?: unknown,
) {
  return useCanvasCommands({
    descriptor,
    ...(descriptor.kind === 'nested' ? { save: vi.fn() } : {}),
    renameNode: vi.fn(() => true),
    setNodeEnabled: vi.fn(() => true),
    setNodesEnabled: vi.fn(() => true),
    deleteNodes: vi.fn(() => true),
    clearNodeOutputs: vi.fn(async () => {
      if (clearFailure) throw clearFailure
      return true
    }),
    canClearNodeOutputs,
    setInputPinned: vi.fn(() => true),
    setOutputTemplate: vi.fn(() => true),
    toggleWorkflowInput: vi.fn(() => ({ status: 'changed' as const })),
    toggleWorkflowOutput: vi.fn(() => ({ status: 'changed' as const })),
    renameWorkflowInput: vi.fn(() => ({ status: 'changed' as const })),
    renameWorkflowOutput: vi.fn(() => ({ status: 'changed' as const })),
    updateParameter: vi.fn(() => true),
  })
}

function makeTool(): ToolMetadata {
  return {
    name: 'gaussian_blur',
    display_name: 'Gaussian Blur',
    package: 'bioimageflow-core',
    package_version: '0.3.2',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    dataframe_output: false,
    row_consumption: 'mapped',
    documentation: '',
    tags: [],
    categories: [],
    inputs: {
      sigma: {
        type: 'float',
        required: true,
        nullable: false,
        connectable: 'never',
        default: 1.0,
        min: 0.1,
        max: 50,
        step: 0.1,
      },
      threshold: {
        type: 'float',
        required: false,
        nullable: false,
        connectable: 'never',
        default: 0.5,
      },
    },
    outputs: {},
    environment: null,
    source_kind: 'package',
    editable: false,
  }
}

function makeNodeData(overrides: Record<string, unknown> = {}) {
  return {
    name: 'Blur 1',
    toolName: 'gaussian_blur',
    tool: makeTool(),
    status: 'unexecuted',
    parameters: { sigma: 1.0, threshold: 0.5 },
    collapsed: false,
    enabled: true,
    connectedInputs: {},
    pinnedInputs: {},
    output_templates: {},
    ...overrides,
  }
}

function mountWithErrors(
  validationResult: ValidationResult | null,
  nodeDataOverrides: Record<string, unknown> = {},
  clearFailure?: unknown,
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  _resetGraphSyncForTest()
  _resetCanvasPersistenceForTest()

  const workflowId = 'node-panel-errors'
  const canvas = registerRootCanvas(workflowId)
  const draft = makeWorkflowDraft({ workflow_id: workflowId })
  const persistence = createInMemoryCanvasPersistence(draft)
  const canvasPersistence = useCanvasPersistence({
    descriptor: canvas.descriptor,
    getWorkflowId: () => workflowId,
    transports: persistence.transports,
  })
  canvasPersistence.initializeFromDraft(draft)
  const sync = useGraphSync({
    descriptor: canvas.descriptor,
    getWorkflowId: () => workflowId,
  })
  registerPanelCommands(canvas.descriptor, true, clearFailure)

  const uiStore = useUIStore()
  const nodeId = 'node-1'
  uiStore.setSelectedNodes([nodeId])
  uiStore.setGraphNodes([{ id: nodeId, data: makeNodeData(nodeDataOverrides) }])

  // Seed the active canvas graph-sync validation before NodePanel mounts.
  sync.validationResult.value = validationResult

  return mount(NodePanel, {
    global: { plugins: [pinia, PrimeVue] },
  })
}

describe('NodePanel — parameter error wiring', () => {
  it('shows every server validation error when clearing outputs fails', async () => {
    const failure = Object.assign(new Error('Failed to build workflow: 2 error(s)'), {
      response: { data: { errors: [
        { type: 'parameter_invalid', node: 'extract_ch2_nuclei', field: 'input_image', detail: 'Unknown input' },
        { type: 'missing_connection', node: 'cellpose3_nuclei', detail: 'Missing upstream input' },
      ] } },
    })
    const wrapper = mountWithErrors(null, {}, failure)
    await wrapper.get('[data-testid="clear-node-outputs"]').trigger('click')
    await flushPromises()
    const confirm = document.body.querySelector<HTMLButtonElement>('[data-testid="node-destructive-confirm"]')
    expect(confirm).not.toBeNull()
    confirm!.click()
    await flushPromises()

    expect(document.body.querySelector('[data-testid="node-destructive-error"]')?.textContent).toContain('2 error(s)')
    const details = document.body.querySelector('[data-testid="node-destructive-validation-errors"]')?.textContent?.replace(/\s+/g, ' ')
    expect(details).toContain('extract_ch2_nuclei · input_image: Unknown input')
    expect(details).toContain('cellpose3_nuclei: Missing upstream input')
    wrapper.unmount()
  })

  it('disables bulk destructive controls while execution owns the mutation lock', async () => {
    const wrapper = mountWithErrors(null)
    const ui = useUIStore()
    ui.setSelectedNodes(['node-1', 'node-2'])
    ui.setGraphNodes([
      { id: 'node-1', data: makeNodeData() },
      { id: 'node-2', data: makeNodeData({ name: 'Blur 2' }) },
    ])
    const execution = useExecutionStore()
    execution.state = 'running'
    await flushPromises()

    expect(wrapper.get('[data-testid="bulk-delete-nodes"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="bulk-clear-node-outputs"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('hides output clearing on an explicitly unsupported nested canvas', async () => {
    const wrapper = mountWithErrors(null)
    const rootId = registerRootCanvas('nested-parent').canvasId
    const nestedCanvasId = canvasIdFromPanelId('nested-workflow:clear-unsupported')
    registerPanelCommands({
      kind: 'nested',
      canvasId: nestedCanvasId,
      sessionId: 'clear-unsupported',
      parentCanvasId: rootId,
    }, false)
    const ui = useUIStore()
    ui.setCanvasGraphNodes(nestedCanvasId, [
      { id: 'node-1', data: makeNodeData() },
      { id: 'node-2', data: makeNodeData({ name: 'Blur 2' }) },
    ])
    ui.setCanvasSelectedNodes(nestedCanvasId, ['node-1', 'node-2'])
    canvasSessionRegistry.activate(nestedCanvasId)
    await flushPromises()

    expect(wrapper.find('[data-testid="bulk-clear-node-outputs"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="clear-node-outputs"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="bulk-delete-nodes"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('opens the selected tool script and hides the action for restricted webapps', async () => {
    const wrapper = mountWithErrors(null)
    await wrapper.get('[data-testid="open-tool-script"]').trigger('click')
    await flushPromises()
    expect(openNodeWithEditor).toHaveBeenCalledWith('node-1', {
      showEmbeddedLoading: true,
    })
    const settings = useSettingsStore()
    settings.settings = { ...settings.settings, deployment_mode: 'webapp', enable_unsafe_webapp_features: false } as NonNullable<typeof settings.settings>
    await flushPromises()
    expect(wrapper.find('[data-testid="open-tool-script"]').exists()).toBe(false)
    wrapper.unmount()
  })

  beforeEach(() => {
    setActivePinia(createPinia())
    _resetGraphSyncForTest()
    _resetCanvasPersistenceForTest()
  })

  it('parameter row gets has-error class when a parameter_invalid error matches', () => {
    const w = mountWithErrors({
      valid: false,
      node_statuses: {},
      errors: [
        {
          type: 'parameter_invalid',
          detail: 'sigma must be > 0',
          node: 'node-1',
          field: 'sigma',
        },
      ],
    })
    const errorRows = w.findAll('.parameter-field-error.has-error')
    expect(errorRows.length).toBeGreaterThan(0)
    // The error block carries the error detail in title attribute.
    const titles = errorRows.map((r) => r.attributes('title') ?? '')
    expect(titles.join('\n')).toContain('sigma must be > 0')
  })

  it('parameter row without errors has no has-error class', () => {
    const w = mountWithErrors({
      valid: true,
      node_statuses: {},
      errors: [],
    })
    expect(w.findAll('.parameter-field-error.has-error')).toHaveLength(0)
  })

  it('replaces a connected parameter widget with its encoded-handle source label', () => {
    const tool = makeTool()
    tool.inputs.sigma = { ...tool.inputs.sigma!, connectable: 'by_default' }
    const handle = encodeEndpointHandle({ kind: 'tool-input', name: 'sigma' })
    const wrapper = mountWithErrors(null, {
      tool,
      connectedInputs: { [handle]: 'number of Seed Numbers 1' },
    })

    const sigmaRow = wrapper.findAll('.param-row').find(row => row.text().includes('sigma'))
    expect(sigmaRow).toBeTruthy()
    expect(sigmaRow!.get('.connected-source').text()).toBe('number of Seed Numbers 1')
    expect(sigmaRow!.find('input').exists()).toBe(false)
    expect(sigmaRow!.get('[data-testid="pin-toggle"]').attributes('aria-pressed')).toBe('true')
  })

  it('clearing the validation error removes the has-error class', async () => {
    const w = mountWithErrors({
      valid: false,
      node_statuses: {},
      errors: [
        {
          type: 'parameter_invalid',
          detail: 'sigma must be > 0',
          node: 'node-1',
          field: 'sigma',
        },
      ],
    })
    expect(w.findAll('.parameter-field-error.has-error').length).toBeGreaterThan(
      0,
    )
    const sync = useGraphSync()
    sync.validationResult.value = {
      valid: true,
      node_statuses: {},
      errors: [],
    }
    await w.vm.$nextTick()
    expect(w.findAll('.parameter-field-error.has-error')).toHaveLength(0)
  })

  it('an error for a different node does NOT mark this node\'s row', () => {
    const w = mountWithErrors({
      valid: false,
      node_statuses: {},
      errors: [
        {
          type: 'parameter_invalid',
          detail: 'other-node sigma',
          node: 'node-other',
          field: 'sigma',
        },
      ],
    })
    expect(w.findAll('.parameter-field-error.has-error')).toHaveLength(0)
  })

  it('an error for a different field does NOT mark this field', () => {
    const w = mountWithErrors({
      valid: false,
      node_statuses: {},
      errors: [
        {
          type: 'parameter_invalid',
          detail: 'threshold range error',
          node: 'node-1',
          field: 'threshold',
        },
      ],
    })
    // Find the row whose label equals "sigma" — it should not have has-error.
    const rows = w.findAll('.param-row')
    const sigmaRow = rows.find((r) => r.text().includes('sigma'))
    expect(sigmaRow).toBeTruthy()
    expect(sigmaRow!.find('.parameter-field-error.has-error').exists()).toBe(
      false,
    )
    // And the threshold row should be marked.
    const thresholdRow = rows.find((r) => r.text().includes('threshold'))
    expect(thresholdRow).toBeTruthy()
    expect(
      thresholdRow!.find('.parameter-field-error.has-error').exists(),
    ).toBe(true)
  })
})
