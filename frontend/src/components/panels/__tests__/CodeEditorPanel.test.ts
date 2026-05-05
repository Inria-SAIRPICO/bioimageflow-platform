import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CodeEditorPanel from '../CodeEditorPanel.vue'
import { useUIStore } from '@/stores/ui'
import { getEditorStatus } from '@/api/editor'

vi.mock('@/api/editor', () => ({
  getEditorStatus: vi.fn(),
}))

const mockedGetEditorStatus = vi.mocked(getEditorStatus)

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
})
