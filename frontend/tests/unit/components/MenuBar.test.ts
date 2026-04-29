import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'

vi.mock('@/composables/useGraphSync', () => ({
  useGraphSync: () => ({
    flushNow: vi.fn(),
    validationResult: { value: null },
    isPending: { value: false },
    currentGraph: { value: { nodes: [], edges: [] } },
  }),
}))

import MenuBar from '@/components/layout/MenuBar.vue'
import { useSettingsPanel } from '@/composables/useSettingsPanel'

class _ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
;(globalThis as { ResizeObserver?: typeof _ResizeObserverMock }).ResizeObserver ??=
  _ResizeObserverMock as unknown as typeof _ResizeObserverMock
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = () =>
    ({
      matches: false,
      media: '',
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList
}

describe('MenuBar — Preferences entry', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useSettingsPanel().close()
  })

  it('Edit menu contains a non-disabled Preferences... item', () => {
    const wrapper = mount(MenuBar, {
      global: { plugins: [PrimeVue, ToastService] },
    })
    type MenuItem = { label: string; disabled?: boolean; command?: () => void; items?: MenuItem[] }
    const items = (wrapper.vm as unknown as { menuItems: MenuItem[] }).menuItems
    const edit = items.find((m) => m.label === 'Edit')
    expect(edit).toBeDefined()
    const prefs = edit?.items?.find((m) => m.label === 'Preferences...')
    expect(prefs).toBeDefined()
    expect(prefs?.disabled).not.toBe(true)
    expect(prefs?.command).toBeTypeOf('function')
  })

  it('Preferences... command opens the settings panel', () => {
    const wrapper = mount(MenuBar, {
      global: { plugins: [PrimeVue, ToastService] },
    })
    type MenuItem = { label: string; command?: () => void; items?: MenuItem[] }
    const items = (wrapper.vm as unknown as { menuItems: MenuItem[] }).menuItems
    const edit = items.find((m) => m.label === 'Edit')
    const prefs = edit?.items?.find((m) => m.label === 'Preferences...')

    expect(useSettingsPanel().isOpen.value).toBe(false)
    prefs?.command?.()
    expect(useSettingsPanel().isOpen.value).toBe(true)
  })
})
