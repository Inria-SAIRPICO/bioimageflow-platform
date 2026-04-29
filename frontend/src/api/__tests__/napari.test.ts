import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { NapariStatus } from '../types'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

import { api } from '@/api/client'
import { openInNapari, getNapariStatus, shutdownNapari } from '../napari'

const mockedGet = vi.mocked(api.get)
const mockedPost = vi.mocked(api.post)

beforeEach(() => {
  mockedGet.mockReset()
  mockedPost.mockReset()
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
