import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '@/api/client'
import ImageViewersSection from '../ImageViewersSection.vue'
import { useSettingsPanel } from '@/composables/useSettingsPanel'
import { useNapariStore } from '@/stores/napari'

const environment = {
  id: 'env-a', registration_order: 0, name: 'Tracking', ownership: 'managed', kind: 'conda',
  root: '/managed/tracking', interpreter: '/managed/tracking/bin/python',
  interpreter_identity: 'identity', interpreter_fingerprint: 'fingerprint',
  launch: { strategy: 'wetlands-managed', argv_prefix: [] }, state: 'ready',
  managed: { wetlands_name: 'napari-env-a', installation_generation: 'generation', recipe: { source: 'managed', preset: 'default', python: '==3.12.*', napari: '0.9.1', qt: 'PyQt6', requested_packages: ['reader>=1'], channels: ['conda-forge'] } },
  inventory: { python_version: '3.12.8', napari_version: '0.9.1', qt_distribution: 'PyQt6', qt_version: '6.8', bridge_distribution: null, bridge_version: null, distributions: [{ name: 'reader', version: '1.2' }], fingerprint: 'inventory', probed_at: '2026-09-15T00:00:00Z' },
}

describe('ImageViewersSection', () => {
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

    await wrapper.get('select[aria-label="Filename rule mode"]').setValue('pattern')
    await wrapper.get('input[aria-label="Extension or filename pattern"]').setValue('*')
    expect(wrapper.text()).toContain('catch-all * rule wins before every later rule')

    await wrapper.get('button[title="Edit rule"]').trigger('click')
    await wrapper.get('input[aria-label="Edit filename pattern"]').setValue('*.ome.tif')
    await wrapper.get('input[aria-label="Edit optional reader ID"]').setValue('reader-id')
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

  it('renders an honest non-modal per-output readiness report with candidate issues', async () => {
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

    const report = wrapper.get('[aria-labelledby="viewing-requirements-heading"]')
    expect(report.text()).toContain('nested/segment/image')
    expect(report.text()).toContain('Not verified')
    expect(report.text()).toContain('Activity')
    expect(report.text()).toContain('Not reported by the portable manifest')
    expect(report.text()).toContain('Refresh the environment inventory')
    expect(report.text()).toContain('Unknown outputs are not treated as compatible')
    expect(wrapper.find('.p-dialog').exists()).toBe(false)
  })
})
