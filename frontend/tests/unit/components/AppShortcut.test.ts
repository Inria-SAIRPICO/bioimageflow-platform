import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, defineComponent, h, onBeforeUnmount, onMounted } from 'vue'
import { mount } from '@vue/test-utils'

import * as nativeDialogs from '@/utils/nativeDialogs'
import { useSettingsPanel } from '@/composables/useSettingsPanel'

// We test the keydown wiring in isolation rather than mounting App.vue (which
// pulls in DockviewVue and many stores). The component below replicates the
// exact shortcut logic from App.vue.
const ShortcutHost = defineComponent({
  setup() {
    function isMac(): boolean {
      return /Mac/i.test(navigator.platform)
    }
    function onPreferencesShortcut(event: KeyboardEvent) {
      if (event.key !== ',') return
      const fired =
        (isMac() && event.metaKey) ||
        (!isMac() && nativeDialogs.isDesktop() && event.ctrlKey)
      if (!fired) return
      event.preventDefault()
      useSettingsPanel().open()
    }
    const shortcutEnabled = isMac() || nativeDialogs.isDesktop()
    onMounted(() => {
      if (shortcutEnabled) {
        window.addEventListener('keydown', onPreferencesShortcut)
      }
    })
    onBeforeUnmount(() => {
      if (shortcutEnabled) {
        window.removeEventListener('keydown', onPreferencesShortcut)
      }
    })
    return () => h('div')
  },
})

function setPlatform(value: string) {
  Object.defineProperty(navigator, 'platform', {
    value,
    configurable: true,
  })
}

describe('Preferences keyboard shortcut', () => {
  beforeEach(() => {
    useSettingsPanel().close()
    vi.restoreAllMocks()
  })

  it('Cmd+, opens panel on macOS (browser or pywebview)', () => {
    setPlatform('MacIntel')
    vi.spyOn(nativeDialogs, 'isDesktop').mockReturnValue(false)
    const wrapper = mount(ShortcutHost)
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: ',', metaKey: true }),
    )
    expect(useSettingsPanel().isOpen.value).toBe(true)
    wrapper.unmount()
  })

  it('Ctrl+, opens panel on Linux pywebview', () => {
    setPlatform('Linux x86_64')
    vi.spyOn(nativeDialogs, 'isDesktop').mockReturnValue(true)
    const wrapper = mount(ShortcutHost)
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: ',', ctrlKey: true }),
    )
    expect(useSettingsPanel().isOpen.value).toBe(true)
    wrapper.unmount()
  })

  it('Ctrl+, is ignored in plain browser mode (Linux/Windows)', () => {
    setPlatform('Linux x86_64')
    vi.spyOn(nativeDialogs, 'isDesktop').mockReturnValue(false)
    const wrapper = mount(ShortcutHost)
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: ',', ctrlKey: true }),
    )
    expect(useSettingsPanel().isOpen.value).toBe(false)
    wrapper.unmount()
  })

  it('Other keys are ignored', () => {
    setPlatform('MacIntel')
    vi.spyOn(nativeDialogs, 'isDesktop').mockReturnValue(true)
    const wrapper = mount(ShortcutHost)
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'k', metaKey: true }),
    )
    expect(useSettingsPanel().isOpen.value).toBe(false)
    wrapper.unmount()
  })
})
