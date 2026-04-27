import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, computed } from 'vue'
import ToolNode from '../ToolNode.vue'
import type { ToolMetadata } from '@/api/types'

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
      image: { type: 'ImagePath', required: true, connectable: 'by_default' },
      sigma: { type: 'float', required: false, connectable: 'never', default: 1.0 },
    },
    outputs: {
      result: { type: 'ImagePath' },
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

function factory(data = makeData()) {
  return mount(ToolNode, {
    props: { id: 'node-1', data } as any,
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

  it('renders output pins for all outputs', () => {
    const w = factory()
    const pins = w.findAllComponents({ name: 'OutputPin' })
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

  it('emits context-menu on right-click', async () => {
    const w = factory()
    await w.find('.tool-node').trigger('contextmenu')
    expect(w.emitted('context-menu')).toBeTruthy()
  })

  it('DataFrameTool with empty outputs and dynamic_outputs=false renders no output pins', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      dynamic_outputs: false,
      inputs: {},
      outputs: {},
    })
    const data = makeData({ tool })
    const w = factory(data)
    const outputPins = w.findAllComponents({ name: 'OutputPin' })
    expect(outputPins).toHaveLength(0)
  })

  it('renders DataFrameTool positional pins', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      inputs: {
        column: { type: 'str', required: true, connectable: 'by_default' },
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

  // --- Category badge ---

  it('shows category badge when categories are present', () => {
    const tool = makeTool({ categories: ['Filtering', 'Enhancement'] })
    const w = factory(makeData({ tool }))
    expect(w.find('.category-badge').exists()).toBe(true)
    expect(w.find('.category-badge').text()).toBe('Filtering')
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
        path: { type: 'Path', required: true, connectable: 'never' },
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
        image: { type: 'ImagePath', required: true, connectable: 'by_default' },
      },
      outputs: {
        result: { type: 'ImagePath' },
      },
    })
    const data = makeData({ tool, connectedInputs: {} })
    const w = factory(data)
    const positionalPins = w
      .findAllComponents({ name: 'InputPin' })
      .filter((p) => p.props('positional') === true)
    expect(positionalPins).toHaveLength(0)
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
    const outputPins = w.findAllComponents({ name: 'OutputPin' })
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
    const outputPins = w.findAllComponents({ name: 'OutputPin' })
    expect(outputPins).toHaveLength(1)
    expect(outputPins[0].props('fieldName')).toBe('sensitivity')
    expect(outputPins[0].props('fieldType')).toBe('any')
    expect(outputPins[0].props('placeholder')).toBe(false)
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
    const outputPins = w.findAllComponents({ name: 'OutputPin' })
    expect(outputPins).toHaveLength(2)
    // First: concrete pin
    expect(outputPins[0].props('fieldName')).toBe('cell_count')
    expect(outputPins[0].props('placeholder')).toBe(false)
    // Second: inherited placeholder
    expect(outputPins[1].props('fieldName')).toBe('(+ inherited columns)')
    expect(outputPins[1].props('placeholder')).toBe(true)
  })
})
