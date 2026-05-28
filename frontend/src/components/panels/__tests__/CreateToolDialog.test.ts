import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '@/api/client'
import CreateToolDialog from '../CreateToolDialog.vue'

const mockedApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
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
          props: ['modelValue', 'options', 'optionLabel', 'optionValue'],
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
    mockedApi.get.mockResolvedValue({ data: [] })
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

  it('create is enabled when a class name can be derived from the provided name', async () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as {
      toolName: string
      toolClassName: string
      createDisabled: boolean
    }
    vm.toolName = 'my custom tool'
    await wrapper.vm.$nextTick()
    expect(vm.toolClassName).toBe('MyCustomTool')
    expect(vm.createDisabled).toBe(false)
  })

  it('create is disabled for names that cannot safely map to a tool class', async () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as { toolName: string; createDisabled: boolean }
    vm.toolName = '!!!'
    await wrapper.vm.$nextTick()
    expect(vm.createDisabled).toBe(true)

    vm.toolName = '../BadTool'
    await wrapper.vm.$nextTick()
    expect(vm.createDisabled).toBe(true)
  })

  it('onCreate calls POST /api/v1/tools and emits created', async () => {
    mockedApi.post.mockResolvedValueOnce({
      data: {
        name: 'MyNewTool',
        tool_type: 'DataFrameTool',
        path: '/tmp/my_new_tool.py',
        source_kind: 'custom',
        editable: true,
      },
    })

    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as {
      toolName: string
      toolType: string
      onCreate: () => Promise<void>
    }
    vm.toolName = 'my new tool'
    vm.toolType = 'DataFrameTool'
    await wrapper.vm.$nextTick()

    await vm.onCreate()

    expect(mockedApi.post).toHaveBeenCalledWith('/api/v1/tools', {
      name: 'MyNewTool',
      tool_type: 'DataFrameTool',
    })
    expect(wrapper.emitted('created')).toBeTruthy()
    expect(wrapper.emitted('created')![0]).toEqual([
      expect.objectContaining({
        name: 'MyNewTool',
        path: '/tmp/my_new_tool.py',
      }),
    ])
  })

  it('onCancel emits update:visible with false', async () => {
    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as { onCancel: () => void }
    vm.onCancel()

    expect(wrapper.emitted('update:visible')).toBeTruthy()
    expect(wrapper.emitted('update:visible')![0]).toEqual([false])
  })

  it('onCreate resets fields after creation', async () => {
    mockedApi.post.mockResolvedValueOnce({
      data: {
        name: 'MyTool',
        tool_type: 'DataFrameTool',
        path: '/tmp/my_tool.py',
        source_kind: 'custom',
        editable: true,
      },
    })

    const wrapper = mountDialog()
    const vm = wrapper.vm as unknown as {
      toolName: string
      toolType: string
      onCreate: () => Promise<void>
    }
    vm.toolName = 'MyTool'
    vm.toolType = 'DataFrameTool'
    await wrapper.vm.$nextTick()

    await vm.onCreate()

    expect(vm.toolName).toBe('')
    expect(vm.toolType).toBe('ProcessingTool')
  })
})
