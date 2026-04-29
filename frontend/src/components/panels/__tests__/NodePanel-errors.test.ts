import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import NodePanel from '../NodePanel.vue'
import { useUIStore } from '@/stores/ui'
import { useGraphSync, _resetGraphSyncForTest } from '@/composables/useGraphSync'
import type { ToolMetadata, ValidationResult } from '@/api/types'

function makeTool(): ToolMetadata {
  return {
    name: 'gaussian_blur',
    display_name: 'Gaussian Blur',
    package: 'bioimageflow-core',
    package_version: '0.3.2',
    tool_type: 'ProcessingTool',
    documentation: '',
    tags: [],
    categories: [],
    inputs: {
      sigma: {
        type: 'float',
        required: true,
        connectable: 'never',
        default: 1.0,
        min: 0.1,
        max: 50,
        step: 0.1,
      },
      threshold: {
        type: 'float',
        required: false,
        connectable: 'never',
        default: 0.5,
      },
    },
    outputs: {},
    environment: null,
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

function mountWithErrors(validationResult: ValidationResult | null) {
  const pinia = createPinia()
  setActivePinia(pinia)
  _resetGraphSyncForTest()

  const uiStore = useUIStore()
  const nodeId = 'node-1'
  uiStore.setSelectedNodes([nodeId])
  uiStore.setGraphNodes([{ id: nodeId, data: makeNodeData() }])

  // Set the singleton graphSync's validationResult before NodePanel mounts.
  const sync = useGraphSync()
  sync.validationResult.value = validationResult

  return mount(NodePanel, {
    global: { plugins: [pinia, PrimeVue] },
  })
}

describe('NodePanel — parameter error wiring', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    _resetGraphSyncForTest()
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
