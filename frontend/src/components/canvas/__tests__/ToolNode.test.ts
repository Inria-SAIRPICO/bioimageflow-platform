import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import ToolNode from '../ToolNode.vue'
import type { ToolMetadata } from '@/api/types'

vi.mock('@vue-flow/core', () => ({
  Handle: defineComponent({
    name: 'Handle',
    props: ['type', 'position', 'id'],
    template: '<div class="mock-handle" />',
  }),
  Position: { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' },
}))

function makeTool(overrides: Partial<ToolMetadata> = {}): ToolMetadata {
  return {
    name: 'gaussian_blur',
    display_name: 'Gaussian Blur',
    package: 'core',
    package_version: '1.0.0',
    tool_type: 'ImageTool',
    documentation: '',
    tags: [],
    categories: [],
    inputs: {
      image: { type: 'ImagePath', connectable: true },
      sigma: { type: 'float', connectable: false, default: 1.0 },
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

  it('synthesizes a default output pin for DataFrameTool with empty outputs', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      inputs: {},
      outputs: {},
    })
    const data = makeData({ tool })
    const w = factory(data)
    const outputPins = w.findAllComponents({ name: 'OutputPin' })
    expect(outputPins).toHaveLength(1)
    expect(outputPins[0].props('fieldName')).toBe('result')
    expect(outputPins[0].props('fieldType')).toBe('DataFrame')
  })

  it('renders DataFrameTool positional pins', () => {
    const tool = makeTool({
      tool_type: 'DataFrameTool',
      inputs: {
        column: { type: 'str', connectable: true },
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
})
