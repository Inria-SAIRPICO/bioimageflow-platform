import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CodeEditorPanel from '../CodeEditorPanel.vue'
import { useUIStore } from '@/stores/ui'
import { getEditorStatus, openEditorPath } from '@/api/editor'
import { closeCodeEditorWindow } from '@/utils/nativeDialogs'

vi.mock('@/api/editor', () => ({
  getEditorStatus: vi.fn(),
  openEditorPath: vi.fn(),
}))

vi.mock('@/utils/nativeDialogs', () => ({
  closeCodeEditorWindow: vi.fn(),
}))

const mockedGetEditorStatus = vi.mocked(getEditorStatus)
const mockedOpenEditorPath = vi.mocked(openEditorPath)
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
    mockedOpenEditorPath.mockResolvedValue({
      opened: true,
      method: 'embedded',
      url: 'http://127.0.0.1:32344',
      path: '/tmp/tool.py',
      message: null,
    })
  })

  it('shows an unavailable state when no editor URL is present', async () => {
    const wrapper = mount(CodeEditorPanel)
    await flushPromises()

    expect(wrapper.find('[data-testid="code-editor-unavailable"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="code-editor-unavailable"]').text()).toContain(
      'code-server is not available. Configure an external editor in Settings.',
    )
    expect(mockedGetEditorStatus).toHaveBeenCalledWith({ launch: true, workspace: true })
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
    expect(mockedGetEditorStatus).toHaveBeenCalledWith()
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

  it('focuses the requested file after a managed workspace iframe loads', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?workspace=%2Ftmp%2Fworkspace%2F.bioimageflow%2FBioImageFlow.code-workspace',
      '/tmp/tool_packages/package/1.0/tool.py',
    )

    const wrapper = mount(CodeEditorPanel)
    await wrapper.find('[data-testid="code-editor-iframe"]').trigger('load')
    await flushPromises()

    expect(mockedOpenEditorPath).toHaveBeenCalledWith(
      '/tmp/tool_packages/package/1.0/tool.py',
    )
  })

  it('shows progress and polls status during an embedded open request', async () => {
    const store = useUIStore()
    store.setCodeEditorOpening('/tmp/tool.py')

    const wrapper = mount(CodeEditorPanel)
    await flushPromises()

    expect(wrapper.find('[data-testid="code-editor-loading-headline"]').text()).toBe(
      'Preparing the code editor',
    )
    expect(wrapper.find('[data-testid="code-editor-loading-detail"]').text()).toBe(
      'First-time setup may take several minutes.',
    )
    expect(wrapper.find('[data-testid="code-editor-progress"]').exists()).toBe(true)
    expect(mockedGetEditorStatus).toHaveBeenCalledWith()
  })

  it('shows extension progress, elapsed time, and opens the Logger panel', async () => {
    vi.useFakeTimers()
    try {
      const store = useUIStore()
      store.setCodeEditorOpening('/tmp/tool.py')
      mockedGetEditorStatus.mockResolvedValue({
        available: false,
        url: null,
        version: null,
        control_available: false,
        launch_phase: 'installing_extensions',
        launch_message: 'Installing Python support.',
        launch_started_at: Date.now() / 1000 - 6,
        launch_current: 2,
        launch_total: 5,
      })

      const wrapper = mount(CodeEditorPanel)
      await flushPromises()

      expect(wrapper.find('[data-testid="code-editor-loading-headline"]').text()).toBe(
        'Installing editor extensions',
      )
      expect(wrapper.find('[data-testid="code-editor-loading-detail"]').text()).toBe(
        'Installing Python support.',
      )
      expect(wrapper.find('[data-testid="code-editor-extension-progress"]').text()).toBe(
        'Extension 2 of 5',
      )
      expect(wrapper.find('[data-testid="code-editor-elapsed"]').text()).toBe('Elapsed: 6s')

      await wrapper.find('[data-testid="code-editor-open-logger"]').trigger('click')
      expect(store.panels.logger).toBe(true)
      expect(store.loggerActivationRequest).toBe(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('polls sequentially and stops when opening finishes', async () => {
    vi.useFakeTimers()
    try {
      const store = useUIStore()
      store.setCodeEditorOpening('/tmp/tool.py')
      const wrapper = mount(CodeEditorPanel)
      await flushPromises()

      expect(mockedGetEditorStatus).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(1000)
      await flushPromises()
      expect(mockedGetEditorStatus).toHaveBeenCalledTimes(2)

      store.clearCodeEditorOpening('/tmp/tool.py')
      await flushPromises()
      await vi.advanceTimersByTimeAsync(2000)
      expect(mockedGetEditorStatus).toHaveBeenCalledTimes(2)
      wrapper.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('keeps the existing iframe mounted while opening another file', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fworkspace',
      '/tmp/workspace/tools/old.py',
    )
    const wrapper = mount(CodeEditorPanel)

    store.setCodeEditorOpening('/tmp/workspace/tools/new.py')
    await flushPromises()

    expect(wrapper.find('[data-testid="code-editor-iframe"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="code-editor-iframe"]').attributes('src')).toBe(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fworkspace',
    )
    expect(wrapper.find('[data-testid="code-editor-loading"]').exists()).toBe(false)
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

  it('keeps the iframe element when the same editor target is set again', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fworkspace',
      '/tmp/workspace/tools/tool.py',
      '/tmp/workspace',
    )
    const wrapper = mount(CodeEditorPanel)
    const iframe = wrapper.find('[data-testid="code-editor-iframe"]')
    const element = iframe.element

    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fworkspace',
      '/tmp/workspace/tools/tool.py',
      '/tmp/workspace',
    )
    await flushPromises()

    expect(wrapper.find('[data-testid="code-editor-iframe"]').element).toBe(element)
    expect(wrapper.find('[data-testid="code-editor-iframe"]').attributes('src')).toBe(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fworkspace',
    )
  })

  it('keeps the iframe element when only the focused file changes', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fworkspace',
      '/tmp/workspace/tools/old.py',
      '/tmp/workspace',
    )
    const wrapper = mount(CodeEditorPanel)
    const iframe = wrapper.find('[data-testid="code-editor-iframe"]')
    const element = iframe.element

    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fworkspace',
      '/tmp/workspace/tools/new.py',
      '/tmp/workspace',
    )
    await flushPromises()

    expect(wrapper.find('[data-testid="code-editor-iframe"]').element).toBe(element)
    expect(wrapper.find('[data-testid="code-editor-iframe"]').attributes('src')).toBe(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fworkspace',
    )
  })

  it('focuses the requested file after a project folder iframe loads', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fworkspace',
      '/tmp/workspace/tools/tool.py',
    )

    const wrapper = mount(CodeEditorPanel)
    await wrapper.find('[data-testid="code-editor-iframe"]').trigger('load')
    await flushPromises()

    expect(mockedOpenEditorPath).toHaveBeenCalledWith('/tmp/workspace/tools/tool.py')
  })

  it('does not focus an old file while a newer editor open is in progress', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fworkspace',
      '/tmp/workspace/tools/old.py',
      '/tmp/workspace',
      1,
    )
    store.setCodeEditorOpening('/tmp/workspace/tools/new.py', 2)

    const wrapper = mount(CodeEditorPanel)
    await wrapper.find('[data-testid="code-editor-iframe"]').trigger('load')
    await flushPromises()

    expect(mockedOpenEditorPath).not.toHaveBeenCalled()
  })

  it('ignores a load event from a previous iframe target', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fold',
      '/tmp/old/tools/old.py',
      '/tmp/old',
      1,
    )
    const wrapper = mount(CodeEditorPanel)
    const oldFrame = wrapper.find('[data-testid="code-editor-iframe"]').element

    store.setCodeEditorTarget(
      'http://127.0.0.1:32344/?folder=%2Ftmp%2Fnew',
      '/tmp/new/tools/new.py',
      '/tmp/new',
      2,
    )
    await flushPromises()

    oldFrame.dispatchEvent(new Event('load'))
    await flushPromises()

    expect(mockedOpenEditorPath).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="code-editor-iframe"]').trigger('load')
    await flushPromises()

    expect(mockedOpenEditorPath).toHaveBeenCalledWith('/tmp/new/tools/new.py')
  })

  it('does not run a follow-up focus request for plain editor URLs', async () => {
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')

    const wrapper = mount(CodeEditorPanel)
    await wrapper.find('[data-testid="code-editor-iframe"]').trigger('load')
    await flushPromises()

    expect(mockedOpenEditorPath).not.toHaveBeenCalled()
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
