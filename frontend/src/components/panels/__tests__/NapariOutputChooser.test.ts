import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Popover from 'primevue/popover'
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
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 0 })
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
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('does no passive resolution for repeated mounted cells and resolves fresh on each action', async () => {
    const cells = [mountChooser(), mountChooser(), mountChooser(), mountChooser()]
    await flushPromises()
    expect(resolveNapariEnvironment).not.toHaveBeenCalled()
    expect(getViewerPreferences).not.toHaveBeenCalled()
    expect(listNapariEnvironments).not.toHaveBeenCalled()
    await cells[0]!.get('[data-testid="open-napari-42-labels"]').trigger('click')
    await flushPromises()
    const nextEnvironment = 'b3a28e8d-63c0-4109-a4c7-2d3ef37e88ed'
    vi.mocked(resolveNapariEnvironment).mockResolvedValueOnce(response({
      effective_environment_id: nextEnvironment,
      candidates: [{ ...response().candidates[0]!, environment_id: nextEnvironment, name: 'Tracking' }],
    }))
    await cells[0]!.get('[data-testid="open-napari-42-labels"]').trigger('click')
    await flushPromises()
    expect(resolveNapariEnvironment).toHaveBeenCalledTimes(2)
    expect(openInNapari).toHaveBeenLastCalledWith(expect.objectContaining({ environment_id: nextEnvironment }))
    cells.forEach(cell => cell.unmount())
  })

  it('explains an unavailable saved favorite before dispatching to a fallback', async () => {
    vi.mocked(resolveNapariEnvironment).mockResolvedValue(response({ candidates: [
      ...response().candidates,
      { ...response().candidates[0]!, environment_id: 'moved', name: 'Old favorite',
        preference: 'favorite', status: 'unavailable', reason: 'Interpreter was moved' },
    ] }))
    const wrapper = mountChooser()
    await wrapper.get('[data-testid="open-napari-42-labels"]').trigger('click')
    await flushPromises()
    expect(openInNapari).not.toHaveBeenCalled()
    expect(resolveNapariEnvironment).toHaveBeenCalledOnce()
    expect(document.body.textContent).toContain('Saved preference unavailable')
    document.querySelector<HTMLButtonElement>('button[aria-label="Open once in Microscopy"]')!.click()
    await flushPromises()
    expect(openInNapari).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('does not resolve again when closing the menu and checks fresh choices when reopening', async () => {
    const wrapper = mountChooser()
    const menu = wrapper.get('[data-testid="choose-napari-42-labels"]')
    await menu.trigger('click')
    await flushPromises()
    expect(resolveNapariEnvironment).toHaveBeenCalledOnce()
    await menu.trigger('click')
    await flushPromises()
    expect(resolveNapariEnvironment).toHaveBeenCalledOnce()
    await menu.trigger('click')
    await flushPromises()
    expect(resolveNapariEnvironment).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('opens the server-selected environment with the exact captured result identity', async () => {
    const wrapper = mountChooser()
    await flushPromises()

    const primary = wrapper.get('[data-testid="open-napari-42-labels"]')
    expect(primary.attributes('aria-label')).toBe('Open image in napari')
    expect(resolveNapariEnvironment).not.toHaveBeenCalled()
    await primary.trigger('click')
    await flushPromises()
    expect(primary.attributes('aria-label')).toBe('Open in Microscopy')

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
    expect(document.body.textContent).toContain('Will open in Microscopy')
    expect(document.body.textContent).not.toContain('Registration order fallback')
    expect([...document.querySelectorAll<HTMLButtonElement>('button')].some(button => button.textContent === 'Unset favorite')).toBe(false)

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
    vi.mocked(getViewerPreferences).mockResolvedValue(preferences(1, incompatibleId))
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

  it('does not open a deferred menu after its result selection changes', async () => {
    let frame!: FrameRequestCallback
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frame = callback; return 0 })
    const wrapper = mountChooser()
    const show = vi.spyOn(wrapper.findComponent(Popover).vm, 'show')
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    expect(show).not.toHaveBeenCalled()
    await wrapper.setProps({ row: 43 })
    frame(0)
    await flushPromises()
    expect(show).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('waits for stable anchor geometry and queued ancestor scroll before showing the menu', async () => {
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.push(callback); return 0 })
    const wrapper = mountChooser()
    const show = vi.spyOn(wrapper.findComponent(Popover).vm, 'show')
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    frames.shift()!(0)
    await flushPromises()
    expect(show).not.toHaveBeenCalled()
    document.body.dispatchEvent(new Event('scroll'))
    frames.shift()!(0)
    await flushPromises()
    expect(show).not.toHaveBeenCalled()
    frames.shift()!(0)
    await flushPromises()
    expect(show).not.toHaveBeenCalled()
    frames.shift()!(0)
    await flushPromises()
    expect(show).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('cancels a pending menu when the user scrolls and permits a later explicit reopen', async () => {
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.push(callback); return 0 })
    const wrapper = mountChooser()
    const show = vi.spyOn(wrapper.findComponent(Popover).vm, 'show')
    const button = wrapper.get('[data-testid="choose-napari-42-labels"]')
    await button.trigger('click')
    await flushPromises()
    window.dispatchEvent(new Event('wheel'))
    frames.shift()!(0)
    await flushPromises()
    expect(show).not.toHaveBeenCalled()
    await button.trigger('click')
    await flushPromises()
    frames.shift()!(0)
    await flushPromises()
    frames.shift()!(0)
    await flushPromises()
    expect(show).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('retains the clicked button while resolving an async fallback chooser', async () => {
    let finish!: (value: NapariResolveResponse) => void
    vi.mocked(resolveNapariEnvironment).mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    const wrapper = mountChooser()
    const show = vi.spyOn(wrapper.findComponent(Popover).vm, 'show')
    const button = wrapper.get<HTMLButtonElement>('[data-testid="open-napari-42-labels"]')
    button.element.click()
    finish(response({ effective_environment_id: null }))
    await flushPromises()
    expect(show).toHaveBeenCalledWith(expect.any(MouseEvent), button.element)
    wrapper.unmount()
  })

  it('abandons a pending primary action if its captured path changes', async () => {
    let finish!: (value: NapariResolveResponse) => void
    vi.mocked(resolveNapariEnvironment).mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    const wrapper = mountChooser()
    await wrapper.get('[data-testid="open-napari-42-labels"]').trigger('click')
    await wrapper.setProps({ path: '/replacement/path.tif' })
    finish(response())
    await flushPromises()
    expect(openInNapari).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="open-napari-42-labels"]').trigger('click')
    await flushPromises()
    expect(openInNapari).toHaveBeenCalledWith(expect.objectContaining({ paths: ['/replacement/path.tif'] }))
    wrapper.unmount()
  })

  it('withdraws the previous replace action while a changed artifact awaits resolution', async () => {
    const wrapper = mountChooser()
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('Clear layers, then open')
    let finishCurrent!: (value: NapariResolveResponse) => void
    vi.mocked(resolveNapariEnvironment).mockReturnValueOnce(new Promise(resolve => { finishCurrent = resolve }))
    const nextIdentity = { ...identity, result_key: 'replacement-result' }
    await wrapper.setProps({ resultIdentity: nextIdentity, identityGeneration: 8, outputKey: 'next-output', row: 43 })
    const replacement = [...document.querySelectorAll<HTMLButtonElement>('button')]
      .find(button => button.textContent?.includes('Clear layers, then open'))
    expect(replacement).toBeUndefined()
    expect(openInNapari).not.toHaveBeenCalled()
    expect(toggleViewerFavorite).not.toHaveBeenCalled()
    const nextEnvironment = 'b3a28e8d-63c0-4109-a4c7-2d3ef37e88ed'
    await wrapper.get('[data-testid="choose-napari-43-next-output"]').trigger('click')
    finishCurrent(response({ artifact_identity: nextIdentity, identity_generation: 8, output_key: 'next-output',
      preference_key: { ...preferenceKey, identity_generation: 8, output_key: 'next-output' },
      effective_environment_id: nextEnvironment,
      candidates: [{ ...response().candidates[0]!, environment_id: nextEnvironment, name: 'Tracking', reader_id: 'current-reader' }],
    }))
    await flushPromises()
    const currentReplace = [...document.querySelectorAll<HTMLButtonElement>('button')]
      .find(button => button.textContent?.includes('Clear layers, then open'))!
    expect(currentReplace.title).toContain('Tracking')
    currentReplace.click()
    await flushPromises()
    expect(openInNapari).toHaveBeenCalledOnce()
    expect(openInNapari).toHaveBeenCalledWith({ paths: ['/stale/client/path.tif'],
      clear_layers: true, environment_id: nextEnvironment, reader_id: 'current-reader', node_id: nextIdentity.node_key,
      row: 43, col: 'next-output', workflow_name: 'analysis', result_identity: nextIdentity })
    expect(toggleViewerFavorite).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('does not retarget a favorite while retrying a failed preference read', async () => {
    vi.mocked(getViewerPreferences).mockRejectedValueOnce(new Error('Preferences temporarily unavailable'))
    const wrapper = mountChooser()
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    let finishPreferences!: (value: ViewerPreferencesSnapshot) => void
    vi.mocked(getViewerPreferences).mockReturnValueOnce(new Promise(resolve => { finishPreferences = resolve }))
    const star = document.querySelector<HTMLButtonElement>('button[aria-label="Set Microscopy as favorite for this output"]')!
    expect(star).toBeTruthy()
    star.click()
    await flushPromises()
    const nextKey = { ...preferenceKey, output_key: 'next-output' }
    const nextIdentity = { ...identity, result_key: 'next-result' }
    vi.mocked(resolveNapariEnvironment).mockResolvedValue(response({ artifact_identity: nextIdentity, preference_key: nextKey, output_key: 'next-output' }))
    await wrapper.setProps({ resultIdentity: nextIdentity, outputKey: 'next-output' })
    await flushPromises()
    vi.mocked(toggleViewerFavorite).mockResolvedValue(preferences(4))
    finishPreferences(preferences(3))
    await flushPromises()
    expect(toggleViewerFavorite).not.toHaveBeenCalled()
    expect(openInNapari).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('does not restore an old menu snapshot over a replacement output favorite', async () => {
    let finishOldPreferences!: (value: ViewerPreferencesSnapshot) => void
    vi.mocked(getViewerPreferences).mockReturnValueOnce(new Promise(resolve => { finishOldPreferences = resolve }))
    const wrapper = mountChooser()
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    const nextKey = { ...preferenceKey, output_key: 'next-output' }
    const nextIdentity = { ...identity, result_key: 'next-result' }
    vi.mocked(resolveNapariEnvironment).mockResolvedValue(response({ artifact_identity: nextIdentity, preference_key: nextKey, output_key: 'next-output' }))
    vi.mocked(getViewerPreferences).mockResolvedValue({ preferences_version: 1, revision: 5,
      favorites: [{ key: nextKey, environment_id: response().effective_environment_id! }] })
    await wrapper.setProps({ resultIdentity: nextIdentity, outputKey: 'next-output' })
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-next-output"]').trigger('click')
    await flushPromises()
    expect(document.querySelectorAll('button[aria-pressed="true"]')).toHaveLength(1)
    finishOldPreferences(preferences(1))
    await flushPromises()
    expect(document.querySelectorAll('button[aria-pressed="true"]')).toHaveLength(1)
    expect(toggleViewerFavorite).not.toHaveBeenCalled()
    expect(openInNapari).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('abandons an undispatched favorite after the chooser unmounts', async () => {
    vi.mocked(getViewerPreferences).mockRejectedValueOnce(new Error('Preferences temporarily unavailable'))
    const wrapper = mountChooser()
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    let finishPreferences!: (value: ViewerPreferencesSnapshot) => void
    vi.mocked(getViewerPreferences).mockReturnValueOnce(new Promise(resolve => { finishPreferences = resolve }))
    document.querySelector<HTMLButtonElement>('button[aria-label="Set Microscopy as favorite for this output"]')!.click()
    await flushPromises()
    wrapper.unmount()
    vi.mocked(toggleViewerFavorite).mockResolvedValue(preferences(4))
    finishPreferences(preferences(3))
    await flushPromises()
    expect(toggleViewerFavorite).not.toHaveBeenCalled()
    expect(openInNapari).not.toHaveBeenCalled()
  })

  it('keeps a replacement favorite action independent of an already dispatched toggle', async () => {
    const wrapper = mountChooser()
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    let finishOldToggle!: (value: ViewerPreferencesSnapshot) => void
    vi.mocked(toggleViewerFavorite).mockReturnValueOnce(new Promise(resolve => { finishOldToggle = resolve }))
    document.querySelector<HTMLButtonElement>('button[aria-label="Set Microscopy as favorite for this output"]')!.click()
    await flushPromises()
    expect(toggleViewerFavorite).toHaveBeenCalledOnce()
    const nextKey = { ...preferenceKey, output_key: 'next-output' }
    const nextIdentity = { ...identity, result_key: 'next-result' }
    vi.mocked(resolveNapariEnvironment).mockResolvedValue(response({ artifact_identity: nextIdentity, preference_key: nextKey, output_key: 'next-output' }))
    vi.mocked(getViewerPreferences).mockResolvedValue({ ...preferences(1), favorites: [{ key: preferenceKey, environment_id: response().effective_environment_id! }] })
    await wrapper.setProps({ resultIdentity: nextIdentity, outputKey: 'next-output' })
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-next-output"]').trigger('click')
    await flushPromises()
    const nextStar = document.querySelector<HTMLButtonElement>('button[aria-label="Set Microscopy as favorite for this output"]')!
    expect(nextStar.disabled).toBe(false)
    let finishNextToggle!: (value: ViewerPreferencesSnapshot) => void
    vi.mocked(toggleViewerFavorite).mockReturnValueOnce(new Promise(resolve => { finishNextToggle = resolve }))
    nextStar.click()
    await flushPromises()
    expect(toggleViewerFavorite).toHaveBeenNthCalledWith(2, { key: nextKey, environment_id: response().effective_environment_id, expected_revision: 1 })
    const resolvesBeforeOldCompletion = vi.mocked(resolveNapariEnvironment).mock.calls.length
    finishOldToggle(preferences(1, response().effective_environment_id!))
    await flushPromises()
    expect(resolveNapariEnvironment).toHaveBeenCalledTimes(resolvesBeforeOldCompletion)
    expect(nextStar.disabled).toBe(true)
    finishNextToggle({ ...preferences(2), favorites: [{ key: nextKey, environment_id: response().effective_environment_id! }] })
    await flushPromises()
    expect(document.querySelector<HTMLButtonElement>('button[aria-label="Unset favorite for this output"]')!.disabled).toBe(false)
    expect(openInNapari).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('refuses a withdrawn candidate callback even when the environment UUID survives', async () => {
    const wrapper = mountChooser()
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    const oldOpen = document.querySelector<HTMLButtonElement>('button[aria-label="Open once in Microscopy"]')!
    const nextIdentity = { ...identity, result_key: 'next-result' }
    vi.mocked(resolveNapariEnvironment).mockResolvedValue(response({ artifact_identity: nextIdentity,
      candidates: [{ ...response().candidates[0]!, reader_id: 'current-reader' }] }))
    await wrapper.setProps({ resultIdentity: nextIdentity })
    await flushPromises()
    oldOpen.click()
    await flushPromises()
    expect(openInNapari).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    document.querySelector<HTMLButtonElement>('button[aria-label="Open once in Microscopy"]')!.click()
    await flushPromises()
    expect(openInNapari).toHaveBeenCalledOnce()
    expect(openInNapari).toHaveBeenCalledWith(expect.objectContaining({ result_identity: nextIdentity, reader_id: 'current-reader' }))
    expect(toggleViewerFavorite).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('ignores a delayed resolver response after the captured result changes', async () => {
    let finishOld!: (value: NapariResolveResponse) => void
    const oldResponse = new Promise<NapariResolveResponse>(resolve => { finishOld = resolve })
    vi.mocked(resolveNapariEnvironment).mockReturnValueOnce(oldResponse)
    const wrapper = mountChooser()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    const nextIdentity = { ...identity, result_key: 'replacement-result' }
    vi.mocked(resolveNapariEnvironment).mockResolvedValue(response({
      artifact_identity: nextIdentity,
      candidates: [{ ...response().candidates[0]!, name: 'Current environment' }],
    }))
    await wrapper.setProps({ resultIdentity: nextIdentity })
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    const primary = wrapper.get('[data-testid="open-napari-42-labels"]')
    expect(primary.attributes('aria-label')).toBe('Open in Current environment')
    finishOld(response({ candidates: [{ ...response().candidates[0]!, name: 'Stale environment' }] }))
    await flushPromises()
    expect(primary.attributes('aria-label')).toBe('Open in Current environment')
    expect(resolveNapariEnvironment).toHaveBeenLastCalledWith(expect.objectContaining({ result_identity: nextIdentity }))
    expect(openInNapari).not.toHaveBeenCalled()
    expect(toggleViewerFavorite).not.toHaveBeenCalled()
    await primary.trigger('click')
    await flushPromises()
    expect(openInNapari).toHaveBeenCalledOnce()
    expect(openInNapari).toHaveBeenCalledWith(expect.objectContaining({ result_identity: nextIdentity }))
    wrapper.unmount()
  })

  it('exposes an explicit replace action scoped to the effective environment', async () => {
    const wrapper = mountChooser()
    await flushPromises()
    await wrapper.get('[data-testid="choose-napari-42-labels"]').trigger('click')
    await flushPromises()
    const replace = [...document.querySelectorAll<HTMLButtonElement>('button')]
      .find(button => button.textContent?.includes('Clear layers, then open'))!
    expect(replace.title).toContain('Clear all layers in Microscopy')
    replace.click()
    await flushPromises()

    expect(openInNapari).toHaveBeenCalledWith(expect.objectContaining({
      environment_id: response().effective_environment_id,
      clear_layers: true,
      result_identity: identity,
    }))
  })
})
