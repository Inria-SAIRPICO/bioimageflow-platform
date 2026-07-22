import { beforeAll, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import InputNumber from 'primevue/inputnumber'
import NodeDataPaginator from '../NodeDataPaginator.vue'

beforeAll(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })))
})

function mountPaginator(overrides = {}) {
  return mount(NodeDataPaginator, {
    props: {
      page: 0,
      pageSize: 25,
      totalRows: 250,
      unfilteredTotalRows: 400,
      ...overrides,
    },
    global: { plugins: [PrimeVue] },
  })
}

describe('NodeDataPaginator', () => {
  it('reports filtered and unfiltered ranges and exposes direct navigation', async () => {
    const wrapper = mountPaginator()

    expect(wrapper.text()).toContain('1–25 of 250')
    expect(wrapper.text()).toContain('400 unfiltered')
    expect(wrapper.text()).toContain('Page')
    expect(wrapper.text()).toContain('of 10')

    await wrapper.get('button[aria-label="Next page"]').trigger('click')
    expect(wrapper.emitted('page')).toEqual([[1]])
  })

  it('navigates directly to a typed page on Enter', async () => {
    const wrapper = mountPaginator()
    wrapper.findComponent(InputNumber).vm.$emit('input', { value: 7 })
    await wrapper.vm.$nextTick()
    await wrapper.get('[data-testid="node-data-page-input"] input').trigger('keydown.enter')

    expect(wrapper.emitted('page')).toEqual([[6]])
  })

  it('disables navigation for empty results', () => {
    const wrapper = mountPaginator({ totalRows: 0, unfilteredTotalRows: 0 })

    expect(wrapper.text()).toContain('0–0 of 0')
    expect(wrapper.get('button[aria-label="Next page"]').attributes('disabled')).toBeDefined()
  })
})
