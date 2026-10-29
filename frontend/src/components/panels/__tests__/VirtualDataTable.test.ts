import { describe, expect, it } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import VirtualDataTable from '../VirtualDataTable.vue'

function props() {
  return {
    columns: [{ id: 'value', label: 'Value', type: 'str' }],
    entries: Array.from({ length: 24 }, (_, index) => ({ index, row: { value: index, tall: false } })),
    totalRows: 24,
    rowHeight: (row: Record<string, any>) => row.tall ? 110 : 40,
    columnStyle: () => ({ width: '120px' }), tableStyle: { width: '120px' }, resetKey: 'query-A',
  }
}

describe('virtual table viewport', () => {
  it('mounts a bounded window and preserves source indices when scrolling', async () => {
    const wrapper = mount(VirtualDataTable, { props: props(), slots: { body: '{{ row.value }}' } })
    await flushPromises()
    expect(wrapper.findAll('tr[data-virtual-index]').length).toBeLessThan(24)
    expect(wrapper.get('[role=grid]').attributes('aria-rowcount')).toBe('25')
    const viewport = wrapper.get('[data-testid="node-data-viewport"]')
    ;(viewport.element as HTMLElement).scrollTop = 400
    await viewport.trigger('scroll')
    expect(wrapper.findAll('tr[data-virtual-index]')[0]!.attributes('data-virtual-index')).toBe('8')
    expect(wrapper.findAll('tr[data-virtual-index]')[0]!.attributes('aria-rowindex')).toBe('10')
    expect(wrapper.emitted('range')!.some(([start]) => start === 8)).toBe(true)
    wrapper.unmount()
  })

  it('keeps a visible row anchor stable when earlier mixed-path row heights become known', async () => {
    const initial = props()
    const wrapper = mount(VirtualDataTable, { props: initial })
    await flushPromises()
    const viewport = wrapper.get('[data-testid="node-data-viewport"]')
    ;(viewport.element as HTMLElement).scrollTop = 400
    await viewport.trigger('scroll')
    await wrapper.setProps({ entries: initial.entries.map(entry => entry.index === 0
      ? { ...entry, row: { ...entry.row, tall: true } } : entry) })
    expect((viewport.element as HTMLElement).scrollTop).toBe(470)
    await wrapper.setProps({ resetKey: 'query-B' })
    await flushPromises()
    expect((viewport.element as HTMLElement).scrollTop).toBe(0)
    wrapper.unmount()
  })
})
