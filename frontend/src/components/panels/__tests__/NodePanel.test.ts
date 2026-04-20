import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import NodePanel from '../NodePanel.vue'
import { useUIStore } from '@/stores/ui'
import type { ToolMetadata, InputFieldSchema } from '@/api/types'

function makeTool(overrides: Partial<ToolMetadata> = {}): ToolMetadata {
  return {
    name: 'gaussian_blur',
    display_name: 'Gaussian Blur',
    package: 'bioimageflow-core',
    package_version: '0.3.2',
    tool_type: 'ProcessingTool',
    documentation: 'Apply gaussian blur to smooth images.',
    tags: [],
    categories: ['Filtering'],
    inputs: {
      image: { type: 'ImagePath', connectable: true, description: 'Input image path' },
      sigma: { type: 'float', connectable: false, default: 1.0, min: 0.1, max: 50.0, step: 0.1, description: 'Blur strength' },
      threshold: { type: 'float', connectable: false, default: 0.5, optional: true, description: 'Optional threshold' },
    },
    outputs: {
      result: { type: 'ImagePath' },
      mask: { type: 'MaskPath' },
    },
    environment: null,
    ...overrides,
  }
}

function makeNodeData(overrides: Record<string, unknown> = {}) {
  return {
    name: 'Blur 1',
    toolName: 'gaussian_blur',
    tool: makeTool(),
    status: 'unexecuted',
    parameters: { sigma: 1.0, threshold: 0.5 } as Record<string, unknown>,
    collapsed: false,
    enabled: true,
    connectedInputs: {} as Record<string, string>,
    pinnedInputs: { image: true } as Record<string, boolean>,
    output_templates: { result: '', mask: '' } as Record<string, string>,
    ...overrides,
  }
}

function mountPanel(nodeData: ReturnType<typeof makeNodeData> | null = null) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const uiStore = useUIStore()

  if (nodeData) {
    const nodeId = 'node-1'
    uiStore.setSelectedNodes([nodeId])
    uiStore.setGraphNodes([{ id: nodeId, data: nodeData }])
  }

  return mount(NodePanel, {
    global: {
      plugins: [pinia, PrimeVue],
    },
  })
}

describe('NodePanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // --- Empty state ---

  it('shows empty state when no node selected', () => {
    const w = mountPanel()
    expect(w.find('.empty-state').exists()).toBe(true)
    expect(w.find('.empty-state').text()).toContain('Select a node')
  })

  // --- Fix 12: Enable/Disable toggle ---

  describe('enable/disable toggle', () => {
    it('renders the enabled toggle switch', () => {
      const w = mountPanel(makeNodeData())
      expect(w.find('[data-testid="node-enabled-toggle"]').exists()).toBe(true)
    })

    it('reflects the enabled state', () => {
      const data = makeNodeData({ enabled: true })
      const w = mountPanel(data)
      const toggle = w.find('[data-testid="node-enabled-toggle"]')
      expect(toggle.exists()).toBe(true)
    })
  })

  // --- Fix 13: Package + version display ---

  describe('package info', () => {
    it('displays package name and version', () => {
      const w = mountPanel(makeNodeData())
      const pkgInfo = w.find('.package-info')
      expect(pkgInfo.exists()).toBe(true)
      expect(pkgInfo.text()).toContain('bioimageflow-core')
      expect(pkgInfo.text()).toContain('v0.3.2')
    })
  })

  // --- Fix 14: Collapsible documentation ---

  describe('documentation panel', () => {
    it('renders the documentation panel when tool has documentation', () => {
      const w = mountPanel(makeNodeData())
      expect(w.find('[data-testid="doc-panel"]').exists()).toBe(true)
    })

    it('does not render documentation panel when tool has no documentation', () => {
      const tool = makeTool({ documentation: '' })
      const w = mountPanel(makeNodeData({ tool }))
      expect(w.find('[data-testid="doc-panel"]').exists()).toBe(false)
    })
  })

  // --- Fix 15: Reset to default button ---

  describe('reset to default', () => {
    it('renders reset buttons for each parameter', () => {
      const w = mountPanel(makeNodeData())
      const resetButtons = w.findAll('[data-testid="reset-default"]')
      expect(resetButtons.length).toBeGreaterThan(0)
    })

    it('resets parameter to default value when clicked', async () => {
      const data = makeNodeData()
      data.parameters.sigma = 5.0
      const w = mountPanel(data)
      const resetButtons = w.findAll('[data-testid="reset-default"]')
      // The sigma reset button (second param row since image is first)
      const sigmaReset = resetButtons[1]
      await sigmaReset.trigger('click')
      expect(data.parameters.sigma).toBe(1.0)
    })
  })

  // --- Fix 16: None toggle for Optional fields ---

  describe('none toggle for optional fields', () => {
    it('renders none toggle only for optional fields', () => {
      const w = mountPanel(makeNodeData())
      const noneToggles = w.findAll('[data-testid="none-toggle"]')
      // Only 'threshold' is optional
      expect(noneToggles.length).toBe(1)
    })

    it('sets parameter to null when toggled via component event', async () => {
      const data = makeNodeData()
      data.parameters.threshold = 0.5
      const w = mountPanel(data)
      const noneToggle = w.find('[data-testid="none-toggle"]')
      // PrimeVue Checkbox emits update:modelValue; find the Checkbox component and trigger it
      const checkbox = noneToggle.findComponent({ name: 'Checkbox' })
      await checkbox.vm.$emit('update:modelValue', true)
      await w.vm.$nextTick()
      expect(data.parameters.threshold).toBe(null)
    })
  })

  // --- Fix 17: Connectable/Pin checkbox ---

  describe('pin toggle for connectable fields', () => {
    it('renders pin toggle only for connectable fields', () => {
      const w = mountPanel(makeNodeData())
      const pinToggles = w.findAll('[data-testid="pin-toggle"]')
      // 'image' is connectable
      expect(pinToggles.length).toBe(1)
    })

    it('toggles the pinned state via component event', async () => {
      const data = makeNodeData()
      data.pinnedInputs = { image: true }
      const w = mountPanel(data)
      const pinToggle = w.find('[data-testid="pin-toggle"]')
      await pinToggle.trigger('click')
      await w.vm.$nextTick()
      expect(data.pinnedInputs.image).toBe(false)
    })
  })

  // --- Fix 18: Collapsible help text ---

  describe('collapsible help text', () => {
    it('renders help toggle buttons for fields with descriptions', () => {
      const w = mountPanel(makeNodeData())
      const helpToggles = w.findAll('[data-testid="help-toggle"]')
      // All three fields have descriptions
      expect(helpToggles.length).toBe(3)
    })

    it('help text is hidden by default', () => {
      const w = mountPanel(makeNodeData())
      expect(w.find('[data-testid="param-help-text"]').exists()).toBe(false)
    })

    it('shows help text when toggle is clicked', async () => {
      const w = mountPanel(makeNodeData())
      const helpToggle = w.findAll('[data-testid="help-toggle"]')[0]
      await helpToggle.trigger('click')
      const helpText = w.find('[data-testid="param-help-text"]')
      expect(helpText.exists()).toBe(true)
      expect(helpText.text()).toContain('Input image path')
    })
  })

  // --- Fix 19: Output template editing ---

  describe('output template editing', () => {
    it('renders editable template inputs for path-typed outputs', () => {
      const w = mountPanel(makeNodeData())
      const templateInputs = w.findAll('[data-testid="output-template"]')
      // Both result (ImagePath) and mask (MaskPath) are path-typed
      expect(templateInputs.length).toBe(2)
    })

    it('does not render template input for non-path outputs', () => {
      const tool = makeTool({
        outputs: {
          count: { type: 'int' },
          label: { type: 'str' },
        },
      })
      const w = mountPanel(makeNodeData({ tool, output_templates: {} }))
      const templateInputs = w.findAll('[data-testid="output-template"]')
      expect(templateInputs.length).toBe(0)
    })
  })

  // --- Multi-selection ---

  it('shows multi-select message when multiple nodes are selected', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const uiStore = useUIStore()
    uiStore.setSelectedNodes(['node-1', 'node-2'])
    uiStore.setGraphNodes([
      { id: 'node-1', data: makeNodeData() },
      { id: 'node-2', data: makeNodeData({ name: 'Blur 2' }) },
    ])
    const w = mount(NodePanel, {
      global: { plugins: [pinia, PrimeVue] },
    })
    expect(w.find('.multi-select').exists()).toBe(true)
    expect(w.find('.multi-select').text()).toContain('2 nodes selected')
  })
})
