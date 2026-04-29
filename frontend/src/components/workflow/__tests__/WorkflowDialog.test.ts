import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import WorkflowDialog from '../WorkflowDialog.vue'

function mountDialog(props = {}) {
  return mount(WorkflowDialog, {
    props: {
      visible: true,
      mode: 'new',
      initialDisplayName: 'My Workflow',
      ...props,
    },
    global: {
      stubs: {
        Dialog: {
          props: ['visible'],
          template: '<div v-if="visible" data-testid="workflow-dialog"><slot name="header" /><slot /><slot name="footer" /></div>',
        },
        Button: {
          props: ['label', 'disabled'],
          template: '<button :disabled="disabled" @click="$emit(\'click\')">{{ label }}</button>',
        },
        InputText: {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
      },
    },
  })
}

describe('WorkflowDialog', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('asks only for the display name and derives the filesystem id', async () => {
    const wrapper = mountDialog()

    expect(wrapper.find('[data-testid="workflow-name-input"]').exists()).toBe(false)
    const input = wrapper.find(
      '[data-testid="workflow-display-name-input"]',
    )
    expect(input.exists()).toBe(true)

    await input.setValue('Cell segmentation v2')
    await wrapper.find('[data-testid="workflow-dialog-submit"]').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('submit')?.[0]?.[0]).toEqual({
      name: 'cell_segmentation_v2',
      display_name: 'Cell segmentation v2',
      description: null,
    })
  })

  it('uses a backend suggested id without changing the display name', async () => {
    const wrapper = mountDialog({
      initialDisplayName: 'Cell segmentation',
      suggestedName: 'cell_segmentation_2',
    })

    await wrapper.find('[data-testid="workflow-dialog-submit"]').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      name: 'cell_segmentation_2',
      display_name: 'Cell segmentation',
    })
  })

  it('disables submit when the display name cannot produce an id', async () => {
    const wrapper = mountDialog({ initialDisplayName: '!!!' })

    expect(wrapper.find('[data-testid="workflow-display-name-error"]').exists()).toBe(true)
    expect(
      wrapper.find('[data-testid="workflow-dialog-submit"]').attributes('disabled'),
    ).toBeDefined()
  })
})
