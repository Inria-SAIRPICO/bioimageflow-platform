import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import NestedWorkflowEditorPanel from '../NestedWorkflowEditorPanel.vue'

const CanvasStub = defineComponent({
  name: 'CanvasView',
  props: {
    nestedWorkflowSessionId: {
      type: String,
      default: '',
    },
    parentCanvasPanelId: {
      type: String,
      default: '',
    },
  },
  template: '<div data-testid="nested-workflow-canvas">{{ nestedWorkflowSessionId }}|{{ parentCanvasPanelId }}</div>',
})

describe('NestedWorkflowEditorPanel', () => {
  it('passes Dockview-wrapped session params to the nested canvas', () => {
    const wrapper = mount(NestedWorkflowEditorPanel, {
      props: {
        params: {
          params: {
            sessionId: 'parent:sub_1',
            parentCanvasPanelId: 'workflow:parent',
          },
        },
      },
      global: {
        stubs: {
          CanvasView: CanvasStub,
        },
      },
    })

    expect(wrapper.find('[data-testid="nested-workflow-canvas"]').text()).toBe(
      'parent:sub_1|workflow:parent',
    )
  })

  it('does not render a separate apply/close toolbar', () => {
    const wrapper = mount(NestedWorkflowEditorPanel, {
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
