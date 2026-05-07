import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import SubWorkflowEditorPanel from '../SubWorkflowEditorPanel.vue'

const CanvasStub = defineComponent({
  name: 'CanvasView',
  props: {
    subWorkflowSessionId: {
      type: String,
      default: '',
    },
  },
  template: '<div data-testid="sub-workflow-canvas">{{ subWorkflowSessionId }}</div>',
})

describe('SubWorkflowEditorPanel', () => {
  it('passes Dockview-wrapped session params to the nested canvas', () => {
    const wrapper = mount(SubWorkflowEditorPanel, {
      props: {
        params: {
          params: {
            sessionId: 'parent:sub_1',
          },
        },
      },
      global: {
        stubs: {
          CanvasView: CanvasStub,
        },
      },
    })

    expect(wrapper.find('[data-testid="sub-workflow-canvas"]').text()).toBe('parent:sub_1')
  })

  it('does not render a separate apply/close toolbar', () => {
    const wrapper = mount(SubWorkflowEditorPanel, {
      props: {
        params: {
          params: {
            sessionId: 'parent:sub_1',
          },
        },
      },
      global: {
        stubs: {
          CanvasView: CanvasStub,
        },
      },
    })

    expect(wrapper.text()).not.toContain('Apply')
    expect(wrapper.text()).not.toContain('Close')
  })
})
