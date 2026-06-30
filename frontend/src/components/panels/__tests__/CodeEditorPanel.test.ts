import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CodeEditorPanel from '../CodeEditorPanel.vue'
import { useUIStore } from '@/stores/ui'
import { getEditorStatus } from '@/api/editor'
import { closeCodeEditorWindow } from '@/utils/nativeDialogs'

vi.mock('@/api/editor', () => ({
  getEditorStatus: vi.fn(),
}))

vi.mock('@/utils/nativeDialogs', () => ({
  closeCodeEditorWindow: vi.fn(),
}))

const mockedGetEditorStatus = vi.mocked(getEditorStatus)
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
    mockedCloseCodeEditorWindow.mockResolvedValue(true)
  })

  it('shows an unavailable state when no editor URL is present', async () => {
    const wrapper = mount(CodeEditorPanel)
    await flushPromises()

    expect(wrapper.find('[data-testid="code-editor-unavailable"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="code-editor-unavailable"]').text()).toContain(
      'code-server is not available. Configure an external editor in Settings.',
    )
    expect(mockedGetEditorStatus).toHaveBeenCalledWith({ launch: true })
  })

  it('shows startup diagnostics when code-server launch fails', async () => {
    mockedGetEditorStatus.mockResolvedValueOnce({
      available: false,
      url: null,
      version: null,
      control_available: false,
      launch_attempted: true,
      error_code: 'embedded_launch_failed',
      error_detail: 'TypeError: bad wetlands api',
    })

    const wrapper = mount(CodeEditorPanel)
    await flushPromises()

    const unavailable = wrapper.find('[data-testid="code-editor-unavailable"]')
    expect(unavailable.text()).toContain('code-server failed to start.')
    expect(unavailable.text()).toContain('Configure an external editor in Settings, or check the server logs.')
    expect(wrapper.find('[data-testid="code-editor-unavailable-detail"]').text()).toBe(
      'TypeError: bad wetlands api',
    )
  })

  it('shows startup diagnostics emitted during an embedded open request', async () => {
    const store = useUIStore()
    store.setCodeEditorOpening('/tmp/tool.py')
    const wrapper = mount(CodeEditorPanel)
    await flushPromises()

    window.dispatchEvent(new CustomEvent('bif:code-editor-diagnostic', {
      detail: {
        path: '/tmp/tool.py',
        error_code: 'embedded_launch_failed',
        error_detail: 'TypeError: bad wetlands api',
      },
    }))
    store.clearCodeEditorOpening('/tmp/tool.py')
    await flushPromises()

    const unavailable = wrapper.find('[data-testid="code-editor-unavailable"]')
    expect(unavailable.text()).toContain('code-server failed to start.')
    expect(wrapper.find('[data-testid="code-editor-unavailable-detail"]').text()).toBe(
      'TypeError: bad wetlands api',
    )
    expect(mockedGetEditorStatus).not.toHaveBeenCalled()
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
