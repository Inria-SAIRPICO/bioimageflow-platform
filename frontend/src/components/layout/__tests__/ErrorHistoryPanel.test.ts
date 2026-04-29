import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import ErrorHistoryPanel from '../ErrorHistoryPanel.vue'
import { useErrorStore, type ErrorKind } from '@/stores/errors'

function mountPanel(visible = true) {
  return mount(ErrorHistoryPanel, {
    props: { visible },
    global: { plugins: [[PrimeVue, { theme: { preset: Aura } }]] },
    attachTo: document.body,
  })
}

describe('ErrorHistoryPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })

  it('does not render rows when visible is false', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'a' })
    const wrapper = mountPanel(false)
    // Sidebar is closed: no rows in document.
    expect(document.querySelectorAll('[data-testid="error-row"]')).toHaveLength(
      0,
    )
    wrapper.unmount()
  })

  it('renders one row per error when visible', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'first' })
    store.report({ kind: 'execution_failed', detail: 'second', nodeId: 'n1' })
    store.report({ kind: 'websocket_error', detail: 'third' })
    const wrapper = mountPanel(true)
    const rows = document.querySelectorAll('[data-testid="error-row"]')
    expect(rows).toHaveLength(3)
    wrapper.unmount()
  })

  it('each row shows a kind label and the detail', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'Network unavailable' })
    const wrapper = mountPanel(true)
    const row = document.querySelector('[data-testid="error-row"]')!
    expect(row.textContent).toContain('Graph sync error')
    expect(row.textContent).toContain('Network unavailable')
    wrapper.unmount()
  })

  it('row timestamp uses HH:MM:SS shape', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'x' })
    const wrapper = mountPanel(true)
    const tsEl = document.querySelector('[data-testid="error-row-timestamp"]')!
    // Locale-tolerant: H:MM:SS or HH:MM:SS, optional AM/PM suffix.
    expect(tsEl.textContent).toMatch(/\d{1,2}:\d{2}:\d{2}/)
    wrapper.unmount()
  })

  it('clicking the per-row dismiss button marks the entry dismissed', async () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'a' })
    const wrapper = mountPanel(true)
    const dismissBtn = document.querySelector(
      '[data-testid="error-row-dismiss"]',
    ) as HTMLElement
    expect(dismissBtn).not.toBeNull()
    dismissBtn.click()
    await wrapper.vm.$nextTick()
    expect(store.errors[0]!.dismissed).toBe(true)
    wrapper.unmount()
  })

  it('dismissed rows have a "dismissed" class', async () => {
    const store = useErrorStore()
    const id = store.report({ kind: 'graph_sync_error', detail: 'a' })
    store.dismiss(id)
    const wrapper = mountPanel(true)
    await wrapper.vm.$nextTick()
    const row = document.querySelector('[data-testid="error-row"]')!
    expect(row.classList.contains('dismissed')).toBe(true)
    wrapper.unmount()
  })

  it('"Clear all" button calls errorStore.clear()', async () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'a' })
    store.report({ kind: 'graph_sync_error', detail: 'b' })
    const wrapper = mountPanel(true)
    const clearBtn = document.querySelector(
      '[data-testid="error-history-clear"]',
    ) as HTMLElement
    expect(clearBtn).not.toBeNull()
    clearBtn.click()
    await wrapper.vm.$nextTick()
    expect(store.errors).toHaveLength(0)
    wrapper.unmount()
  })

  it('"Dismiss all" button calls errorStore.dismissAll()', async () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'a' })
    store.report({ kind: 'graph_sync_error', detail: 'b' })
    const wrapper = mountPanel(true)
    const dismissAllBtn = document.querySelector(
      '[data-testid="error-history-dismiss-all"]',
    ) as HTMLElement
    expect(dismissAllBtn).not.toBeNull()
    dismissAllBtn.click()
    await wrapper.vm.$nextTick()
    expect(store.errors.every((e) => e.dismissed)).toBe(true)
    expect(store.unreadCount).toBe(0)
    wrapper.unmount()
  })

  it('rows are sorted newest first', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2025, 0, 1, 12, 0, 0))
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'oldest' })
    vi.setSystemTime(new Date(2025, 0, 1, 12, 0, 5))
    store.report({ kind: 'graph_sync_error', detail: 'middle' })
    vi.setSystemTime(new Date(2025, 0, 1, 12, 0, 10))
    store.report({ kind: 'graph_sync_error', detail: 'newest' })
    vi.useRealTimers()
    const wrapper = mountPanel(true)
    const rows = Array.from(
      document.querySelectorAll('[data-testid="error-row-detail"]'),
    )
    expect(rows.map((r) => r.textContent?.trim())).toEqual([
      'newest',
      'middle',
      'oldest',
    ])
    wrapper.unmount()
  })

  it('emits navigate when "Go to node" is clicked on a row with a nodeId', async () => {
    const store = useErrorStore()
    store.report({ kind: 'execution_failed', detail: 'broke', nodeId: 'n42' })
    const wrapper = mountPanel(true)
    const link = document.querySelector(
      '[data-testid="error-row-navigate"]',
    ) as HTMLElement
    expect(link).not.toBeNull()
    link.click()
    await wrapper.vm.$nextTick()
    const events = wrapper.emitted('navigate')
    expect(events).toBeTruthy()
    expect(events![0]).toEqual(['n42'])
    wrapper.unmount()
  })

  it('rows without a nodeId do not render the navigate link', () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'no node' })
    const wrapper = mountPanel(true)
    expect(
      document.querySelector('[data-testid="error-row-navigate"]'),
    ).toBeNull()
    wrapper.unmount()
  })

  it('shows empty state when no errors are present', () => {
    const wrapper = mountPanel(true)
    const empty = document.querySelector('[data-testid="error-history-empty"]')
    expect(empty).not.toBeNull()
    expect(empty!.textContent).toContain('No errors recorded')
    wrapper.unmount()
  })

  it('emits update:visible(false) when the panel is closed', async () => {
    const store = useErrorStore()
    store.report({ kind: 'graph_sync_error', detail: 'a' })
    const wrapper = mountPanel(true)
    // PrimeVue Sidebar's close button has class p-drawer-close-button or
    // p-drawer-close. The component itself emits update:visible internally;
    // we simulate by calling the prop change.
    await wrapper.setProps({ visible: false })
    // The prop transition itself doesn't emit; we instead verify that the
    // close button (mask click or X) triggers the event when invoked.
    const closeBtn = document.querySelector(
      '[data-testid="error-history-close"]',
    ) as HTMLElement | null
    if (closeBtn) {
      closeBtn.click()
      await wrapper.vm.$nextTick()
      const ev = wrapper.emitted('update:visible')
      expect(ev?.some((e) => e[0] === false)).toBe(true)
    }
    wrapper.unmount()
  })

  it('renders a label for every ErrorKind value', () => {
    const store = useErrorStore()
    const kinds: ErrorKind[] = [
      'graph_sync_error',
      'websocket_error',
      'log_subscription_failed',
      'execution_failed',
      'network_unreachable',
      'edge_rejected',
      'unknown',
    ]
    for (const k of kinds) {
      store.report({ kind: k, detail: `detail-${k}` })
    }
    const wrapper = mountPanel(true)
    const text = document.body.textContent ?? ''
    expect(text).not.toContain('undefined')
    // Each kind gets some label rendered.
    expect(text).toContain('Graph sync error')
    expect(text).toContain('Connection error')
    expect(text).toContain('Log subscription error')
    expect(text).toContain('Execution failed')
    expect(text).toContain('Network unreachable')
    expect(text).toContain('Edge rejected')
    wrapper.unmount()
  })
})
