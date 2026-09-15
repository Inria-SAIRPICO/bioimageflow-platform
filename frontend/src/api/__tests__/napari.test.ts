import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { NapariStatus } from '../types'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

import { api } from '@/api/client'
import {
  addNapariFilenameRule, cancelManagedNapariOperation, createManagedNapariEnvironment,
  getManagedNapariOperation, getNapariStatus, getNapariViewingReadiness,
  getWorkflowViewingRequirements, launchNapariEnvironment, openInNapari, previewNapariFilename,
  replaceNapariFilenameRules, shutdownNapari,
} from '../napari'

const mockedGet = vi.mocked(api.get)
const mockedPost = vi.mocked(api.post)
const mockedPut = vi.mocked(api.put)

beforeEach(() => {
  mockedGet.mockReset()
  mockedPost.mockReset()
  mockedPut.mockReset()
})

describe('openInNapari', () => {
  it('posts the correct body shape', async () => {
    mockedPost.mockResolvedValue({ data: { status: 'ok' } })
    await openInNapari(['/tmp/a.tif'], false)
    expect(mockedPost).toHaveBeenCalledWith('/api/v1/napari/open', {
      paths: ['/tmp/a.tif'],
      clear_layers: false,
    })
  })

  it('passes clear_layers=true when requested', async () => {
    mockedPost.mockResolvedValue({ data: { status: 'ok' } })
    await openInNapari(['/tmp/a.tif'], true)
    const body = mockedPost.mock.calls[0][1] as { clear_layers: boolean }
    expect(body.clear_layers).toBe(true)
  })

  it('defaults clear_layers to false when not provided', async () => {
    mockedPost.mockResolvedValue({ data: { status: 'ok' } })
    await openInNapari(['/tmp/a.tif'])
    const body = mockedPost.mock.calls[0][1] as { clear_layers: boolean }
    expect(body.clear_layers).toBe(false)
  })

  it('throws on a 400 response (path not found)', async () => {
    mockedPost.mockRejectedValue({
      response: { status: 400, data: { error: 'path_not_found', detail: '/tmp/missing.tif' } },
    })
    await expect(openInNapari(['/tmp/missing.tif'])).rejects.toBeTruthy()
  })

  it('throws on a 503 response (launch failed)', async () => {
    mockedPost.mockRejectedValue({
      response: { status: 503, data: { error: 'napari_launch_failed', detail: 'solver crashed' } },
    })
    await expect(openInNapari(['/tmp/a.tif'])).rejects.toBeTruthy()
  })
})

describe('getNapariStatus', () => {
  it('GETs and returns the parsed NapariStatus', async () => {
    const status: NapariStatus = { running: true, env_path: '/envs/napari', pid: 4242 }
    mockedGet.mockResolvedValue({ data: status })
    const result = await getNapariStatus()
    expect(mockedGet).toHaveBeenCalledWith('/api/v1/napari/status')
    expect(result).toEqual(status)
  })

  it('parses running=false correctly', async () => {
    const status: NapariStatus = { running: false, env_path: null, pid: null }
    mockedGet.mockResolvedValue({ data: status })
    const result = await getNapariStatus()
    expect(result.running).toBe(false)
    expect(result.env_path).toBeNull()
    expect(result.pid).toBeNull()
  })
})

describe('shutdownNapari', () => {
  it('POSTs to /napari/shutdown', async () => {
    mockedPost.mockResolvedValue({ data: { status: 'ok' } })
    await shutdownNapari()
    expect(mockedPost).toHaveBeenCalledWith('/api/v1/napari/shutdown')
  })
})

describe('napari registry contracts', () => {
  it('preserves extension shorthand and ordered rule replacement bodies', async () => {
    mockedPost.mockResolvedValueOnce({ data: { revision: 2, rule: { id: 'r1', pattern: '*.tif' } } })
    await addNapariFilenameRule({ value: '.tif', mode: 'extension', environment_id: 'env-a', enabled: true, reader_id: null, expected_revision: 1 })
    expect(mockedPost).toHaveBeenCalledWith('/api/v1/napari/environment-settings/filename-rules', expect.objectContaining({ value: '.tif', mode: 'extension' }))

    mockedPut.mockResolvedValueOnce({ data: { revision: 3, environments: [], default_environment_id: null, filename_rules: [], operations: [] } })
    await replaceNapariFilenameRules({ rules: [], expected_revision: 2 })
    expect(mockedPut).toHaveBeenCalledWith('/api/v1/napari/environment-settings/filename-rules', { rules: [], expected_revision: 2 })
  })

  it('previews rules and routes managed operation create, poll, and cancel', async () => {
    mockedPost.mockResolvedValue({ data: { revision: 1, environment: null, operation: { id: 'op', environment_id: 'env', state: 'installing' } } })
    mockedGet.mockResolvedValue({ data: { revision: 1, environment: null, operation: { id: 'op', environment_id: 'env', state: 'completed' } } })
    await createManagedNapariEnvironment({ name: 'Tracking', recipe: { preset: 'default', requested_packages: ['track-reader>=1'] }, expected_revision: 0 })
    await getManagedNapariOperation('env', 'op')
    await cancelManagedNapariOperation('env', 'op')
    expect(mockedPost).toHaveBeenCalledWith('/api/v1/napari/environments/managed', expect.anything())
    expect(mockedGet).toHaveBeenCalledWith('/api/v1/napari/environments/env/operations/op')
    expect(mockedPost).toHaveBeenCalledWith('/api/v1/napari/environments/env/operations/op/cancel')

    mockedPost.mockResolvedValueOnce({ data: { filename: 'sample.tif', matching_rule_ids: ['r1'], winner_rule_id: 'r1' } })
    expect((await previewNapariFilename('sample.tif')).winner_rule_id).toBe('r1')
  })

  it('uses dedicated launch and passive readiness endpoints without probing or opening', async () => {
    mockedPost.mockResolvedValueOnce({ data: { status: 'launched' } })
    await launchNapariEnvironment('env')
    expect(mockedPost).toHaveBeenCalledWith('/api/v1/napari/launch', { environment_id: 'env' })

    const manifest = { schema: 'bioimageflow.viewing_requirements.v1' as const, complete: true, outputs: {} }
    mockedPost.mockResolvedValueOnce({ data: { manifest_schema: manifest.schema, manifest_complete: true, summary: { total_outputs: 0, covered_outputs: 0, not_covered_outputs: 0, unknown_outputs: 0, outputs_needing_setup: 0, message: 'No setup needed' }, outputs: [], groups: [] } })
    await getNapariViewingReadiness(manifest)
    expect(mockedPost).toHaveBeenCalledWith('/api/v1/napari/viewing-readiness', manifest)

    mockedGet.mockResolvedValueOnce({ data: manifest })
    await getWorkflowViewingRequirements('folder/workflow')
    expect(mockedGet).toHaveBeenCalledWith('/api/v1/workflows/folder/workflow/viewing-readiness')
  })
})
