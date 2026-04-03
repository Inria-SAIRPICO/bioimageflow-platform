import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '@/api/client'
import CreateToolDialog from '../CreateToolDialog.vue'

const mockedApi = api as unknown as {
  post: ReturnType<typeof vi.fn>
}

function mountDialog(visible = true) {
  return mount(CreateToolDialog, {
    props: { visible },
    global: {
      plugins: [createPinia()],
      stubs: {
        Dialog: {
          template: '<div><slot /><slot name="footer" /></div>',
          props: ['visible'],
        },
        InputText: {
          template: '<input :data-testid="$attrs[\'data-testid\']" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          props: ['modelValue'],
          emits: ['update:modelValue'],
        },
        Select: {
          template: '<select :data-testid="$attrs[\'data-testid\']"></select>',
          props: ['modelValue'],
        },
        Button: {
          template: '<button :data-testid="$attrs[\'data-testid\']" :disabled="$attrs.disabled" @click="$emit(\'click\')">{{ label }}</button>',
          props: ['label', 'disabled'],
          emits: ['click'],
        },
      },
    },
  })
}

describe('CreateToolDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders name input', () => {
    const wrapper = mountDialog()
    expect(wrapper.find('[data-testid="tool-name-input"]').exists()).toBe(true)
  })

  it('renders type select', () => {
    const wrapper = mountDialog()
    expect(wrapper.find('[data-testid="tool-type-select"]').exists()).toBe(true)
  })

  it('defaults tool type to ProcessingTool', () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as { toolType: string }
    expect(vm.toolType).toBe('ProcessingTool')
  })

  it('create is disabled when name is empty', () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as { createDisabled: boolean }
    expect(vm.createDisabled).toBe(true)
  })

  it('create is enabled when name is provided', async () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as { toolName: string; createDisabled: boolean }
    vm.toolName = 'my_tool'
    await wrapper.vm.$nextTick()
    expect(vm.createDisabled).toBe(false)
  })

  it('onCreate calls POST /api/v1/tools and emits created', async () => {
    mockedApi.post.mockResolvedValueOnce({ data: {} })

    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as {
      toolName: string
      toolType: string
      onCreate: () => Promise<void>
    }
    vm.toolName = 'my_new_tool'
    vm.toolType = 'SourceTool'
    await wrapper.vm.$nextTick()

    await vm.onCreate()

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/tools', {
      name: 'my_new_tool',
      tool_type: 'SourceTool',
    })
    expect(wrapper.emitted('created')).toBeTruthy()
    expect(wrapper.emitted('created')![0]).toEqual(['my_new_tool'])
  })

  it('onCancel emits update:visible with false', async () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as { onCancel: () => void }
    vm.onCancel()

    expect(wrapper.emitted('update:visible')).toBeTruthy()
    expect(wrapper.emitted('update:visible')![0]).toEqual([false])
  })

  it('onCreate resets fields after creation', async () => {
    mockedApi.post.mockResolvedValueOnce({ data: {} })

    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as {
      toolName: string
      toolType: string
      onCreate: () => Promise<void>
    }
    vm.toolName = 'my_tool'
    vm.toolType = 'SinkTool'
    await wrapper.vm.$nextTick()

    await vm.onCreate()

    expect(vm.toolName).toBe('')
    expect(vm.toolType).toBe('ProcessingTool')
  })
})
