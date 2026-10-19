import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Select from 'primevue/select'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '@/api/client'
import ImageViewersSection from '../ImageViewersSection.vue'
import { useSettingsPanel } from '@/composables/useSettingsPanel'
import { useNapariStore } from '@/stores/napari'
import type { NapariViewingRequirementGroup } from '@/api/types'

enableAutoUnmount(afterEach)

function viewingGroup(packages: string): NapariViewingRequirementGroup {
  return {
    id: `sha256:${'a'.repeat(64)}`, members: ['node/image'], required_packages: [],
    recommended_packages: [], napari_version: null,
    managed_create_prefill: { requested_packages: [packages], recommended_packages: [],
      napari_version_constraint: null, package_source: 'unverified', requires_source_confirmation: false },
  }
}

const environment = {
  id: 'env-a', registration_order: 0, name: 'Tracking', ownership: 'managed', kind: 'conda',
  root: '/managed/tracking', interpreter: '/managed/tracking/bin/python',
  interpreter_identity: 'identity',
  launch: { strategy: 'wetlands-managed', argv_prefix: [] }, state: 'ready',
  managed: { wetlands_name: 'napari-env-a', installation_generation: 'generation', recipe: { source: 'managed', preset: 'default', python: '==3.12.*', napari: '0.9.1', qt: 'PyQt6', requested_packages: ['reader>=1'], channels: ['conda-forge'] } },
  inventory: { python_version: '3.12.8', napari_version: '0.9.1', qt_distribution: 'PyQt6', qt_version: '6.8', bridge_distribution: null, bridge_version: null, distributions: [{ name: 'reader', version: '1.2' }], fingerprint: 'inventory', probed_at: '2026-09-15T00:00:00Z' },
}

describe('ImageViewersSection', () => {
  it('requires an explicit exact napari version instead of reusing a prior recipe for a constrained set', async () => {
    const settings = useSettingsPanel()
    const store = useNapariStore()
    const creation = vi.spyOn(store, 'createManagedEnvironment').mockResolvedValue({ environment_id: 'env-a', id: 'op' } as any)
    vi.spyOn(store, 'watchOperation').mockResolvedValue({} as any)
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    const recipe = wrapper.findAllComponents(Select).find(item => item.attributes('id') === 'managed-environment-recipe')!
    await recipe.vm.$emit('update:modelValue', 'advanced')
    await flushPromises()
    await wrapper.get('input[aria-label="napari version"]').setValue('0.9.1')
    const group = viewingGroup('legacy-reader>=1')
    group.napari_version = '>=0.6,<0.7'
    group.managed_create_prefill.napari_version_constraint = '>=0.6,<0.7'
    settings.prepareNapariCreate([group], {})
    settings.selectNapariCreateGroup(group)
    await flushPromises()
    expect(wrapper.text()).toContain('Required napari constraint: >=0.6,<0.7')
    const version = wrapper.get('input[aria-label="napari version"]')
    expect((version.element as HTMLInputElement).value).toBe('')
    const button = wrapper.findAll('button').find(item => item.text() === 'Create environment')!
    expect(button.attributes('disabled')).toBeDefined()
    expect(creation).not.toHaveBeenCalled()
    await recipe.vm.$emit('update:modelValue', 'default')
    await flushPromises()
    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('click')
    expect(creation).not.toHaveBeenCalled()
    await recipe.vm.$emit('update:modelValue', 'advanced')
    await flushPromises()
    await wrapper.get('input[aria-label="napari version"]').setValue('0.6.6')
    await button.trigger('click')
    await flushPromises()
    expect(creation).toHaveBeenCalledWith(expect.objectContaining({ recipe: expect.objectContaining({ preset: 'advanced', napari: '0.6.6', requested_packages: ['legacy-reader>=1'] }) }))
  })

  it('discards a superseded queued setup transfer before the form mounts', async () => {
    const settings = useSettingsPanel()
    settings.prepareNapariCreate([viewingGroup('first-reader>=1')], {})
    settings.selectNapariCreateGroup(settings.napariCreatePrefills.value[0]!)
    settings.prepareNapariCreate([viewingGroup('second-reader>=2')], {})
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()
    expect((wrapper.get('textarea[aria-label="Required Python distributions"]').element as HTMLTextAreaElement).value).toBe('second-reader>=2')
    expect(settings.napariCreateTransfer.value).toBeNull()
  })

  it('preserves an edited form through readiness refresh and transfers only an explicitly selected set', async () => {
    const settings = useSettingsPanel()
    settings.prepareNapariCreate([viewingGroup('first-reader>=1')], {})
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()
    const packages = wrapper.get('textarea[aria-label="Required Python distributions"]')
    await packages.setValue('user-edited-reader>=3')
    settings.prepareNapariCreate([viewingGroup('second-reader>=2')], {})
    await flushPromises()
    expect((packages.element as HTMLTextAreaElement).value).toBe('user-edited-reader>=3')
    settings.selectNapariCreateGroup(settings.napariCreatePrefills.value[0]!)
    await flushPromises()
    expect((packages.element as HTMLTextAreaElement).value).toBe('second-reader>=2')
    expect((packages.element as HTMLTextAreaElement).value).not.toContain('first-reader')
  })

  it('keeps an in-flight creation bound to its captured group and preserves a newer same-ID prefill', async () => {
    const settings = useSettingsPanel()
    settings.prepareNapariCreate([viewingGroup('first-reader>=1')], {})
    const store = useNapariStore()
    let resolveCreation!: (value: any) => void
    const creation = vi.spyOn(store, 'createManagedEnvironment').mockReturnValue(new Promise(resolve => { resolveCreation = resolve }))
    vi.spyOn(store, 'watchOperation').mockResolvedValue({} as any)
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()
    const button = wrapper.findAll('button').find(item => item.text() === 'Create environment')!
    await button.trigger('click')
    settings.prepareNapariCreate([viewingGroup('second-reader>=2')], {})
    await flushPromises()
    expect((wrapper.get('textarea[aria-label="Required Python distributions"]').element as HTMLTextAreaElement).value).toBe('first-reader>=1')
    expect(creation).toHaveBeenCalledWith(expect.objectContaining({ recipe: expect.objectContaining({ requested_packages: ['first-reader>=1'] }) }))
    resolveCreation({ environment_id: 'env-a', id: 'op' })
    await flushPromises()
    expect(settings.napariCreatePrefills.value[0]!.managed_create_prefill.requested_packages).toEqual(['second-reader>=2'])
  })

  it('does not publish an older creation failure into an explicitly transferred form', async () => {
    const settings = useSettingsPanel()
    settings.prepareNapariCreate([viewingGroup('first-reader>=1')], {})
    let rejectCreation!: (error: Error) => void
    vi.spyOn(useNapariStore(), 'createManagedEnvironment').mockReturnValue(new Promise((_resolve, reject) => { rejectCreation = reject }))
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === 'Create environment')!.trigger('click')
    settings.prepareNapariCreate([viewingGroup('second-reader>=2')], {})
    settings.selectNapariCreateGroup(settings.napariCreatePrefills.value[0]!)
    await flushPromises()
    rejectCreation(new Error('Obsolete creation failed'))
    await flushPromises()
    expect(wrapper.text()).not.toContain('Obsolete creation failed')
    expect((wrapper.get('textarea[aria-label="Required Python distributions"]').element as HTMLTextAreaElement).value).toBe('second-reader>=2')
    expect(settings.napariCreatePrefills.value[0]!.managed_create_prefill.requested_packages).toEqual(['second-reader>=2'])
  })

  beforeEach(() => {
    setActivePinia(createPinia())
    useSettingsPanel().prepareNapariCreate([])
    vi.mocked(api.get).mockReset().mockImplementation((url: string) => {
      if (url.includes('/operations/')) return Promise.resolve({ data: { revision: 4, environment, operation: { id: 'op', environment_id: 'env-a', kind: 'create', state: 'completed', progress: 100, message: 'Ready', error: null } } })
      if (url === '/api/v1/napari/status') return Promise.resolve({ data: { environment_id: 'env-a', environment_name: 'Tracking', installation_identity: 'identity', status: 'running', running: true, env_path: environment.root, pid: 42 } })
      return Promise.resolve({ data: { revision: 4, environments: [environment], default_environment_id: 'env-a', filename_rules: [{ id: 'r1', pattern: '*.tif', environment_id: 'env-a', enabled: true, reader_id: null }], operations: [{ id: 'op', environment_id: 'env-a', kind: 'create', state: 'installing', progress: 60, message: 'Installing packages', error: null }] } })
    })
    vi.mocked(api.post).mockReset()
    vi.mocked(api.put).mockReset()
    vi.mocked(api.patch).mockReset()
    vi.mocked(api.delete).mockReset()
  })

  it('offers explicit Setup for an uninstalled default and retries that same entry after failure', async () => {
    const declaration = {
      ...environment, name: 'Default napari', state: 'setup_needed',
      root: 'managed-pending:napari-env-a', interpreter: '', interpreter_identity: '', inventory: null,
      managed: { ...environment.managed, installation_generation: null,
        recipe: { ...environment.managed.recipe, requested_packages: [] } },
    }
    vi.mocked(api.get).mockImplementation((url: string) => Promise.resolve({ data: url === '/api/v1/napari/status'
      ? { environment_id: declaration.id, status: 'stopped', running: false }
      : { revision: 1, environments: [declaration], default_environment_id: declaration.id, filename_rules: [], operations: [] },
    }))
    const napari = useNapariStore()
    const watcher = vi.spyOn(napari, 'watchOperation').mockResolvedValue({} as any)
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 1 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()
    const card = wrapper.get(`[data-testid="napari-environment-card-${declaration.id}"]`)
    expect(card.get('details').attributes('open')).toBeDefined()
    const button = (label: string) => card.findAll('button').find(item => item.text() === label)
    expect(button('Setup')).toBeDefined()
    expect(button('Retry')).toBeUndefined()
    expect(button('Forget')).toBeDefined()
    expect(button('Delete managed installation')).toBeUndefined()
    expect(button('Refresh')!.attributes('disabled')).toBeDefined()
    expect(button('Launch empty viewer')!.attributes('disabled')).toBeDefined()
    expect(api.post).not.toHaveBeenCalled()
    const operation = { id: 'setup-op', environment_id: declaration.id, kind: 'retry', state: 'resolving',
      progress: 5, message: 'Resolving managed environment recipe', error: null }
    vi.mocked(api.post).mockResolvedValueOnce({ data: { revision: 2,
      environment: { ...declaration, state: 'creating' }, operation } })
    await button('Setup')!.trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledExactlyOnceWith(`/api/v1/napari/environments/${declaration.id}/retry`, { expected_revision: 1 })
    expect(watcher).toHaveBeenCalledWith(declaration.id, operation.id)
    expect(wrapper.text()).toContain('Resolving managed environment recipe')
    napari.applySnapshot({ revision: 3, environments: [{ ...declaration, state: 'failed' }],
      default_environment_id: declaration.id, filename_rules: [], operations: [{ ...operation, state: 'failed',
        message: 'Controlled setup failure', error: { code: 'napari_provision_failed', detail: 'Controlled setup failure' } }],
    } as any)
    await flushPromises()
    expect(button('Setup')).toBeUndefined()
    expect(button('Retry')).toBeDefined()
    expect(wrapper.text()).toContain('Controlled setup failure')
    vi.mocked(api.post).mockResolvedValueOnce({ data: { revision: 4,
      environment: { ...declaration, state: 'creating' }, operation: { ...operation, id: 'retry-op' } } })
    await button('Retry')!.trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenLastCalledWith(`/api/v1/napari/environments/${declaration.id}/retry`, { expected_revision: 3 })
    expect(napari.environments.map(item => item.id)).toEqual([declaration.id])
    expect(napari.defaultEnvironmentId).toBe(declaration.id)
  })

  it('shows immutable details as installed packages and operation progress', async () => {
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Installed packages')
    expect(wrapper.text()).toContain('reader 1.2')
    expect(wrapper.text()).toContain('Managed by BioImageFlow')
    expect(wrapper.text()).toContain('/managed/tracking')
    expect(wrapper.text()).toContain('Installing packages')
    expect(wrapper.text()).not.toContain('napari plugins')
  })

  it('previews the canonical extension shorthand before saving', async () => {
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()
    const inputs = wrapper.findAll('input')
    const ruleInput = inputs.find(input => input.attributes('placeholder') === '.tif')!
    await ruleInput.setValue('.ome.tif')
    expect(wrapper.text()).toContain('Saves as *.ome.tif')
  })

  it('prefills one uncovered requirement group without combining separate groups', async () => {
    useSettingsPanel().prepareNapariCreate([
      {
        id: `sha256:${'a'.repeat(64)}`,
        members: ['segment/image'],
        required_packages: [],
        recommended_packages: [],
        napari_version: null,
        managed_create_prefill: {
          requested_packages: ['special-reader>=2'],
          recommended_packages: ['viewer-colormap>=1'],
          napari_version_constraint: null,
          package_source: 'unverified',
          requires_source_confirmation: true,
        },
      },
      {
        id: `sha256:${'b'.repeat(64)}`,
        members: ['track/table'],
        required_packages: [],
        recommended_packages: [],
        napari_version: null,
        managed_create_prefill: {
          requested_packages: ['track-reader>=3'],
          recommended_packages: [],
          napari_version_constraint: null,
          package_source: 'unverified',
          requires_source_confirmation: true,
        },
      },
    ])
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()

    const packages = wrapper.get('textarea[aria-label="Required Python distributions"]')
      .element as HTMLTextAreaElement
    expect(packages.value).toBe('special-reader>=2')
    expect(wrapper.text()).toContain('Package availability on PyPI is not yet verified')
    expect(wrapper.text()).toContain('viewer-colormap>=1')
    expect(packages.value).not.toContain('track-reader')
    const createButton = wrapper.findAll('button').find(button => button.text() === 'Create environment')!
    expect(createButton.attributes('disabled')).toBeDefined()
    await wrapper.get('.source-confirmation input').setValue(true)
    expect(createButton.attributes('disabled')).toBeUndefined()
  })

  it('warns about catch-all rules and edits the complete canonical rule', async () => {
    vi.mocked(api.put).mockResolvedValueOnce({
      data: { revision: 5, environments: [environment], default_environment_id: 'env-a', filename_rules: [{ id: 'r1', pattern: '*.ome.tif', environment_id: 'env-a', enabled: true, reader_id: 'reader-id' }], operations: [] },
    })
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()

    const mode = wrapper.findAllComponents(Select).find(component => component.attributes('id') === 'filename-rule-mode')!
    mode.vm.$emit('update:modelValue', 'pattern')
    await flushPromises()
    await wrapper.get('input[aria-label="Extension or filename pattern"]').setValue('*')
    expect(wrapper.text()).toContain('catch-all * rule wins before every later rule')

    await wrapper.get('button[title="Edit rule"]').trigger('click')
    await wrapper.get('input[aria-label="Edit filename pattern"]').setValue('*.ome.tif')
    await wrapper.get('input[aria-label="Edit reader plugin ID"]').setValue('reader-id')
    await wrapper.get('button[title="Save rule"]').trigger('click')
    await flushPromises()

    expect(api.put).toHaveBeenCalledWith('/api/v1/napari/environment-settings/filename-rules', {
      rules: [expect.objectContaining({ pattern: '*.ome.tif', environment_id: 'env-a', reader_id: 'reader-id' })],
      expected_revision: 4,
    })
  })

  it('does not offer locate or launch for a failed recipe-created environment', async () => {
    const unavailable = { ...environment, state: 'probe_failed' }
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/api/v1/napari/status') return Promise.reject(new Error('unavailable'))
      return Promise.resolve({ data: { revision: 4, environments: [unavailable], default_environment_id: null, filename_rules: [], operations: [] } })
    })
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()

    expect(wrapper.find('button[aria-label="Locate environment"]').exists()).toBe(false)
    const launch = wrapper.findAll('button').find(button => button.text() === 'Launch empty viewer')!
    expect(launch.attributes('disabled')).toBeDefined()
  })

  it('omits the large readiness report but retains setup prefills and concise guidance', async () => {
    const napari = useNapariStore()
    napari.viewingManifest = { schema: 'bioimageflow.viewing_requirements.v1', complete: false, outputs: {} }
    napari.viewingReadiness = {
      manifest_schema: 'bioimageflow.viewing_requirements.v1',
      manifest_complete: false,
      summary: { total_outputs: 1, covered_outputs: 0, not_covered_outputs: 0, unknown_outputs: 1, outputs_needing_setup: 0, message: '1 output could not be verified' },
      outputs: [{
        output_identity: 'nested/segment/image', manifest_status: 'unknown',
        manifest_reason: 'Tool metadata was unavailable', status: 'unknown',
        reason: 'manifest_unknown', group_id: null, effective_environment_id: null,
        effective_reason: 'Choose explicitly after refreshing metadata',
        candidates: [{
          environment_id: 'env-a', name: 'Tracking', status: 'unknown',
          label: 'Not verified', reason: 'Inventory is stale', preference: 'other',
          issues: [{ code: 'inventory_stale', detail: 'Refresh the environment inventory' }],
          missing_recommended_packages: [], reader_id: null,
        }],
      }],
      groups: [],
    }
    vi.mocked(api.post).mockResolvedValue({ data: napari.viewingReadiness })
    const wrapper = mount(ImageViewersSection, {
      props: { modelValue: { deployment_mode: 'desktop', napari_registry_revision: 4 } as any },
      global: { plugins: [PrimeVue] },
    })
    await flushPromises()

    expect(wrapper.find('[aria-labelledby="viewing-requirements-heading"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Create a napari environment')
    expect(wrapper.text()).toContain('checks the complete file or folder name from top to bottom')
    expect(wrapper.text()).toContain('Reader plugin ID (optional)')
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.find('input[aria-label="Test filename"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Create modified copy')
  })

})
