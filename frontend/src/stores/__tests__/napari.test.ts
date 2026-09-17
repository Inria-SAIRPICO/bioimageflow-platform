import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import { api } from '@/api/client'
import { useNapariStore, type NapariOpenPayload } from '@/stores/napari'

const payload: NapariOpenPayload = {
  paths: ['/tmp/image.tif'],
  clear_layers: false,
  node_id: 'node-1',
  row: 0,
  col: 'image',
  workflow_name: null,
}

describe('napari store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.post).mockReset()
    vi.mocked(api.get).mockReset()
    vi.mocked(api.put).mockReset()
    vi.mocked(api.patch).mockReset()
    vi.mocked(api.delete).mockReset()
  })

  it('keeps progress visible until opening completes', async () => {
    let resolveRequest!: () => void
    vi.mocked(api.post).mockReturnValueOnce(new Promise((resolve) => {
      resolveRequest = () => resolve({ data: { status: 'ok' } })
    }))
    const napari = useNapariStore()

    const request = napari.open(payload)

    expect(napari.requestPending).toBe(true)
    expect(napari.phase).toBe('opening')
    expect(api.post).toHaveBeenCalledWith('/api/v1/napari/open', payload)

    resolveRequest()
    await request

    expect(napari.requestPending).toBe(false)
    expect(napari.phase).toBeNull()
  })

  it('clears progress when opening fails', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new Error('launch failed'))
    const napari = useNapariStore()

    await expect(napari.open(payload)).rejects.toThrow('launch failed')

    expect(napari.requestPending).toBe(false)
    expect(napari.phase).toBeNull()
  })

  it('deduplicates one environment while another environment remains responsive', async () => {
    const releases: Array<() => void> = []
    vi.mocked(api.post).mockImplementation(() => new Promise((resolve) => {
      releases.push(() => resolve({ data: { status: 'ok' } }))
    }))
    const napari = useNapariStore()
    const environmentA = { ...payload, environment_id: '68ff94c5-b649-4dc5-9d98-605e82736e3b' }
    const environmentB = { ...payload, environment_id: '0767ed99-f301-445a-8c31-c75462303fde' }

    const first = napari.open(environmentA)
    await napari.open(environmentA)
    const second = napari.open(environmentB)

    expect(api.post).toHaveBeenCalledTimes(2)
    expect(napari.environmentState(environmentA.environment_id).pending).toBe(true)
    expect(napari.environmentState(environmentB.environment_id).pending).toBe(true)
    releases.forEach(release => release())
    await Promise.all([first, second])
    expect(napari.requestPending).toBe(false)
  })

  it('distinguishes environment installation from opening and requests Logger', () => {
    const napari = useNapariStore()
    napari.requestPending = true

    napari.applyEnvironmentStatus({ env_name: 'napari', status: 'creating' })

    expect(napari.phase).toBe('installing')
    expect(napari.loggerActivationRequest).toBe(1)

    napari.applyEnvironmentStatus({ env_name: 'napari', status: 'opening' })

    expect(napari.phase).toBe('opening')
    expect(napari.loggerActivationRequest).toBe(2)
  })

  it('does not request Logger for a terminal running status', () => {
    const napari = useNapariStore()

    napari.applyEnvironmentStatus({ env_name: 'napari', status: 'running' })

    expect(napari.loggerActivationRequest).toBe(0)
  })

  it('tracks concurrent opens independently across environments', async () => {
    const resolvers: Array<() => void> = []
    vi.mocked(api.post).mockImplementation(() => new Promise((resolve) => {
      resolvers.push(() => resolve({ data: { status: 'ok' } }))
    }))
    const napari = useNapariStore()
    const first = napari.open({ ...payload, environment_id: 'env-a' })
    const second = napari.open({ ...payload, environment_id: 'env-b' })

    expect(api.post).toHaveBeenCalledTimes(2)
    expect(napari.environmentState('env-a').pending).toBe(true)
    expect(napari.environmentState('env-b').pending).toBe(true)

    resolvers[0]!()
    await first
    expect(napari.environmentState('env-a').pending).toBe(false)
    expect(napari.environmentState('env-b').pending).toBe(true)
    resolvers[1]!()
    await second
    expect(napari.requestPending).toBe(false)
  })

  it('attributes lifecycle events to the addressed environment', () => {
    const napari = useNapariStore()
    napari.applyEnvironmentStatus({ environment_id: 'env-a', request_id: 'a1', status: 'opening' })
    napari.applyEnvironmentStatus({ environment_id: 'env-b', request_id: 'b1', status: 'opening' })
    napari.applyEnvironmentStatus({ environment_id: 'env-a', request_id: 'a1', status: 'running' })

    expect(napari.environmentState('env-a').pending).toBe(false)
    expect(napari.environmentState('env-b').pending).toBe(true)
  })

  it('applies registry mutations with the current revision', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        revision: 3,
        environment: { id: 'env-a', name: 'Tracking' },
      },
    })
    const napari = useNapariStore()
    napari.revision = 2

    await napari.registerEnvironment({ name: 'Tracking', path: '/envs/tracking' })

    expect(api.post).toHaveBeenCalledWith('/api/v1/napari/environments', {
      name: 'Tracking', path: '/envs/tracking', expected_revision: 2,
    })
    expect(napari.revision).toBe(3)
    expect(napari.environments[0]?.name).toBe('Tracking')
  })

  it('launches an empty viewer through the dedicated endpoint then refreshes status', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { status: 'launched' } })
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        environment_id: 'env-a', environment_name: 'Tracking',
        installation_identity: 'identity', status: 'running', running: true,
        env_path: '/envs/tracking', pid: 42,
      },
    })
    const napari = useNapariStore()

    await napari.launchEmpty('env-a')

    expect(api.post).toHaveBeenCalledWith('/api/v1/napari/launch', { environment_id: 'env-a' })
    expect(api.get).toHaveBeenCalledWith('/api/v1/napari/status', { params: { environment_id: 'env-a' } })
    expect(napari.environmentState('env-a').status).toBe('running')
  })

  it('keeps filename-rule order backend-authoritative', async () => {
    const rules = [
      { id: 'specific', pattern: '*_labels.tif', environment_id: 'env-a', enabled: true, reader_id: null },
      { id: 'general', pattern: '*.tif', environment_id: 'env-a', enabled: true, reader_id: null },
    ]
    vi.mocked(api.put).mockResolvedValueOnce({
      data: { revision: 6, environments: [], default_environment_id: null, filename_rules: rules, operations: [] },
    })
    const napari = useNapariStore()
    napari.revision = 5

    await napari.replaceFilenameRules(rules)

    expect(api.put).toHaveBeenCalledWith('/api/v1/napari/environment-settings/filename-rules', {
      rules, expected_revision: 5,
    })
    expect(napari.filenameRules.map(rule => rule.id)).toEqual(['specific', 'general'])
  })

  it('deduplicates resumed polling for a durable managed operation', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({
        data: { revision: 2, environment: null, operation: { id: 'op-a', environment_id: 'env-a', kind: 'create', state: 'completed', progress: 100, message: 'Ready', error: null } },
      })
      .mockResolvedValueOnce({
        data: { revision: 2, environments: [], default_environment_id: null, filename_rules: [], operations: [] },
      })
    const napari = useNapariStore()

    await Promise.all([
      napari.watchOperation('env-a', 'op-a'),
      napari.watchOperation('env-a', 'op-a'),
    ])

    expect(vi.mocked(api.get).mock.calls.filter(([url]) => String(url).includes('/operations/'))).toHaveLength(1)
  })

  it('retains a saved workflow manifest and refetches it after inventory changes', async () => {
    const manifest = { schema: 'bioimageflow.viewing_requirements.v1' as const, complete: true, outputs: {} }
    const report = {
      manifest_schema: manifest.schema, manifest_complete: true,
      summary: { total_outputs: 0, covered_outputs: 0, not_covered_outputs: 0, unknown_outputs: 0, outputs_needing_setup: 0, message: 'No declared requirements' },
      outputs: [], groups: [],
    }
    vi.mocked(api.get).mockResolvedValue({ data: manifest })
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: report })
      .mockResolvedValueOnce({ data: { revision: 2, environment: { id: 'env-a', name: 'Tracking' } } })
      .mockResolvedValueOnce({ data: report })
    const napari = useNapariStore()
    napari.revision = 1

    await napari.evaluateWorkflowReadiness('folder/workflow')
    await napari.probeEnvironment('env-a')

    expect(api.get).toHaveBeenCalledTimes(2)
    expect(api.get).toHaveBeenCalledWith('/api/v1/workflows/folder/workflow/viewing-readiness')
    expect(api.post).toHaveBeenCalledWith('/api/v1/napari/viewing-readiness', manifest)
    expect(napari.viewingWorkflowId).toBe('folder/workflow')
    expect(napari.viewingReadiness?.summary.message).toBe('No declared requirements')
  })
})
