import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import OmeroSection from '@/components/panels/sections/OmeroSection.vue'

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
  props: { label: String, ariaLabel: String },
  emits: ['click'],
  template:
    '<button :aria-label="ariaLabel || label" @click="$emit(\'click\')">{{ label || ariaLabel }}</button>',
})

const TagStub = defineComponent({
  props: { value: String },
  template: '<span>{{ value }}</span>',
})

const baseSettings = {
  deployment_mode: 'desktop' as const,
  external_editor: null,
  napari_env_path: null,
  omero_instances: [],
  output_data_folder: '~/bioimageflow_data/',
  tool_store_path: '~/.bioimageflow/tool_packages/',
  update_mode: 'auto' as const,
  execution_engine: 'sequential' as const,
  cache_max_executions: null,
  cache_max_age: null,
  keyboard_shortcuts: {},
  dev_mode: true,
  datasets_root: null,
  max_upload_size: 2147483648,
  resolved_tool_store_path: '/tools',
  resolved_output_data_folder: '/out',
}

function mountSection(instances = baseSettings.omero_instances) {
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
    confirmRequire.mockClear()
  })

  it('adds an instance and emits transient password only on save', async () => {
    const wrapper = mountSection()

    await wrapper.get('[data-testid="omero-add-button"]').trigger('click')
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
})
