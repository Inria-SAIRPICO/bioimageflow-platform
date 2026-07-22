import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import NodeDataColumnHeader from '../NodeDataColumnHeader.vue'
import type { DataTablePageState } from '@/stores/dataTable'

function state(sortBy: string | null, sortOrder: 'asc' | 'desc' = 'asc'): DataTablePageState {
  return { page: 0, pageSize: 250, sortBy, sortOrder, filters: [] }
}

describe('NodeDataColumnHeader', () => {
  it('cycles unsorted, ascending, descending, and unsorted', async () => {
    const wrapper = mount(NodeDataColumnHeader, {
      props: { column: 'score', label: 'Score', type: 'float', pageState: state(null) },
      global: { plugins: [PrimeVue] },
    })
    const sort = wrapper.get('.node-data-column-header__sort')

    await sort.trigger('click')
    expect(wrapper.emitted('sort')?.slice(-1)[0]).toEqual(['score', 'asc'])

    await wrapper.setProps({ pageState: state('score', 'asc') })
    await sort.trigger('click')
    expect(wrapper.emitted('sort')?.slice(-1)[0]).toEqual(['score', 'desc'])

    await wrapper.setProps({ pageState: state('score', 'desc') })
    await sort.trigger('click')
    expect(wrapper.emitted('sort')?.slice(-1)[0]).toEqual([null, 'asc'])
  })

  it('marks an active column filter', () => {
    const pageState = state(null)
    pageState.filters = [{ column: 'score', operator: 'gte', value: 2 }]
    const wrapper = mount(NodeDataColumnHeader, {
      props: { column: 'score', label: 'Score', type: 'float', pageState },
      global: { plugins: [PrimeVue] },
    })

    expect(wrapper.get('button[aria-label="Filter Score"]').attributes('aria-pressed')).toBe('true')
  })
})
