import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CodeEditorPanel from '../CodeEditorPanel.vue'
import { useUIStore } from '@/stores/ui'

describe('CodeEditorPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows an unavailable state when no editor URL is present', () => {
    const wrapper = mount(CodeEditorPanel)
    expect(wrapper.find('[data-testid="code-editor-unavailable"]').exists()).toBe(true)
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
