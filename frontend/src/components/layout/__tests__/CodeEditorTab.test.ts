import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CodeEditorTab from '../CodeEditorTab.vue'
import { useUIStore } from '@/stores/ui'
import type { DockviewApi, DockviewPanelApi, IDockviewPanel } from 'dockview-core'
import {
  closeCodeEditorWindow,
  hasCodeEditorWindowBridge,
  isDesktop,
  openCodeEditorWindow,
} from '@/utils/nativeDialogs'

vi.mock('@/utils/nativeDialogs', () => ({
  closeCodeEditorWindow: vi.fn(),
  hasCodeEditorWindowBridge: vi.fn(),
  isDesktop: vi.fn(),
  openCodeEditorWindow: vi.fn(),
}))

const mockedCloseCodeEditorWindow = vi.mocked(closeCodeEditorWindow)
const mockedHasCodeEditorWindowBridge = vi.mocked(hasCodeEditorWindowBridge)
const mockedIsDesktop = vi.mocked(isDesktop)
const mockedOpenCodeEditorWindow = vi.mocked(openCodeEditorWindow)

function createTabParams(location: any = { type: 'grid' }) {
  const panel = { id: 'codeEditor' }
  const api = {
    id: 'codeEditor',
    title: 'Code Editor',
    location,
    close: vi.fn(),
    onDidTitleChange: vi.fn(() => ({ dispose: vi.fn() })),
    onDidLocationChange: vi.fn(() => ({ dispose: vi.fn() })),
  }
  const containerApi = {
    addPopoutGroup: vi.fn().mockResolvedValue(true),
    getPanel: vi.fn(() => panel),
  }
  return {
    api: api as unknown as DockviewPanelApi,
    containerApi: containerApi as unknown as DockviewApi,
    panel: panel as unknown as IDockviewPanel,
    mocks: { api, containerApi },
  }
}

describe('CodeEditorTab', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockedIsDesktop.mockReturnValue(false)
    mockedHasCodeEditorWindowBridge.mockReturnValue(false)
    mockedOpenCodeEditorWindow.mockResolvedValue(true)
    mockedCloseCodeEditorWindow.mockResolvedValue(true)
  })

  it('opens the Code Editor panel through Dockview in browser mode', async () => {
    const params = createTabParams()
    useUIStore().setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')
    const wrapper = mount(CodeEditorTab, { props: { params } })

    await wrapper.find('[data-testid="code-editor-tab-window-toggle"]').trigger('click')
    await flushPromises()

    expect(params.mocks.containerApi.addPopoutGroup).toHaveBeenCalledWith(
      params.panel,
      { popoutUrl: '/popout.html' },
    )
    expect(mockedOpenCodeEditorWindow).not.toHaveBeenCalled()
  })

  it('closes the Dockview popout window instead of opening another one', async () => {
    const close = vi.fn()
    const params = createTabParams({ type: 'popout', getWindow: () => ({ close }) })
    useUIStore().setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')
    const wrapper = mount(CodeEditorTab, { props: { params } })

    await wrapper.find('[data-testid="code-editor-tab-window-toggle"]').trigger('click')

    expect(close).toHaveBeenCalledOnce()
    expect(params.mocks.containerApi.addPopoutGroup).not.toHaveBeenCalled()
  })

  it('uses the pywebview bridge in desktop mode and then closes that window', async () => {
    mockedIsDesktop.mockReturnValue(true)
    mockedHasCodeEditorWindowBridge.mockReturnValue(true)
    const store = useUIStore()
    store.setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')
    const wrapper = mount(CodeEditorTab, { props: { params: createTabParams() } })

    await wrapper.find('[data-testid="code-editor-tab-window-toggle"]').trigger('click')
    await flushPromises()

    expect(mockedOpenCodeEditorWindow).toHaveBeenCalledWith(
      'http://127.0.0.1:32344',
      'Code editor - /tmp/tool.py',
    )
    expect(store.codeEditorDetached).toBe(true)

    await wrapper.find('[data-testid="code-editor-tab-window-toggle"]').trigger('click')
    await flushPromises()

    expect(mockedCloseCodeEditorWindow).toHaveBeenCalledOnce()
    expect(store.codeEditorDetached).toBe(false)
  })

  it('hides the window toggle in desktop mode when the bridge is missing', () => {
    mockedIsDesktop.mockReturnValue(true)
    mockedHasCodeEditorWindowBridge.mockReturnValue(false)
    useUIStore().setCodeEditorTarget('http://127.0.0.1:32344', '/tmp/tool.py')

    const wrapper = mount(CodeEditorTab, { props: { params: createTabParams() } })

    expect(wrapper.find('[data-testid="code-editor-tab-window-toggle"]').exists()).toBe(false)
  })

  it('keeps the close-tab action available', async () => {
    const params = createTabParams()
    const wrapper = mount(CodeEditorTab, { props: { params } })

    await wrapper.find('[data-testid="code-editor-tab-close"]').trigger('click')

    expect(params.mocks.api.close).toHaveBeenCalledOnce()
  })
})
