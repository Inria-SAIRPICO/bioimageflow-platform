import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CodeEditorPanel from '../CodeEditorPanel.vue'
import { useUIStore } from '@/stores/ui'
import { getEditorStatus } from '@/api/editor'
import {
  closeCodeEditorWindow,
  hasCodeEditorWindowBridge,
  isDesktop,
  openCodeEditorWindow,
} from '@/utils/nativeDialogs'

vi.mock('@/api/editor', () => ({
  getEditorStatus: vi.fn(),
}))

vi.mock('@/utils/nativeDialogs', () => ({
  closeCodeEditorWindow: vi.fn(),
  hasCodeEditorWindowBridge: vi.fn(),
  isDesktop: vi.fn(),
  openCodeEditorWindow: vi.fn(),
}))

const mockedGetEditorStatus = vi.mocked(getEditorStatus)
const mockedHasCodeEditorWindowBridge = vi.mocked(hasCodeEditorWindowBridge)
const mockedIsDesktop = vi.mocked(isDesktop)
const mockedOpenCodeEditorWindow = vi.mocked(openCodeEditorWindow)
const mockedCloseCodeEditorWindow = vi.mocked(closeCodeEditorWindow)

describe('CodeEditorPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockedGetEditorStatus.mockResolvedValue({
      available: false,
      url: null,
      version: null,
      control_available: false,
    })
    mockedIsDesktop.mockReturnValue(false)
    mockedHasCodeEditorWindowBridge.mockReturnValue(false)
    mockedOpenCodeEditorWindow.mockResolvedValue(true)
    mockedCloseCodeEditorWindow.mockResolvedValue(true)
  })

  it('shows an unavailable state when no editor URL is present', async () => {
    const wrapper = mount(CodeEditorPanel)
    await flushPromises()

    expect(wrapper.find('[data-testid="code-editor-unavailable"]').exists()).toBe(true)
    expect(mockedGetEditorStatus).toHaveBeenCalledWith({ launch: true })
  })

  it('starts and renders the embedded editor when the panel opens from the menu', async () => {
    mockedGetEditorStatus.mockResolvedValueOnce({
      available: true,
      url: 'http://127.0.0.1:32344',
      version: '4.106.2',
      control_available: true,
    })

    const wrapper = mount(CodeEditorPanel)
    await flushPromises()

    expect(wrapper.find('[data-testid="code-editor-iframe"]').attributes('src')).toBe(
      'http://127.0.0.1:32344',
    )
  })

  it('shows the opening state without checking status during an embedded open request', async () => {
    const store = useUIStore()
    store.setCodeEditorOpening('/tmp/tool.py')

    const wrapper = mount(CodeEditorPanel)
    await flushPromises()

    expect(wrapper.find('[data-testid="code-editor-loading"]').text()).toBe(
      'Opening code editor...',
    )
    expect(wrapper.find('.pi-spinner').exists()).toBe(true)
    expect(mockedGetEditorStatus).not.toHaveBeenCalled()
  })

  it('renders an iframe when the embedded editor is available', () => {
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')

    const wrapper = mount(CodeEditorPanel)

    expect(wrapper.find('[data-testid="code-editor-iframe"]').attributes('src')).toBe(
      'http://127.0.0.1:32344',
    )
  })

  it('switches to unavailable state on iframe error', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')
    const wrapper = mount(CodeEditorPanel)

    await wrapper.find('[data-testid="code-editor-iframe"]').trigger('error')

    expect(wrapper.find('[data-testid="code-editor-unavailable"]').exists()).toBe(true)
  })

  it('shows a pop-out control when the desktop bridge is available', () => {
    mockedHasCodeEditorWindowBridge.mockReturnValue(true)
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')

    const wrapper = mount(CodeEditorPanel)

    expect(wrapper.find('[data-testid="code-editor-popout"]').exists()).toBe(true)
  })

  it('shows pop-out controls in browser mode', () => {
    mockedIsDesktop.mockReturnValue(false)
    mockedHasCodeEditorWindowBridge.mockReturnValue(false)
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')

    const wrapper = mount(CodeEditorPanel)

    expect(wrapper.find('[data-testid="code-editor-popout"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="code-editor-iframe"]').exists()).toBe(true)
  })

  it('hides pop-out controls in desktop mode when the bridge is missing', () => {
    mockedIsDesktop.mockReturnValue(true)
    mockedHasCodeEditorWindowBridge.mockReturnValue(false)
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')

    const wrapper = mount(CodeEditorPanel)

    expect(wrapper.find('[data-testid="code-editor-popout"]').exists()).toBe(false)
  })

  it('pops out to a detached placeholder', async () => {
    mockedHasCodeEditorWindowBridge.mockReturnValue(true)
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')
    const wrapper = mount(CodeEditorPanel)

    await wrapper.find('[data-testid="code-editor-popout"]').trigger('click')
    await flushPromises()

    expect(mockedOpenCodeEditorWindow).toHaveBeenCalledWith(
      'http://127.0.0.1:32344',
      'Code editor - /tmp/tool.py',
    )
    expect(wrapper.find('[data-testid="code-editor-detached"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="code-editor-iframe"]').exists()).toBe(false)
  })

  it('asks the Dockview shell to pop out the panel in browser mode', async () => {
    mockedIsDesktop.mockReturnValue(false)
    mockedHasCodeEditorWindowBridge.mockReturnValue(false)
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')
    const wrapper = mount(CodeEditorPanel)

    await wrapper.find('[data-testid="code-editor-popout"]').trigger('click')

    expect(mockedOpenCodeEditorWindow).not.toHaveBeenCalled()
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({
      type: 'bioimageflow:popout-code-editor',
    }))
    dispatchSpy.mockRestore()
  })

  it('restores the iframe and closes the detached window', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')
    store.setCodeEditorDetached(true)
    const wrapper = mount(CodeEditorPanel)

    await wrapper.find('[data-testid="code-editor-restore"]').trigger('click')
    await flushPromises()

    expect(mockedCloseCodeEditorWindow).toHaveBeenCalledOnce()
    expect(wrapper.find('[data-testid="code-editor-iframe"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="code-editor-detached"]').exists()).toBe(false)
  })

  it('restores the iframe when the native child window is closed manually', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')
    store.setCodeEditorDetached(true)
    const wrapper = mount(CodeEditorPanel)

    window.dispatchEvent(new CustomEvent('bioimageflow:code-editor-window-closed'))
    await flushPromises()

    expect(wrapper.find('[data-testid="code-editor-iframe"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="code-editor-detached"]').exists()).toBe(false)
  })
})
