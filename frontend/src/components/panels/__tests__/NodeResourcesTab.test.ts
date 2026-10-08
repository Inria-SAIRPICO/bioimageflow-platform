import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import NodeResourcesTab from '../NodeResourcesTab.vue'
import type { ToolMetadata } from '@/api/types'

const tool = {
  name: 'Segment', display_name: 'Segment', package: 'tests', package_version: '1',
  tool_type: 'ProcessingTool', accepts_upstream: true, dynamic_outputs: false,
  dataframe_output: true, row_consumption: 'mapped', documentation: '', tags: [], categories: [], inputs: {}, outputs: {},
  environment: { resources: { cpu: 2, gpu: 1 } }, source_kind: 'package', editable: false,
} as ToolMetadata

describe('NodeResourcesTab', () => {
  it('disables Reset for canonical inherited resources and retains an explicit zero override', async () => {
    const inherited = { cpu: null, gpu: null, memory: null, gpu_memory: null, max_concurrent: null }
    const wrapper = mount(NodeResourcesTab, {
      props: { resources: inherited, tool },
      global: { plugins: [createPinia(), PrimeVue] },
    })

    expect((wrapper.get('[data-testid="resource-reset-all"]').element as HTMLButtonElement).disabled).toBe(true)
    await wrapper.setProps({ resources: { ...inherited, gpu: 0 } })
    expect((wrapper.get('[data-testid="resource-reset-all"]').element as HTMLButtonElement).disabled).toBe(false)
    await wrapper.get('[data-testid="resource-reset-all"]').trigger('click')
    expect(wrapper.emitted('change')).toEqual([[{}]])
    await wrapper.setProps({ resources: inherited })
    expect((wrapper.get('[data-testid="resource-reset-all"]').element as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows declared, override, and effective resources and emits reset', async () => {
    const wrapper = mount(NodeResourcesTab, {
      props: { resources: { cpu: 4 }, tool },
      global: { plugins: [createPinia(), PrimeVue] },
    })

    expect(wrapper.text()).toContain('Worker resources')
    expect(wrapper.text()).toContain('Local execution uses these values')
    await wrapper.get('[data-testid="resource-reset-all"]').trigger('click')
    expect(wrapper.emitted('change')).toEqual([[{}]])
  })

  it('emits the strict graph resource field names and capacity grammar', async () => {
    const wrapper = mount(NodeResourcesTab, {
      props: { resources: {}, tool },
      global: { plugins: [createPinia(), PrimeVue] },
    })

    await wrapper.get('[data-testid="resource-override-memory"]').setValue('32GB')

    const changes = wrapper.emitted('change') ?? []
    expect(changes[changes.length - 1]).toEqual([{ memory: '32GB' }])
    expect(wrapper.get('[data-testid="resource-override-cpu"] input').attributes('inputmode')).toBe('numeric')
  })
})
