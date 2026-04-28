import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import NodePanel from '../NodePanel.vue'
import { useUIStore } from '@/stores/ui'
import { useGraphSync, _resetGraphSyncForTest } from '@/composables/useGraphSync'
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
      image: { type: 'ImagePath', required: true, nullable: false, connectable: 'by_default', description: 'Input image path' },
      sigma: { type: 'float', required: true, nullable: false, connectable: 'never', default: 1.0, min: 0.1, max: 50.0, step: 0.1, description: 'Blur strength' },
      threshold: { type: 'float', required: false, nullable: true, connectable: 'never', default: 0.5, description: 'Optional threshold' },
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
    _resetGraphSyncForTest()
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

  // --- Fix 16: None toggle for nullable fields ---

  describe('none toggle for nullable fields', () => {
    it('renders none toggle only for nullable fields', () => {
      const w = mountPanel(makeNodeData())
      const noneToggles = w.findAll('[data-testid="none-toggle"]')
      // Only `threshold` is nullable; `sigma` has a default but is non-nullable.
      expect(noneToggles.length).toBe(1)
    })

    it('does not render the toggle for a non-nullable field with a default', () => {
      // Regression: prior to nullable, ANY field with a default got the toggle —
      // which would crash the tool when the user nulled e.g. Atlas's `gaussian_std: int = 60`.
      const tool = makeTool({
        inputs: {
          k: { type: 'int', required: false, nullable: false, connectable: 'never', default: 5 },
        },
      })
      const w = mountPanel(makeNodeData({ tool, parameters: { k: 5 } }))
      expect(w.findAll('[data-testid="none-toggle"]').length).toBe(0)
    })

    it('renders the toggle for a nullable required field (no default)', () => {
      // `int | None` with no default: user must pass *something*, but None is acceptable.
      const tool = makeTool({
        inputs: {
          t: { type: 'int', required: true, nullable: true, connectable: 'never' },
        },
      })
      const w = mountPanel(makeNodeData({ tool, parameters: {} }))
      expect(w.findAll('[data-testid="none-toggle"]').length).toBe(1)
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

    it('treats both by_default and not_by_default as connectable (pin visible)', () => {
      const tool = makeTool({
        inputs: {
          a: { type: 'float', required: true, nullable: false, connectable: 'by_default' },
          b: { type: 'float', required: true, nullable: false, connectable: 'not_by_default' },
          c: { type: 'float', required: true, nullable: false, connectable: 'never' },
        },
      })
      const data = makeNodeData({ tool, pinnedInputs: { a: true, b: true } })
      const w = mountPanel(data)
      // Per the T6 decision: treat both by_default and not_by_default as
      // connectable and always show the pin. `never` hides it.
      expect(w.findAll('[data-testid="pin-toggle"]').length).toBe(2)
    })
  })

  describe('new wire-format fields', () => {
    it('accepts image_spec and new field shape', () => {
      const tool = makeTool({
        inputs: {
          mask: {
            type: 'ImagePath',
            required: true,
            nullable: false,
            connectable: 'by_default',
            display_name: 'Input mask',
            description: 'Binary mask',
            image_spec: {
              semantics: ['binary'],
              layouts: ['YX', 'ZYX'],
              dtypes: [],
              formats: [],
            },
          },
        },
      })
      const data = makeNodeData({ tool, pinnedInputs: { mask: true } })
      const w = mountPanel(data)
      // Field renders with a pin toggle (connectable !== 'never').
      expect(w.findAll('[data-testid="pin-toggle"]').length).toBe(1)
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

    it('does not render template input for DataFrameTool path outputs (column declarations)', () => {
      // DataFrameTool Outputs are column declarations, not file paths.
      // Files (a source DataFrameTool) declares `path: Path` to enable
      // downstream column-ref validation — it must NOT render a template editor.
      const tool = makeTool({
        name: 'files',
        display_name: 'Files',
        tool_type: 'DataFrameTool',
        inputs: {
          path: { type: 'Path', required: true, nullable: false, connectable: 'never', description: 'Directory' },
          pattern: { type: 'str', required: false, nullable: false, connectable: 'never', default: '*' },
        },
        outputs: {
          path: { type: 'Path' },
          filename: { type: 'str' },
        },
      })
      const w = mountPanel(makeNodeData({ tool, output_templates: {} }))
      const templateInputs = w.findAll('[data-testid="output-template"]')
      expect(templateInputs.length).toBe(0)
    })
  })

  // --- Path input: file/folder pickers (pywebview bridge) ---

  describe('path input widgets', () => {
    function mockPywebviewApi() {
      return {
        select_file: vi.fn(),
        select_files: vi.fn(),
        select_folder: vi.fn(),
        save_file: vi.fn(),
        set_title: vi.fn(),
        reveal_path: vi.fn(),
      }
    }

    afterEach(() => {
      delete window.pywebview
      vi.restoreAllMocks()
    })

    function makePathTool(): ToolMetadata {
      return makeTool({
        inputs: {
          input_image: { type: 'ImagePath', required: true, nullable: false, connectable: 'by_default', description: 'Image file' },
          work_dir: { type: 'Path', required: true, nullable: false, connectable: 'never', description: 'Working directory' },
        },
        outputs: { result: { type: 'ImagePath' } },
      })
    }

    it('renders a text input and file button for ImagePath (non-optional, no default)', () => {
      const data = makeNodeData({ tool: makePathTool(), parameters: {}, pinnedInputs: { input_image: true } })
      const w = mountPanel(data)
      // The widget must render — previously this rendered the "null" label
      // because an undefined parameter was treated as nulled.
      expect(w.find('[data-testid="path-input-input_image"]').exists()).toBe(true)
      expect(w.find('[data-testid="select-file-input_image"]').exists()).toBe(true)
      expect(w.find('.null-indicator').exists()).toBe(false)
    })

    it('renders both file and folder buttons for plain Path in desktop mode', () => {
      window.pywebview = { api: mockPywebviewApi() }

      const data = makeNodeData({ tool: makePathTool(), parameters: {} })
      const w = mountPanel(data)
      expect(w.find('[data-testid="select-file-work_dir"]').exists()).toBe(true)
      expect(w.find('[data-testid="select-folder-work_dir"]').exists()).toBe(true)
    })

    it('hides the folder button for plain Path in browser mode', () => {
      // No window.pywebview — browser mode.
      const data = makeNodeData({ tool: makePathTool(), parameters: {} })
      const w = mountPanel(data)
      expect(w.find('[data-testid="select-file-work_dir"]').exists()).toBe(true)
      expect(w.find('[data-testid="select-folder-work_dir"]').exists()).toBe(false)
    })

    it('renders only a file button for ImagePath (no folder button)', () => {
      const data = makeNodeData({ tool: makePathTool(), parameters: {}, pinnedInputs: { input_image: true } })
      const w = mountPanel(data)
      expect(w.find('[data-testid="select-file-input_image"]').exists()).toBe(true)
      expect(w.find('[data-testid="select-folder-input_image"]').exists()).toBe(false)
    })

    it('calls the pywebview select_file bridge and stores the chosen path', async () => {
      const api = mockPywebviewApi()
      api.select_file.mockResolvedValue('/absolute/chosen/image.tif')
      window.pywebview = { api }

      const data = makeNodeData({ tool: makePathTool(), parameters: {}, pinnedInputs: { input_image: true } })
      const w = mountPanel(data)

      await w.find('[data-testid="select-file-input_image"]').trigger('click')
      await flushPromises()

      expect(api.select_file).toHaveBeenCalledTimes(1)
      expect(data.parameters.input_image).toBe('/absolute/chosen/image.tif')
    })

    it('calls the pywebview select_folder bridge and stores the chosen path', async () => {
      const api = mockPywebviewApi()
      api.select_folder.mockResolvedValue('/absolute/chosen/dir')
      window.pywebview = { api }

      const data = makeNodeData({ tool: makePathTool(), parameters: {} })
      const w = mountPanel(data)

      await w.find('[data-testid="select-folder-work_dir"]').trigger('click')
      await flushPromises()

      expect(api.select_folder).toHaveBeenCalledTimes(1)
      expect(data.parameters.work_dir).toBe('/absolute/chosen/dir')
    })

    it('passes image extensions to the native dialog for ImagePath fields', async () => {
      const api = mockPywebviewApi()
      api.select_file.mockResolvedValue('/chosen.tif')
      window.pywebview = { api }

      const data = makeNodeData({
        tool: makePathTool(),
        parameters: {},
        pinnedInputs: { input_image: true },
      })
      const w = mountPanel(data)

      await w.find('[data-testid="select-file-input_image"]').trigger('click')
      await flushPromises()

      const [, fileTypes] = api.select_file.mock.calls[0]
      expect(fileTypes).toEqual(
        expect.arrayContaining(['*.tif', '*.tiff', '*.png', '*.jpg']),
      )
    })

    it('passes no filter for plain Path fields', async () => {
      const api = mockPywebviewApi()
      api.select_file.mockResolvedValue('/chosen')
      window.pywebview = { api }

      const data = makeNodeData({ tool: makePathTool(), parameters: {} })
      const w = mountPanel(data)

      await w.find('[data-testid="select-file-work_dir"]').trigger('click')
      await flushPromises()

      const [, fileTypes] = api.select_file.mock.calls[0]
      expect(fileTypes).toEqual([])
    })

    it('does not overwrite the parameter when the user cancels the native dialog', async () => {
      const api = mockPywebviewApi()
      api.select_file.mockResolvedValue(null)
      window.pywebview = { api }

      const data = makeNodeData({
        tool: makePathTool(),
        parameters: { input_image: '/existing/path.tif' },
        pinnedInputs: { input_image: true },
      })
      const w = mountPanel(data)

      await w.find('[data-testid="select-file-input_image"]').trigger('click')
      await flushPromises()

      expect(data.parameters.input_image).toBe('/existing/path.tif')
    })

    it('shows the current parameter value in the text input', () => {
      const data = makeNodeData({
        tool: makePathTool(),
        parameters: { input_image: '/preset/image.tif' },
        pinnedInputs: { input_image: true },
      })
      const w = mountPanel(data)
      const input = w
        .find('[data-testid="path-input-input_image"]')
        .find('input')
      expect((input.element as HTMLInputElement).value).toBe('/preset/image.tif')
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

  describe('validation errors', () => {
    it('renders no error banner when validationResult is null', () => {
      const w = mountPanel(makeNodeData())
      expect(
        w.find('[data-testid="node-validation-errors"]').exists(),
      ).toBe(false)
    })

    it('renders error list scoped to the selected node', () => {
      // Mount first (creates pinia), then push a validation result into
      // the shared useGraphSync singleton so NodePanel can see it.
      const w = mountPanel(makeNodeData())
      const { validationResult } = useGraphSync()
      validationResult.value = {
        valid: false,
        node_statuses: {},
        errors: [
          {
            type: 'parameter_invalid',
            detail: "Input is not a valid path",
            node: 'node-1',
            edge_id: null,
            field: 'path',
          },
          {
            // Error on a different node — must be excluded.
            type: 'parameter_invalid',
            detail: 'other',
            node: 'other',
            edge_id: null,
            field: 'x',
          },
        ],
      }
      return w.vm.$nextTick().then(() => {
        const banner = w.find('[data-testid="node-validation-errors"]')
        expect(banner.exists()).toBe(true)
        expect(banner.text()).toContain('path')
        expect(banner.text()).toContain('Input is not a valid path')
        expect(banner.text()).not.toContain('other')
      })
    })

    it('banner disappears once errors are cleared', async () => {
      const w = mountPanel(makeNodeData())
      const { validationResult } = useGraphSync()
      validationResult.value = {
        valid: false,
        node_statuses: {},
        errors: [
          {
            type: 'missing_connection',
            detail: 'nope',
            node: 'node-1',
            edge_id: null,
            field: 'image',
          },
        ],
      }
      await w.vm.$nextTick()
      expect(
        w.find('[data-testid="node-validation-errors"]').exists(),
      ).toBe(true)
      validationResult.value = { valid: true, node_statuses: {}, errors: [] }
      await w.vm.$nextTick()
      expect(
        w.find('[data-testid="node-validation-errors"]').exists(),
      ).toBe(false)
    })
  })
})
