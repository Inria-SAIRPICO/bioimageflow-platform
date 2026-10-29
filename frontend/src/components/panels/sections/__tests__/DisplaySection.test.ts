import { shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it } from 'vitest'
import DisplaySection from '../DisplaySection.vue'
import type { Settings } from '@/stores/settings'

const SelectStub = defineComponent({
  name: 'DisplaySelectStub', props: ['modelValue', 'options'], emits: ['update:modelValue'], template: '<select />',
})

describe('Node Data display preferences', () => {
  it('defaults legacy preferences to pagination and offers continuous scrolling', async () => {
    const settings = { deployment_mode: 'desktop', node_data_page_size: 25 } as Settings
    const wrapper = shallowMount(DisplaySection, { props: { modelValue: settings }, global: { stubs: { Select: SelectStub } } })
    const choices = wrapper.findAllComponents(SelectStub)
    expect(choices[0]!.props('modelValue')).toBe('paginated')
    expect(choices[0]!.props('options')).toEqual([
      { label: 'Paginated', value: 'paginated' },
      { label: 'Continuous scrolling', value: 'continuous' },
    ])
    choices[0]!.vm.$emit('update:modelValue', 'continuous')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('update:field')).toEqual([
      [{ field: 'node_data_browsing_mode', value: 'continuous' }],
    ])
    expect(settings.node_data_page_size).toBe(25)
    expect(wrapper.text()).toContain('paginated mode')
  })
})
