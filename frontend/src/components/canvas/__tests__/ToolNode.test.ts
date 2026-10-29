import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { emptyGraph } from '@/sessions/graphDocument'
import { decodeEndpointHandle, encodeEndpointHandle } from '@/utils/endpointHandles'
import ToolNode from '../ToolNode.vue'

describe('ToolNode', () => {
  it('shows a GPU badge for a node-specific effective override', () => {
    const wrapper = mount(ToolNode, {
      props: {
        id: 'gpu-tool',
        data: {
          nodeType: 'tool', name: 'GPU tool', toolName: 'tool', tool: null,
          status: 'unexecuted', parameters: {}, resources: { gpu: 1 }, collapsed: false,
          enabled: true, connectedInputs: {}, pinnedInputs: {}, output_templates: {},
        },
      },
      global: { stubs: { InputPin: true, OutputPin: true } },
    })

    expect(wrapper.get('.gpu-badge').text()).toBe('GPU')
  })

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
  it('honors stable workflow pin visibility and keeps connected pins visible', async () => {
    const workflow = emptyGraph('child', 'Child')
    workflow.interface.inputs = ['hidden', 'constant', 'connected'].map(id => ({
      id, name: id, kind: 'field', schema: { type: 'int' }, default: null, targets: [],
    }))
    const data = {
      nodeType: 'workflow' as const, name: 'Child', toolName: '', tool: null,
      status: 'unexecuted', parameters: {}, collapsed: false, enabled: true,
      connectedInputs: { [encodeEndpointHandle({ kind: 'workflow-input', id: 'connected' })]: 'source.number' },
      pinnedInputs: { hidden: false, constant: true, connected: false }, output_templates: {}, workflow,
      workflowInputPresentation: Object.fromEntries(['hidden', 'constant', 'connected'].map(id => [id, {
        field: { type: 'int', required: false, nullable: false, connectable: 'not_by_default' as const },
        targets: [], metadataAvailable: true, canPin: id !== 'constant',
      }])),
    }
    const wrapper = mount(ToolNode, { props: { id: 'child', data }, global: { stubs: { InputPin: true, OutputPin: true } } })
    let handles = wrapper.findAllComponents({ name: 'InputPin' }).map(pin => decodeEndpointHandle(pin.props('fieldName')))
    expect(handles).toEqual([{ kind: 'workflow-input', id: 'connected' }])
    await wrapper.setProps({ data: { ...data, pinnedInputs: { ...data.pinnedInputs, hidden: true } } })
    handles = wrapper.findAllComponents({ name: 'InputPin' }).map(pin => decodeEndpointHandle(pin.props('fieldName')))
    expect(handles).toEqual([{ kind: 'workflow-input', id: 'hidden' }, { kind: 'workflow-input', id: 'connected' }])
    wrapper.unmount()
  })

})
