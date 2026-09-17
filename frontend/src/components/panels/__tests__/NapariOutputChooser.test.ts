import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import NapariOutputChooser from '../NapariOutputChooser.vue'
import {
  getViewerPreferences,
  listNapariEnvironments,
  openInNapari,
  resolveNapariEnvironment,
  toggleViewerFavorite,
} from '@/api/napari'
import type { NapariResolveResponse, ViewerPreferencesSnapshot } from '@/api/types'

vi.mock('@/api/napari', () => ({
  getViewerPreferences: vi.fn(),
  listNapariEnvironments: vi.fn(),
  openInNapari: vi.fn(),
  resolveNapariEnvironment: vi.fn(),
  toggleViewerFavorite: vi.fn(),
}))

const identity = {
  run_id: 'run-4',
  node_key: 'segment/mask',
  result_key: 'result-8',
  record_id: 'record-12',
}
const preferenceKey = {
  kind: 'persistent' as const,
  workspace_id: 'c61df43d-503c-4564-962f-645e17a6e3e1',
  workflow_id: 'analysis',
  identity_generation: 7,
  node_path: ['segment', 'mask'],
  output_key: 'labels',
}

function response(overrides: Partial<NapariResolveResponse> = {}): NapariResolveResponse {
  return {
    artifact_identity: identity,
    preference_key: preferenceKey,
    workflow_id: 'analysis',
    identity_generation: 7,
    node_path: ['segment', 'mask'],
    output_key: 'labels',
    filename: 'labels.ome.tif',
    candidates: [{
      environment_id: '8c43031d-724e-4566-98a5-19747e191b17',
      name: 'Microscopy',
      status: 'compatible',
      label: 'Required packages installed',
      reason: 'Selected by the global default',
      preference: 'global_default',
      issues: [],
      missing_recommended_packages: [],
      reader_id: 'labels-reader',
    }],
    effective_environment_id: '8c43031d-724e-4566-98a5-19747e191b17',
    effective_reason: 'Selected by the global default',
    ...overrides,
  }
}

function preferences(revision = 0, environmentId?: string): ViewerPreferencesSnapshot {
  return {
    preferences_version: 1,
    revision,
    favorites: environmentId ? [{ key: preferenceKey, environment_id: environmentId }] : [],
  }
}

function mountChooser() {
  return mount(NapariOutputChooser, {
    attachTo: document.body,
    props: {
      workflowId: 'analysis',
      identityGeneration: 7,
      nodePath: ['segment', 'mask'],
      outputKey: 'labels',
      outputName: 'Cell labels',
      resultIdentity: identity,
      row: 42,
      path: '/stale/client/path.tif',
    },
    global: { plugins: [PrimeVue] },
  })
}

describe('NapariOutputChooser', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(openInNapari).mockReset().mockResolvedValue()
    vi.mocked(resolveNapariEnvironment).mockReset().mockResolvedValue(response())
    vi.mocked(getViewerPreferences).mockReset().mockResolvedValue(preferences())
    vi.mocked(toggleViewerFavorite).mockReset()
    vi.mocked(listNapariEnvironments).mockReset().mockResolvedValue({
      revision: 2,
      environments: [{
        id: '8c43031d-724e-4566-98a5-19747e191b17',
        registration_order: 0,
        name: 'Microscopy',
        ownership: 'external',
        kind: 'venv',
        root: '/env',
        interpreter: '/env/bin/python',
        interpreter_identity: 'python-id',
        interpreter_fingerprint: 'python-fingerprint',
        launch: { strategy: 'interpreter', argv_prefix: ['/env/bin/python'] },
        inventory: {
          python_version: '3.12',
          napari_version: '0.9.1',
          distributions: [],
          fingerprint: 'inventory-fingerprint',
          probed_at: '2026-09-15T10:00:00Z',
        },
        state: 'ready',
      }],
      default_environment_id: '8c43031d-724e-4566-98a5-19747e191b17',
      filename_rules: [],
      operations: [],
    })
  })

  afterEach(() => {
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  it('opens the server-selected environment with the exact captured result identity', async () => {
    const wrapper = mountChooser()
    await flushPromises()

    const primary = wrapper.get('[data-testid="open-napari-42-labels"]')
    expect(primary.attributes('aria-label')).toBe('Open in Microscopy')
    expect(primary.attributes('title')).toContain('Selected by the global default')
    await primary.trigger('click')

    expect(openInNapari).toHaveBeenCalledWith({
      paths: ['/stale/client/path.tif'],
      clear_layers: false,
      environment_id: '8c43031d-724e-4566-98a5-19747e191b17',
      reader_id: 'labels-reader',
      node_id: 'segment/mask',
      row: 42,
      col: 'labels',
      workflow_name: 'analysis',
      result_identity: identity,
    })
  })

  it('sets, replaces, and unsets the exclusive output favorite without launching', async () => {
    const secondEnvironmentId = 'b3a28e8d-63c0-4109-a4c7-2d3ef37e88ed'
    vi.mocked(resolveNapariEnvironment).mockResolvedValue(response({
      candidates: [
        ...response().candidates,
        {
          environment_id: secondEnvironmentId,
          name: 'Tracking',
          status: 'compatible',
          label: 'Required packages installed',
          reason: 'Compatible fallback',
          preference: 'other',
          issues: [],
          missing_recommended_packages: [],
        },
      ],
    }))
    const registry = await listNapariEnvironments()
    vi.mocked(listNapariEnvironments).mockResolvedValue({
      ...registry,
      environments: [
        ...(registry.environments ?? []),
        {
          id: secondEnvironmentId,
          registration_order: 1,
          name: 'Tracking',
          ownership: 'external',
          kind: 'venv',
          root: '/tracking',
          interpreter: '/tracking/bin/python',
          interpreter_identity: 'tracking-python',
          interpreter_fingerprint: 'tracking-fingerprint',
          launch: { strategy: 'interpreter', argv_prefix: ['/tracking/bin/python'] },
          state: 'ready',
        },
      ],
    })
    vi.mocked(toggleViewerFavorite)
      .mockResolvedValueOnce(preferences(1, response().candidates[0]!.environment_id))
      .mockResolvedValueOnce(preferences(2, secondEnvironmentId))
      .mockResolvedValueOnce(preferences(3))
    const wrapper = mountChooser()
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()

    let stars = [...document.querySelectorAll<HTMLButtonElement>('button[aria-pressed="false"]')]
    stars[0]!.click()
    await flushPromises()
    stars = [...document.querySelectorAll<HTMLButtonElement>('button[aria-pressed="false"]')]
    expect(document.querySelectorAll('button[aria-pressed="true"]')).toHaveLength(1)
    stars[0]!.click()
    await flushPromises()
    expect(document.querySelectorAll('button[aria-pressed="true"]')).toHaveLength(1)
    ;(document.querySelector('button[aria-label="Unset favorite for this output"]') as HTMLButtonElement).click()
    await flushPromises()

    expect(toggleViewerFavorite).toHaveBeenNthCalledWith(1, expect.objectContaining({
      environment_id: response().candidates[0]!.environment_id,
      expected_revision: 0,
    }))
    expect(toggleViewerFavorite).toHaveBeenNthCalledWith(2, expect.objectContaining({
      environment_id: secondEnvironmentId,
      expected_revision: 1,
    }))
    expect(toggleViewerFavorite).toHaveBeenNthCalledWith(3, expect.objectContaining({
      environment_id: secondEnvironmentId,
      expected_revision: 2,
    }))
    expect(openInNapari).not.toHaveBeenCalled()
  })

  it('explains incompatible and unavailable environments and requires an explicit try-anyway action', async () => {
    const incompatibleId = response().candidates[0]!.environment_id
    const unavailableId = '944f4316-e72a-4445-8026-482382f753b2'
    vi.mocked(resolveNapariEnvironment).mockResolvedValue(response({
      candidates: [{
        environment_id: incompatibleId,
        name: 'Missing reader',
        status: 'incompatible',
        label: 'Needs attention',
        reason: 'A required package is missing',
        preference: 'favorite',
        issues: [{
          code: 'missing_distribution',
          distribution: 'labels-reader',
          required_version: '>=2',
          detail: 'labels-reader is not installed',
        }],
        missing_recommended_packages: [],
      }, {
        environment_id: unavailableId,
        name: 'Moved environment',
        status: 'unavailable',
        label: 'Unavailable',
        reason: 'Interpreter is missing',
        preference: 'other',
        issues: [{ code: 'unavailable', detail: 'Interpreter no longer exists' }],
        missing_recommended_packages: [],
      }],
      effective_environment_id: null,
      effective_reason: 'No registered environment has verified required packages',
    }))
    const wrapper = mountChooser()
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('Saved preference unavailable')
    expect(document.body.textContent).toContain('labels-reader is not installed')
    const tryMissing = document.querySelector<HTMLButtonElement>(
      'button[aria-label="Try opening anyway in Missing reader"]',
    )!
    const tryUnavailable = document.querySelector<HTMLButtonElement>(
      'button[aria-label="Try opening anyway in Moved environment"]',
    )!
    expect(tryMissing.disabled).toBe(false)
    expect(tryUnavailable.disabled).toBe(true)
    const incompatibleStar = document.querySelector<HTMLButtonElement>(
      'button[aria-label="Unset favorite for this output"]',
    )!
    expect(incompatibleStar.disabled).toBe(false)
    tryMissing.click()
    await flushPromises()
    expect(openInNapari).toHaveBeenCalledTimes(1)
  })

  it('exposes an explicit replace action scoped to the effective environment', async () => {
    const wrapper = mountChooser()
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    const replace = [...document.querySelectorAll<HTMLButtonElement>('button')]
      .find(button => button.textContent?.includes('Replace layers and open'))!
    replace.click()
    await flushPromises()

    expect(openInNapari).toHaveBeenCalledWith(expect.objectContaining({
      environment_id: response().effective_environment_id,
      clear_layers: true,
      result_identity: identity,
    }))
  })
})
