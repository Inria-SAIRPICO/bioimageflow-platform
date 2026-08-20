import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../client', () => ({ api: { post: vi.fn() } }))

import { api } from '../client'
import { openInFiji } from '../fiji'

describe('Fiji API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('opens one workflow result image by identity', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { status: 'ok' } })

    await openInFiji({
      node_id: 'segment',
      row: 2,
      col: 'mask',
      workflow_name: 'analysis',
    })

    expect(api.post).toHaveBeenCalledWith('/api/v1/fiji/open', {
      node_id: 'segment',
      row: 2,
      col: 'mask',
      workflow_name: 'analysis',
    })
  })
})
