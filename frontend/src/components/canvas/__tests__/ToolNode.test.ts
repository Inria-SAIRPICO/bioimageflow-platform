import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { emptyGraph } from '@/sessions/graphDocument'
import { decodeEndpointHandle } from '@/utils/endpointHandles'
import ToolNode from '../ToolNode.vue'

describe('ToolNode', () => {
  it('renders a workflow node solely from its discriminator and child interface', () => {
    const workflow = emptyGraph('child', 'Child')
    workflow.interface.inputs.push({
      id: 'table-id', name: 'Images', kind: 'dataframe', schema: { type: 'DataFrame' },
      default: null, targets: [],
    })
    workflow.interface.outputs.push({
      id: 'mask-id', name: 'Masks', schema: { type: 'MaskPath' },
      source: { node: 'inner', column: 'mask' },
    })
    const wrapper = mount(ToolNode, {
      props: {
        id: 'workflow',
        data: {
          nodeType: 'workflow', name: 'Child', toolName: '', tool: null,
          status: 'unexecuted', parameters: {}, collapsed: false, enabled: true,
          connectedInputs: {}, pinnedInputs: {}, output_templates: {}, workflow,
        },
      },
      global: { stubs: { InputPin: true, OutputPin: true } },
    })

    expect(wrapper.find('.tool-node').classes()).toContain('workflow-node')
    const input = wrapper.findComponent({ name: 'InputPin' })
    const outputs = wrapper.findAllComponents({ name: 'OutputPin' })
    expect(decodeEndpointHandle(input.props('fieldName'))).toEqual({
      kind: 'workflow-input', id: 'table-id',
    })
    expect(outputs.some(output => {
      const endpoint = decodeEndpointHandle(output.props('fieldName'))
      return endpoint.kind === 'workflow-output' && endpoint.id === 'mask-id'
    })).toBe(true)
  })
})
