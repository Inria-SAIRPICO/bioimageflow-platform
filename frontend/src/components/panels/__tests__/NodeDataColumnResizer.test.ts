import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import NodeDataColumnResizer from '../NodeDataColumnResizer.vue'

describe('NodeDataColumnResizer', () => {
  it('emits every keyboard resize as an independent delta', async () => {
    const wrapper = mount(NodeDataColumnResizer, {
      props: { label: 'number', getWidth: () => 200 },
    })

    await wrapper.trigger('keydown', { key: 'ArrowRight' })
    await wrapper.trigger('keydown', { key: 'ArrowRight' })
    await wrapper.trigger('keydown', { key: 'ArrowLeft' })

    expect(wrapper.emitted('nudge')).toEqual([[10], [10], [-10]])
    expect(wrapper.emitted('resize')).toBeUndefined()
  })
})
