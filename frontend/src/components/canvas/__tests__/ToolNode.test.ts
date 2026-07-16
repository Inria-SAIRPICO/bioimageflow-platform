import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, computed } from 'vue'
import ToolNode from '../ToolNode.vue'
import type { ToolMetadata } from '@/api/types'
import { CANVAS_STATUS_PROJECTION_KEY } from '@/composables/useCanvasStatusProjection'
import type { ProjectedNodeStatus } from '@/sessions/nodeStatusProjection'

vi.mock('@vue-flow/core', () => ({
  Handle: defineComponent({
    name: 'Handle',
    props: ['type', 'position', 'id'],
    template: '<div class="mock-handle vue-flow__handle" />',
  }),
  Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
  useVueFlow: () => ({
    getEdges: computed(() => []),
  }),
}))

function makeTool(overrides: Partial<ToolMetadata> = {}): ToolMetadata {
  return {
    name: 'gaussian_blur',
    display_name: 'Gaussian Blur',
    package: 'core',
    package_version: '1.0.0',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    documentation: '',
    tags: [],
    categories: [],
    inputs: {
      image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' },
      sigma: { type: 'float', required: false, nullable: false, connectable: 'never', default: 1.0 },
    },
    outputs: {
      result: { type: 'ImageFile' },
    },
    environment: null,
    ...overrides,
  }
}

function makeData(overrides: Record<string, unknown> = {}) {
  return {
    name: 'Blur 1',
    toolName: 'gaussian_blur',
    tool: makeTool(),
    status: 'unexecuted',
    parameters: { sigma: 1.0 },
    collapsed: false,
    enabled: true,
    connectedInputs: {} as Record<string, string>,
    pinnedInputs: { image: true } as Record<string, boolean>,
    output_templates: {} as Record<string, string>,
    ...overrides,
  }
}

function factory(
  data = makeData(),
  projectedStatus?: ProjectedNodeStatus,
) {
  const provisional = (data as { provisional?: boolean }).provisional === true
  const status = projectedStatus ?? {
    node_id: 'node-1',
    status: data.enabled === false
      ? 'disabled'
      : data.status as ProjectedNodeStatus['status'],
    cached: false,
    provisional,
    source: provisional ? 'provisional' : 'validation',
  } satisfies ProjectedNodeStatus
  return mount(ToolNode, {
    props: { id: 'node-1', data } as any,
    global: {
      provide: {
        [CANVAS_STATUS_PROJECTION_KEY as symbol]: {
          canvasId: null,
          statuses: computed(() => ({ 'node-1': status })),
          statusForNode: (nodeId: string) => (
            nodeId === 'node-1' ? status : null
          ),
          progressForNode: () => null,
        },
      },
    },
  })
}

describe('ToolNode', () => {
  it('renders node name', () => {
    const w = factory()
    expect(w.find('.node-name').text()).toBe('Blur 1')
  })

  it('renders input pins for connectable inputs only', () => {
    const w = factory()
    // 'image' is connectable, 'sigma' is not
    const pins = w.findAllComponents({ name: 'InputPin' })
    expect(pins).toHaveLength(1)
    expect(pins[0].props('fieldName')).toBe('image')
    expect(pins[0].props('nodeId')).toBe('node-1')
  })

  it('renders a connected body input even when stale pinnedInputs marks it hidden', () => {
    const tool = makeTool({
      inputs: {
        image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' },
        sigma: { type: 'float', required: false, nullable: false, connectable: 'not_by_default', default: 1.0 },
      },
    })
    const w = factory(makeData({
      tool,
      connectedInputs: { sigma: 'Source.sigma' },
      pinnedInputs: { image: true, sigma: false },
    }))

    const pins = w.findAllComponents({ name: 'InputPin' })
    expect(pins.map((pin) => pin.props('fieldName'))).toContain('sigma')
    const sigmaPin = pins.find((pin) => pin.props('fieldName') === 'sigma')!
    expect(sigmaPin.props('connected')).toBe(true)
    expect(sigmaPin.props('sourceLabel')).toBe('Source.sigma')
  })

  it('renders output pins for all outputs', () => {
    const w = factory()
    const pins = w.find('.body-outputs').findAllComponents({ name: 'OutputPin' })
    expect(pins).toHaveLength(1)
    expect(pins[0].props('fieldName')).toBe('result')
  })

  it('applies correct status CSS class', () => {
    const w = factory(makeData({ status: 'executed' }))
    expect(w.find('.tool-node').classes()).toContain('status-executed')
  })

  it('applies status-out-of-date class', () => {
    const w = factory(makeData({ status: 'out_of_date' }))
    expect(w.find('.tool-node').classes()).toContain('status-out-of-date')
  })

  it('applies status-running class', () => {
    const w = factory(makeData({ status: 'running' }))
    expect(w.find('.tool-node').classes()).toContain('status-running')
  })

  it('applies status-failed class', () => {
    const w = factory(makeData({ status: 'failed' }))
    expect(w.find('.tool-node').classes()).toContain('status-failed')
  })

  it('applies disabled class when not enabled', () => {
    const w = factory(makeData({ enabled: false }))
    expect(w.find('.tool-node').classes()).toContain('disabled')
  })

  it('hides body when collapsed', () => {
    const w = factory(makeData({ collapsed: true }))
    const body = w.find('.node-body')
    // v-show sets display:none
    expect(body.isVisible()).toBe(false)
  })

  it('applies provisional class', () => {
    const w = factory(makeData({ provisional: true }))
    expect(w.find('.tool-node').classes()).toContain('provisional')
  })

  it('uses the injected canvas projection instead of mutable node data', () => {
    const w = factory(
      makeData({ status: 'executed', provisional: false }),
      {
        node_id: 'node-1',
        status: 'out_of_date',
        cached: false,
        provisional: true,
        source: 'provisional',
      },
    )

    expect(w.find('.tool-node').classes()).toContain('status-out-of-date')
    expect(w.find('.tool-node').classes()).toContain('provisional')
    expect(w.find('.provisional-indicator').exists()).toBe(true)
  })

  it('emits context-menu on right-click', async () => {
    const w = factory()
    await w.find('.tool-node').trigger('contextmenu')
    expect(w.emitted('context-menu')).toBeTruthy()
  })

  it('renders updated-badge when data.updatedBadge is true', () => {
    const w = factory(makeData({ updatedBadge: true }))
    expect(w.find('.updated-badge').exists()).toBe(true)
  })

  it('hides updated-badge when data.updatedBadge is false', () => {
    const w = factory(makeData({ updatedBadge: false }))
    expect(w.find('.updated-badge').exists()).toBe(false)
  })

  it('hides updated-badge when data.updatedBadge is absent', () => {
    const w = factory(makeData())
    expect(w.find('.updated-badge').exists()).toBe(false)
  })

  it('emits dismiss-badge with the node id when the badge is clicked', async () => {
    const w = factory(makeData({ updatedBadge: true }))
    await w.find('.updated-badge').trigger('click')
    const emitted = w.emitted('dismiss-badge')
    expect(emitted).toBeTruthy()
    expect(emitted![0]).toEqual(['node-1'])
  })

  it('renders missing state from the structured missingTool payload', () => {
    const w = factory(makeData({
      tool: null,
      missingTool: {
        node_id: 'node-1',
        tool_name: 'gaussian_blur',
        installed_versions: [],
      },
    }))
    expect(w.find('.tool-node').classes()).toContain('missing-tool')
    expect(w.find('.missing-tool-badge').text()).toBe('Missing')
  })

  it('renders sub-workflow pins from published inputs and outputs', () => {
    const w = factory(makeData({
      toolName: '__sub_workflow__',
      tool: null,
      published_inputs: [{
        name: 'image',
        internal_node_id: 'load',
        internal_field: 'image',
        kind: 'input',
        schema: { type: 'Path' },
      }],
      published_outputs: [{
        name: 'mask',
        internal_node_id: 'segment',
        internal_output: 'mask',
        schema: { type: 'ImageFile' },
      }],
    }))

    expect(w.find('.tool-node').classes()).toContain('sub-workflow')
    const inputPins = w.find('.body-inputs').findAllComponents({ name: 'InputPin' })
    expect(inputPins).toHaveLength(1)
    expect(inputPins[0].props('fieldName')).toBe('image')
    expect(inputPins[0].props('fieldType')).toBe('Path')
    const outputPins = w.find('.body-outputs').findAllComponents({ name: 'OutputPin' })
    expect(outputPins).toHaveLength(1)
    expect(outputPins[0].props('fieldName')).toBe('mask')
    expect(outputPins[0].props('fieldType')).toBe('ImageFile')
  })

  it('marks readonly sub-workflows without hiding published pins', () => {
    const w = factory(makeData({
      toolName: '__sub_workflow__',
      tool: null,
      published_inputs: [{
        name: 'image',
        internal_node_id: '',
        internal_field: 'image',
        kind: 'input',
        schema: { type: 'Path' },
      }],
      published_outputs: [],
      sub_workflow_readonly_reason: 'Class-based sub-workflow',
    }))

    expect(w.find('.tool-node').classes()).toContain('readonly-sub-workflow')
    expect(w.find('.body-inputs').findAllComponents({ name: 'InputPin' })).toHaveLength(1)
  })

  it('DataFrameTool with empty outputs and dynamic_outputs=false renders no body output pins', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      dynamic_outputs: false,
      inputs: {},
      outputs: {},
    })
    const data = makeData({ tool })
    const w = factory(data)
    // Body outputs should be empty (header still has __dataframe_out)
    const bodyOutputs = w.find('.body-outputs')
    const outputPins = bodyOutputs.findAllComponents({ name: 'OutputPin' })
    expect(outputPins).toHaveLength(0)
  })

  it('renders DataFrameTool positional pins', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      inputs: {
        column: { type: 'str', required: true, nullable: false, connectable: 'by_default' },
      },
    })
    const data = makeData({
      tool,
      connectedInputs: { __positional_0: 'Source.output' },
    })
    const w = factory(data)
    const inputPins = w.findAllComponents({ name: 'InputPin' })
    // 1 connectable (column) + 2 positional (0 connected + 1 spare)
    expect(inputPins).toHaveLength(3)
    const positionalPins = inputPins.filter((p) => p.props('positional') === true)
    expect(positionalPins).toHaveLength(2)
  })

  it('shows GPU badge when environment has gpu resource', () => {
    const tool = makeTool({
      environment: { resources: { gpu: 1 } },
    })
    const w = factory(makeData({ tool }))
    expect(w.find('.gpu-badge').exists()).toBe(true)
    expect(w.find('.gpu-badge').text()).toBe('GPU')
  })

  it('does not show GPU badge without gpu resource', () => {
    const w = factory()
    expect(w.find('.gpu-badge').exists()).toBe(false)
  })

  // --- Header content ---

  it('does not show a category badge when categories are present', () => {
    const tool = makeTool({ categories: ['Filtering', 'Enhancement'] })
    const w = factory(makeData({ tool }))
    expect(w.find('.category-badge').exists()).toBe(false)
  })

  it('does not show category badge when categories are empty', () => {
    const w = factory()
    expect(w.find('.category-badge').exists()).toBe(false)
  })

  // --- Dynamic positional pin compaction ---

  it('shows correct number of positional pins with gaps compacted', () => {
    // After reindexing, __positional_0 and __positional_2 become 0 and 1
    // positionalInputCount = connected count + 1 spare
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      inputs: {},
    })
    const data = makeData({
      tool,
      connectedInputs: {
        __positional_0: 'A.output',
        __positional_1: 'B.output',
      },
    })
    const w = factory(data)
    const positionalPins = w
      .findAllComponents({ name: 'InputPin' })
      .filter((p) => p.props('positional') === true)
    // 2 connected + 1 spare = 3
    expect(positionalPins).toHaveLength(3)
  })

  it('shows single spare pin when no positional inputs connected', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      inputs: {},
    })
    const data = makeData({
      tool,
      connectedInputs: {},
    })
    const w = factory(data)
    const positionalPins = w
      .findAllComponents({ name: 'InputPin' })
      .filter((p) => p.props('positional') === true)
    // 0 connected + 1 spare = 1
    expect(positionalPins).toHaveLength(1)
  })

  // --- Source DataFrameTool (accepts_upstream === false) ---

  it('source DataFrameTool (accepts_upstream=false) renders zero positional pins', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      accepts_upstream: false,
      inputs: {
        path: { type: 'Path', required: true, nullable: false, connectable: 'never' },
      },
      outputs: {
        path: { type: 'Path' },
        filename: { type: 'str' },
      },
    })
    const data = makeData({ tool, connectedInputs: {} })
    const w = factory(data)
    const positionalPins = w
      .findAllComponents({ name: 'InputPin' })
      .filter((p) => p.props('positional') === true)
    expect(positionalPins).toHaveLength(0)
  })

  it('DataFrameTool with accepts_upstream=true renders one spare positional pin', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      accepts_upstream: true,
      inputs: {},
      outputs: {},
    })
    const data = makeData({ tool, connectedInputs: {} })
    const w = factory(data)
    const positionalPins = w
      .findAllComponents({ name: 'InputPin' })
      .filter((p) => p.props('positional') === true)
    expect(positionalPins).toHaveLength(1)
  })

  it('ProcessingTool renders zero positional pins regardless of accepts_upstream', () => {
    const tool = makeTool({
      tool_type: 'ProcessingTool',
      accepts_upstream: true,
      inputs: {
        image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' },
      },
      outputs: {
        result: { type: 'ImageFile' },
      },
    })
    const data = makeData({ tool, connectedInputs: {} })
    const w = factory(data)
    const positionalPins = w
      .findAllComponents({ name: 'InputPin' })
      .filter((p) => p.props('positional') === true)
    expect(positionalPins).toHaveLength(0)
  })

  it('ProcessingTool renders a DataFrame header output pin', () => {
    const tool = makeTool({
      tool_type: 'ProcessingTool',
      dataframe_output: true,
      outputs: {
        result: { type: 'ImageFile' },
      },
    })
    const data = makeData({ tool, connectedInputs: {} })
    const w = factory(data)

    const headerOutputs = w.find('.header-outputs')
    const headerOutPins = headerOutputs.findAllComponents({ name: 'OutputPin' })
    expect(headerOutPins).toHaveLength(1)
    expect(headerOutPins[0].props('fieldName')).toBe('__dataframe_out')
    expect(headerOutPins[0].props('fieldType')).toBe('DataFrame')
    expect(headerOutPins[0].props('variant')).toBe('header')
  })

  // --- Phase 2: dynamic outputs ---

  it('dynamic_outputs=true with no resolved entry renders a placeholder pin', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      dynamic_outputs: true,
      inputs: {},
      outputs: {},
    })
    const data = makeData({ tool, connectedInputs: {} })
    const w = factory(data)
    // Query body-outputs only (excludes header __dataframe_out pin)
    const bodyOutputs = w.find('.body-outputs')
    const outputPins = bodyOutputs.findAllComponents({ name: 'OutputPin' })
    expect(outputPins).toHaveLength(1)
    expect(outputPins[0].props('fieldName')).toBe('...')
    expect(outputPins[0].props('placeholder')).toBe(true)
  })

  it('dynamic_outputs=true with resolved entry renders per-column pins', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      dynamic_outputs: true,
      inputs: {},
      outputs: {},
    })
    const data = makeData({ tool, connectedInputs: {} })
    // Provide resolved outputs via inject
    const resolved = {
      'node-1': {
        resolved: true,
        columns: {
          sensitivity: { type: 'any', default: null, image_spec: null },
        },
      },
    }
    const w = mount(ToolNode, {
      props: { id: 'node-1', data } as any,
      global: {
        provide: {
          'bioimageflow:resolvedOutputs': resolved,
        },
      },
    })
    // Query body-outputs only (excludes header __dataframe_out pin)
    const bodyOutputs = w.find('.body-outputs')
    const outputPins = bodyOutputs.findAllComponents({ name: 'OutputPin' })
    expect(outputPins).toHaveLength(1)
    expect(outputPins[0].props('fieldName')).toBe('sensitivity')
    expect(outputPins[0].props('fieldType')).toBe('any')
    expect(outputPins[0].props('placeholder')).toBe(false)
  })

  // --- Phase 3: Header / Body / Footer layout ---

  describe('Phase 3 layout — header / body / footer', () => {
    it('Source DataFrameTool: header has DataFrame-out only, no header-in, body has per-column outputs', () => {
      const tool = makeTool({
        tool_type: 'DataFrameTool',
        accepts_upstream: false,
        dynamic_outputs: false,
        inputs: {
          path: { type: 'Path', required: true, nullable: false, connectable: 'never' },
        },
        outputs: {
          path: { type: 'Path' },
          filename: { type: 'str' },
        },
      })
      const data = makeData({ tool, connectedInputs: {} })
      const w = factory(data)

      // Header region exists
      expect(w.find('.node-header').exists()).toBe(true)
      // Header has a DataFrame output pin
      const headerOutputs = w.find('.header-outputs')
      expect(headerOutputs.exists()).toBe(true)
      const headerOutPins = headerOutputs.findAllComponents({ name: 'OutputPin' })
      expect(headerOutPins).toHaveLength(1)
      expect(headerOutPins[0].props('fieldName')).toBe('__dataframe_out')
      expect(headerOutPins[0].props('variant')).toBe('header')

      // No header input pins
      const headerInputs = w.find('.header-inputs')
      expect(headerInputs.findAllComponents({ name: 'InputPin' })).toHaveLength(0)

      // Body has per-column output pins
      const bodyOutputs = w.find('.body-outputs')
      const bodyOutPins = bodyOutputs.findAllComponents({ name: 'OutputPin' })
      expect(bodyOutPins).toHaveLength(2)
      expect(bodyOutPins[0].props('fieldName')).toBe('path')
      expect(bodyOutPins[1].props('fieldName')).toBe('filename')
    })

    it('Merge DataFrameTool: header has DataFrame-in (positional, auto-grow) + DataFrame-out, body has per-column outputs', () => {
      const tool = makeTool({
        tool_type: 'DataFrameTool',
        accepts_upstream: true,
        dynamic_outputs: true,
        inputs: {},
        outputs: {},
      })
      const data = makeData({
        tool,
        connectedInputs: { __positional_0: 'Source.output' },
      })
      const resolved = {
        'node-1': {
          resolved: true,
          columns: {
            col_a: { type: 'str' },
            col_b: { type: 'int' },
          },
        },
      }
      const w = mount(ToolNode, {
        props: { id: 'node-1', data } as any,
        global: {
          provide: { 'bioimageflow:resolvedOutputs': resolved },
        },
      })

      // Header has positional input pins
      const headerInputs = w.find('.header-inputs')
      const headerInPins = headerInputs.findAllComponents({ name: 'InputPin' })
      expect(headerInPins.length).toBeGreaterThanOrEqual(2) // 1 connected + 1 spare
      expect(headerInPins[0].props('variant')).toBe('header')

      // Header has DataFrame output
      const headerOutputs = w.find('.header-outputs')
      const headerOutPins = headerOutputs.findAllComponents({ name: 'OutputPin' })
      expect(headerOutPins).toHaveLength(1)
      expect(headerOutPins[0].props('fieldName')).toBe('__dataframe_out')

      // Body has per-column output pins
      const bodyOutputs = w.find('.body-outputs')
      const bodyOutPins = bodyOutputs.findAllComponents({ name: 'OutputPin' })
      expect(bodyOutPins).toHaveLength(2)
    })

    it('Transform DataFrameTool (e.g. FilterRows): same as merge — header pins + body column outputs', () => {
      const tool = makeTool({
        name: 'filter_rows',
        display_name: 'FilterRows',
        tool_type: 'DataFrameTool',
        accepts_upstream: true,
        dynamic_outputs: true,
        inputs: {
          column: { type: 'str', required: true, nullable: false, connectable: 'never' },
        },
        outputs: {},
      })
      const data = makeData({ tool, connectedInputs: {} })
      const w = factory(data)

      // Header has positional pins (1 spare) and DataFrame out
      const headerInputs = w.find('.header-inputs')
      expect(headerInputs.findAllComponents({ name: 'InputPin' })).toHaveLength(1)
      const headerOutputs = w.find('.header-outputs')
      expect(headerOutputs.findAllComponents({ name: 'OutputPin' })).toHaveLength(1)
    })

    it('ProcessingTool: header has DataFrame-out only, body has per-field input + per-output-field output pins', () => {
      const tool = makeTool({
        tool_type: 'ProcessingTool',
        inputs: {
          image: { type: 'ImageFile', required: true, nullable: false, connectable: 'by_default' },
          sigma: { type: 'float', required: false, nullable: false, connectable: 'never', default: 1.0 },
        },
        outputs: {
          result: { type: 'ImageFile' },
        },
      })
      const data = makeData({ tool, connectedInputs: {} })
      const w = factory(data)

      // Header has no positional inputs and one DataFrame output.
      const headerInputs = w.find('.header-inputs')
      expect(headerInputs.findAllComponents({ name: 'InputPin' })).toHaveLength(0)
      const headerOutputs = w.find('.header-outputs')
      const headerOutPins = headerOutputs.findAllComponents({ name: 'OutputPin' })
      expect(headerOutPins).toHaveLength(1)
      expect(headerOutPins[0].props('fieldName')).toBe('__dataframe_out')

      // Body has per-field input pins
      const bodyInputs = w.find('.body-inputs')
      expect(bodyInputs.findAllComponents({ name: 'InputPin' })).toHaveLength(1) // only 'image' is connectable

      // Body has per-field output pins
      const bodyOutputs = w.find('.body-outputs')
      expect(bodyOutputs.findAllComponents({ name: 'OutputPin' })).toHaveLength(1)
    })

    it('status indicator is in the header before the node name and the footer is hidden', () => {
      const tool = makeTool({
        environment: { resources: { gpu: 1 } },
      })
      const w = factory(makeData({ tool }))

      expect(w.find('.node-footer').exists()).toBe(false)
      expect(w.find('.node-header .status-indicator').exists()).toBe(true)
      const status = w.find('.node-header .status-indicator').element
      const name = w.find('.node-header .node-name').element
      expect(status.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })

    it('header has status indicator', () => {
      const w = factory(makeData({ status: 'executed' }))
      expect(w.find('.node-header .status-indicator').exists()).toBe(true)
    })
  })

  it('dynamic_outputs=true with passthrough marker renders concrete pins plus inherited placeholder', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      dynamic_outputs: true,
      inputs: {},
      outputs: {},
    })
    const data = makeData({ tool, connectedInputs: {} })
    const resolved = {
      'node-1': {
        resolved: true,
        columns: {
          _passthrough: true,
          cell_count: { type: 'int', default: null, image_spec: null },
        },
      },
    }
    const w = mount(ToolNode, {
      props: { id: 'node-1', data } as any,
      global: {
        provide: {
          'bioimageflow:resolvedOutputs': resolved,
        },
      },
    })
    // Query body-outputs only (excludes header __dataframe_out pin)
    const bodyOutputs = w.find('.body-outputs')
    const outputPins = bodyOutputs.findAllComponents({ name: 'OutputPin' })
    expect(outputPins).toHaveLength(2)
    // First: concrete pin
    expect(outputPins[0].props('fieldName')).toBe('cell_count')
    expect(outputPins[0].props('placeholder')).toBe(false)
    // Second: inherited placeholder
    expect(outputPins[1].props('fieldName')).toBe('(+ inherited columns)')
    expect(outputPins[1].props('placeholder')).toBe(true)
  })
})
