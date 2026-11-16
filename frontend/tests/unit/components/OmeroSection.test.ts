import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OmeroSection from '@/components/panels/sections/OmeroSection.vue'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import type { ToolMetadata, OmeroInstanceResponse } from '@/api/types'
import type { CanvasCommandsApi } from '@/composables/useCanvasCommands'

const canvasCommands = vi.hoisted(() => ({
  addToolNode: vi.fn<CanvasCommandsApi['addToolNode']>(() => 'omero_1'),
  canAddToolNode: vi.fn(() => true),
}))
vi.mock('@/composables/useCanvasCommands', () => ({ useCanvasCommands: () => canvasCommands }))

const confirmRequire = vi.hoisted(() => vi.fn((options: { accept: () => void }) => {
  options.accept()
}))

vi.mock('primevue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequire }),
}))

const InputStub = defineComponent({
  props: { modelValue: [String, Number] },
  emits: ['update:modelValue'],
  template:
    '<input :aria-label="$attrs[\'aria-label\']" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
})

const NumberStub = defineComponent({
  props: { modelValue: Number },
  emits: ['update:modelValue'],
  template:
    '<input :aria-label="$attrs[\'aria-label\']" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
})

const ButtonStub = defineComponent({
  props: { label: String, ariaLabel: String, disabled: Boolean },
  emits: ['click'],
  template:
    '<button :disabled="disabled" :aria-label="ariaLabel || label" @click="$emit(\'click\')">{{ label || ariaLabel }}</button>',
})

const TagStub = defineComponent({
  props: { value: String },
  template: '<span>{{ value }}</span>',
})

const baseSettings = {
  deployment_mode: 'desktop' as const,
  external_editor: null,
  omero_instances: [],
  tool_store_path: '~/.bioimageflow/tool_packages/',
  update_mode: 'auto' as const,
  new_workflow_execution: 'sequential' as const,
  keyboard_shortcuts: {},
  enable_unsafe_webapp_features: false,
  datasets_root: null,
  max_upload_size: 2147483648,
  resolved_tool_store_path: '/tools',
}

function mountSection(instances: OmeroInstanceResponse[] = baseSettings.omero_instances) {
  return mount(OmeroSection, {
    props: {
      modelValue: {
        ...baseSettings,
        omero_instances: instances,
      },
    },
    global: {
      stubs: {
        InputText: InputStub,
        InputNumber: NumberStub,
        Password: InputStub,
        Button: ButtonStub,
        Tag: TagStub,
      },
    },
  })
}

describe('OmeroSection', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    confirmRequire.mockClear()
    canvasCommands.addToolNode.mockReset().mockReturnValue('omero_1')
    canvasCommands.canAddToolNode.mockReset().mockReturnValue(true)
  })

  it('shows an empty state before any instances are configured', () => {
    const wrapper = mountSection()

    expect(wrapper.get('[data-testid="omero-empty-state"]').text()).toBe(
      'No OMERO instances configured.',
    )
    expect(wrapper.find('[role="table"]').exists()).toBe(false)
  })

  it('renders labelled instance cards with derived headings and visible actions', () => {
    const wrapper = mountSection([
      {
        name: 'Prod',
        host: 'omero.example.com',
        port: 4064,
        username: 'admin',
        password_stored: true,
      },
      {
        name: null,
        host: 'test.example.com',
        port: 4064,
        username: 'tester',
        password_stored: false,
      },
    ])

    const cards = wrapper.findAll('[role="listitem"]')
    expect(cards).toHaveLength(2)
    expect(cards[0].get('h3').text()).toBe('Prod')
    expect(cards[1].get('h3').text()).toBe('test.example.com:tester')
    expect(cards[0].findAll('label').map((label) => label.text())).toEqual([
      'Name',
      'Host',
      'Port',
      'Username',
      'Password',
    ])
    expect(cards[0].get('button[aria-label="Save OMERO instance"]').text()).toBe('Save')
    expect(cards[0].get('button[aria-label="Duplicate OMERO instance"]').text()).toBe(
      'Duplicate',
    )
    expect(cards[0].get('button[aria-label="Remove OMERO instance"]').text()).toBe(
      'Remove',
    )
  })

  it('adds an instance and emits transient password only on save', async () => {
    const wrapper = mountSection()

    await wrapper.get('[data-testid="omero-add-button"]').trigger('click')
    expect(wrapper.get('[data-testid="omero-card-0"] h3').text()).toBe('OMERO instance 1')
    await wrapper.get('input[aria-label="Host"]').setValue(' omero.example.com ')
    await wrapper.get('input[aria-label="Username"]').setValue(' admin ')
    await wrapper.get('input[aria-label="Password"]').setValue('secret')
    await wrapper.get('button[aria-label="Save OMERO instance"]').trigger('click')

    expect(wrapper.emitted('update:field')?.[0]).toEqual([
      {
        field: 'omero_instances',
        value: [
          {
            name: null,
            host: 'omero.example.com',
            port: 4064,
            username: 'admin',
            password: 'secret',
          },
        ],
      },
    ])
  })

  it('duplicates metadata without password', async () => {
    const wrapper = mountSection([
      {
        name: 'Prod',
        host: 'omero.example.com',
        port: 4064,
        username: 'admin',
        password_stored: true,
      },
    ])

    await wrapper.get('input[aria-label="Password"]').setValue('secret')
    await wrapper.get('button[aria-label="Duplicate OMERO instance"]').trigger('click')

    const passwordInputs = wrapper.findAll('input[aria-label="Password"]')
    expect(passwordInputs).toHaveLength(2)
    expect((passwordInputs[1].element as HTMLInputElement).value).toBe('')
  })

  it('validates required host before emitting', async () => {
    const wrapper = mountSection()

    await wrapper.get('[data-testid="omero-add-button"]').trigger('click')
    await wrapper.get('input[aria-label="Username"]').setValue('admin')
    await wrapper.get('button[aria-label="Save OMERO instance"]').trigger('click')

    expect(wrapper.emitted('update:field')).toBeUndefined()
    expect(wrapper.get('[data-testid="omero-validation-error"]').text()).toContain(
      'Host is required',
    )
  })

  it('confirms removal with the specified message and emits remaining rows', async () => {
    const wrapper = mountSection([
      {
        name: 'Prod',
        host: 'omero.example.com',
        port: 4064,
        username: 'admin',
        password_stored: true,
      },
    ])

    await wrapper.get('button[aria-label="Remove OMERO instance"]').trigger('click')

    expect(confirmRequire).toHaveBeenCalledWith(
      expect.objectContaining({
        message: "Remove OMERO instance 'Prod'? Stored credentials will be deleted.",
      }),
    )
    expect(wrapper.emitted('update:field')?.[0]).toEqual([
      { field: 'omero_instances', value: [] },
    ])
  })

  const savedInstance = {
    name: 'Prod', host: 'omero.example.com', port: 4064, username: 'scientist', password_stored: true,
  }
  function installTools(packageName = 'bioimageflow_omero_tools') {
    useToolRegistryStore().tools = ['OmeroDownloadDataset', 'OmeroUploadImage'].map(name => ({
      name, display_name: name, package: packageName, package_version: '0.2.0', source_kind: 'package',
      inputs: {}, outputs: {},
    } as ToolMetadata))
  }

  it('adds transfer tools with only saved connection fields and exact installed bindings', async () => {
    installTools()
    const wrapper = mountSection([savedInstance])
    for (const [action, tool] of [['download', 'OmeroDownloadDataset'], ['upload', 'OmeroUploadImage']]) {
      await wrapper.get(`button[aria-label="Add OMERO ${action} tool"]`).trigger('click')
      expect(canvasCommands.addToolNode).toHaveBeenLastCalledWith(tool, {
        host: savedInstance.host, port: 4064, username: 'scientist',
      }, {
        tool_module: 'bioimageflow_omero_tools.omero', tool_class: tool,
        tool_package: 'bioimageflow_omero_tools', tool_package_version: '0.2.0',
      })
    }
    expect(wrapper.emitted('update:field')).toBeUndefined()
    const captured = canvasCommands.addToolNode.mock.calls[0]
    await wrapper.setProps({ modelValue: { ...baseSettings, omero_instances: [{ ...savedInstance, host: 'later.example.com' }] } })
    expect(captured[1]).toEqual({ host: 'omero.example.com', port: 4064, username: 'scientist' })
    expect(JSON.stringify(canvasCommands.addToolNode.mock.calls)).not.toContain('password')
  })

  it.each(['Host', 'Port', 'Username', 'Password'])('refuses transfers while %s has an unsaved edit', async field => {
    installTools()
    const wrapper = mountSection([savedInstance])
    await wrapper.get(`input[aria-label="${field}"]`).setValue(field === 'Port' ? '4065' : 'unsaved-secret-or-value')
    for (const action of ['download', 'upload']) {
      const button = wrapper.get(`button[aria-label="Add OMERO ${action} tool"]`)
      expect(button.attributes('disabled')).toBeDefined()
      await button.trigger('click')
    }
    expect(canvasCommands.addToolNode).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:field')).toBeUndefined()
  })

  it('keeps new and duplicated cards disabled until settings accept them', async () => {
    installTools()
    const wrapper = mountSection([savedInstance])
    await wrapper.get('button[aria-label="Duplicate OMERO instance"]').trigger('click')
    await wrapper.get('[data-testid="omero-add-button"]').trigger('click')
    for (const index of [1, 2]) {
      expect(wrapper.get(`[data-testid="omero-card-${index}"] button[aria-label="Add OMERO download tool"]`).attributes('disabled')).toBeDefined()
    }
    expect(canvasCommands.addToolNode).not.toHaveBeenCalled()
  })

  it('requires a writable active canvas and exact first-party catalog tools', async () => {
    installTools('unrelated-package')
    const wrapper = mountSection([savedInstance])
    expect(wrapper.get('button[aria-label="Add OMERO download tool"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Install the OMERO tools from Tools')
    wrapper.unmount()
    installTools()
    canvasCommands.canAddToolNode.mockReturnValue(false)
    const unavailable = mountSection([savedInstance])
    for (const action of ['download', 'upload']) {
      const button = unavailable.get(`button[aria-label="Add OMERO ${action} tool"]`)
      expect(button.attributes('disabled')).toBeDefined()
      await button.trigger('click')
    }
    expect(canvasCommands.addToolNode).not.toHaveBeenCalled()
  })
})
