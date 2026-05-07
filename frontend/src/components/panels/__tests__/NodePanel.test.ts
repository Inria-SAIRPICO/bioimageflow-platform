import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import NodePanel from '../NodePanel.vue'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useLoggerStore } from '@/stores/logger'
import { useGraphSync, _resetGraphSyncForTest } from '@/composables/useGraphSync'
import type { ToolMetadata, InputFieldSchema } from '@/api/types'

function makeTool(overrides: Partial<ToolMetadata> = {}): ToolMetadata {
  return {
    name: 'gaussian_blur',
    display_name: 'Gaussian Blur',
    package: 'bioimageflow-core',
    package_version: '0.3.2',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    documentation: 'Apply gaussian blur to smooth images.',
    tags: [],
    categories: ['Filtering'],
    inputs: {
      image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default', description: 'Input image path' },
      sigma: { type: 'float', required: true, nullable: false, connectable: 'never', default: 1.0, min: 0.1, max: 50.0, step: 0.1, description: 'Blur strength' },
      threshold: { type: 'float', required: false, nullable: true, connectable: 'never', default: 0.5, description: 'Optional threshold' },
    },
    outputs: {
      result: { type: 'ImageFile' },
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

    it('sets parameter to null when toggled via click', async () => {
      const data = makeNodeData()
      data.parameters.threshold = 0.5
      const w = mountPanel(data)
      const noneToggle = w.find('[data-testid="none-toggle"]')
      await noneToggle.trigger('click')
      await w.vm.$nextTick()
      expect(data.parameters.threshold).toBe(null)
    })

    it('toggles between pencil and Ø (pi-ban) icons based on null state', async () => {
      // Icons reflect the action that will happen on click, not the
      // current state — so an editable field shows Ø (click to nullify)
      // and a nulled field shows pencil (click to edit).
      const data = makeNodeData()
      data.parameters.threshold = 0.5
      const w = mountPanel(data)
      const noneToggle = w.find('[data-testid="none-toggle"]')
      // Editable: Ø (pi-ban)
      expect(noneToggle.html()).toContain('pi-ban')
      await noneToggle.trigger('click')
      await w.vm.$nextTick()
      // Nulled: pencil
      expect(noneToggle.html()).toContain('pi-pencil')
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
            type: 'ImageFile',
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

  // --- Fix 18: Always-visible help text ---

  describe('parameter help text', () => {
    it('does not render help toggle buttons for field descriptions', () => {
      const w = mountPanel(makeNodeData())
      const helpToggles = w.findAll('[data-testid="help-toggle"]')
      expect(helpToggles.length).toBe(0)
    })

    it('shows parameter descriptions by default', () => {
      const w = mountPanel(makeNodeData())
      const helpTexts = w.findAll('[data-testid="param-help-text"]')
      expect(helpTexts.length).toBe(3)
      expect(w.text()).toContain('Input image path')
      expect(w.text()).toContain('Blur strength')
      expect(w.text()).toContain('Optional threshold')
    })
  })

  // --- Fix 19: Output template editing ---

  describe('output template editing', () => {
    it('renders editable template inputs for path-typed outputs', () => {
      const w = mountPanel(makeNodeData())
      const templateInputs = w.findAll('[data-testid="output-template"]')
      // Both result (ImageFile) and mask (MaskPath) are path-typed
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

  describe('sub-workflow publishing controls', () => {
    it('shows publishing controls for a normal workflow context and only publishes connectable inputs', async () => {
      const data = makeNodeData({
        publicationContext: {
          published_inputs: [],
          published_outputs: [],
        },
      })
      const w = mountPanel(data)

      const inputButtons = w.findAll('[data-testid="publish-input-toggle"]')
      expect(inputButtons).toHaveLength(1)
      expect(w.find('[data-testid="publish-output-toggle-result"]').exists()).toBe(true)
      expect(w.find('[data-testid="publish-output-toggle-mask"]').exists()).toBe(true)

      await inputButtons[0].trigger('click')
      await w.vm.$nextTick()

      expect((data as any).publicationContext.published_inputs).toEqual([
        expect.objectContaining({
          name: 'node-1.image',
          internal_node_id: 'node-1',
          internal_field: 'image',
          kind: 'input',
        }),
      ])
      expect((data as any).publicationContext.published_inputs[0].schema)
        .toStrictEqual(data.tool.inputs.image)
      expect(w.find('[data-testid="published-input-name-image"]').exists()).toBe(true)
      expect(w.find('[data-testid="published-input-name-sigma"]').exists()).toBe(false)
    })

    it('publishes and unpublishes an internal parameter with a stable default name', async () => {
      const data = makeNodeData({
        subWorkflowContext: {
          parentNodeId: 'sub_1',
          published_inputs: [],
          published_outputs: [],
        },
      })
      const w = mountPanel(data)

      const buttons = w.findAll('[data-testid="publish-input-toggle"]')
      const imageButton = buttons[0]
      await imageButton.trigger('click')
      await w.vm.$nextTick()

      expect((data as any).subWorkflowContext.published_inputs).toEqual([
        expect.objectContaining({
          name: 'node-1.image',
          internal_node_id: 'node-1',
          internal_field: 'image',
          kind: 'input',
          schema: data.tool.inputs.image,
          default: null,
        }),
      ])
      expect(w.find('[data-testid="published-input-name-image"]').exists()).toBe(true)

      await imageButton.trigger('click')
      expect((data as any).subWorkflowContext.published_inputs).toEqual([])
    })

    it('prevents publishing an output with a name already used by an input', async () => {
      const data = makeNodeData({
        subWorkflowContext: {
          parentNodeId: 'sub_1',
          published_inputs: [{
            name: 'node-1.result',
            internal_node_id: 'node-1',
            internal_field: 'sigma',
            kind: 'parameter',
            schema: {},
            default: 1.0,
          }],
          published_outputs: [],
        },
      })
      const w = mountPanel(data)

      await w.find('[data-testid="publish-output-toggle-result"]').trigger('click')

      expect((data as any).subWorkflowContext.published_outputs).toEqual([])
      expect(w.find('[data-testid="publish-name-error"]').text()).toContain('already used')
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
          input_image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default', description: 'Image file' },
          work_dir: { type: 'Path', required: true, nullable: false, connectable: 'never', description: 'Working directory' },
        },
        outputs: { result: { type: 'ImageFile' } },
      })
    }

    it('renders a text input and file button for ImageFile (non-optional, no default)', () => {
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

    it('renders only a file button for ImageFile (no folder button)', () => {
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

    it('passes image extensions to the native dialog for ImageFile fields', async () => {
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

  describe('execution output', () => {
    it('renders failed-node error and traceback from execution state', async () => {
      const w = mountPanel(makeNodeData())
      useExecutionStore().applyNodeState({
        node_id: 'node-1',
        status: 'failed',
        cached: false,
        error: 'Node failed',
        traceback: 'Traceback line 1\nTraceback line 2',
      })
      await w.vm.$nextTick()

      const error = w.find('[data-testid="node-runtime-error"]')
      expect(error.exists()).toBe(true)
      expect(error.text()).toContain('Node failed')
      expect(error.text()).toContain('Traceback line 2')
    })

    it('renders selected-node logs and hides other nodes', async () => {
      const w = mountPanel(makeNodeData())
      const logger = useLoggerStore()
      logger.addEntry({ level: 'INFO', message: 'selected log', nodeId: 'node-1', timestamp: 1 })
      logger.addEntry({ level: 'INFO', message: 'other log', nodeId: 'node-2', timestamp: 2 })
      await w.vm.$nextTick()

      const list = w.find('[data-testid="node-log-list"]')
      expect(list.text()).toContain('selected log')
      expect(list.text()).not.toContain('other log')
    })

    it('filters selected-node logs independently by level', async () => {
      const w = mountPanel(makeNodeData())
      const logger = useLoggerStore()
      logger.addEntry({ level: 'DEBUG', message: 'debug log', nodeId: 'node-1', timestamp: 1 })
      logger.addEntry({ level: 'ERROR', message: 'error log', nodeId: 'node-1', timestamp: 2 })
      await w.vm.$nextTick()

      expect(w.find('[data-testid="node-log-list"]').text()).toContain('error log')
      expect(w.find('[data-testid="node-log-list"]').text()).not.toContain('debug log')

      await w.find('[data-testid="node-log-level-DEBUG"]').trigger('click')
      expect(w.find('[data-testid="node-log-list"]').text()).toContain('debug log')
    })

    it('renders node log messages as escaped text', async () => {
      const w = mountPanel(makeNodeData())
      useLoggerStore().addEntry({
        level: 'INFO',
        message: '<script>alert(1)</script>',
        nodeId: 'node-1',
        timestamp: 1,
      })
      await w.vm.$nextTick()

      const message = w.find('[data-testid="node-log-message"]')
      expect(message.text()).toBe('<script>alert(1)</script>')
      expect(w.find('script').exists()).toBe(false)
    })
  })
})
