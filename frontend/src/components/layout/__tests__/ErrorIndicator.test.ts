import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ErrorIndicator from '../ErrorIndicator.vue'
import { useErrorStore } from '@/stores/errors'

describe('ErrorIndicator', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('does not render anything when there are no errors at all', () => {
    const wrapper = mount(ErrorIndicator)
    expect(wrapper.find('.error-indicator').exists()).toBe(false)
  })

  it('renders the bell icon when unreadCount > 0', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'down' })
    const wrapper = mount(ErrorIndicator)
    expect(wrapper.find('.error-indicator').exists()).toBe(true)
    expect(wrapper.find('.pi-exclamation-circle').exists()).toBe(true)
  })

  it('shows the unread count badge with the actual count', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'a' })
    store.report({ kind: 'graph_sync_error', detail: 'b' })
    store.report({ kind: 'graph_sync_error', detail: 'c' })
    const wrapper = mount(ErrorIndicator)
    expect(wrapper.find('.unread-badge').text()).toBe('3')
  })

  it('badge text is "9+" when unreadCount > 9', () => {
    const store = useErrorStore()
    for (let i = 0; i < 25; i += 1) {
      store.report({ kind: 'graph_sync_error', detail: String(i) })
    }
    const wrapper = mount(ErrorIndicator)
    expect(wrapper.find('.unread-badge').text()).toBe('9+')
  })

  it('emits "open" when the indicator is clicked', async () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'x' })
    const wrapper = mount(ErrorIndicator)
    await wrapper.find('.error-indicator').trigger('click')
    expect(wrapper.emitted('open')).toBeTruthy()
    expect(wrapper.emitted('open')!).toHaveLength(1)
  })

  it('renders without unread badge when all errors are acknowledged', () => {
    const store = useErrorStore()
    const id = store.report({ kind: 'graph_sync_error', detail: 'a' })
    store.toggleAcknowledged(id)
    const wrapper = mount(ErrorIndicator)
    // Indicator is still visible (history accessible) but no badge.
    expect(wrapper.find('.error-indicator').exists()).toBe(true)
    expect(wrapper.find('.unread-badge').exists()).toBe(false)
  })

  it('icon receives data-state="unread" when there are unread errors', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'a' })
    const wrapper = mount(ErrorIndicator)
    expect(wrapper.find('.error-indicator').attributes('data-state')).toBe(
      'unread',
    )
  })

  it('icon receives data-state="acknowledged" when only acknowledged entries remain', () => {
    const store = useErrorStore()
    const id = store.report({ kind: 'graph_sync_error', detail: 'a' })
    store.toggleAcknowledged(id)
    const wrapper = mount(ErrorIndicator)
    expect(wrapper.find('.error-indicator').attributes('data-state')).toBe(
      'acknowledged',
    )
  })

  it('tooltip text is "Errors (N)" when unread > 0, else "Error history"', () => {
    const store = useErrorStore()
    const id = store.report({ kind: 'graph_sync_error', detail: 'a' })
    store.report({ kind: 'graph_sync_error', detail: 'b' })
    let wrapper = mount(ErrorIndicator)
    expect(wrapper.find('.error-indicator').attributes('title')).toBe(
      'Errors (2)',
    )
    store.toggleAcknowledged(id)
    store.toggleAcknowledged(store.errors[1]!.id)
    wrapper = mount(ErrorIndicator)
    expect(wrapper.find('.error-indicator').attributes('title')).toBe(
      'Error history',
    )
  })
})
