import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'
import { getWorkspaceInfo, revealFilesystemPath } from '@/api/workspace'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

describe('workspace API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('returns the server-resolved workspace', async () => {
    const workspace = {
      workspace_path: '/Users/me/BioImageFlow/workspace',
      workflows_root: '/Users/me/BioImageFlow/workspace/workflows',
      tools_root: '/Users/me/BioImageFlow/workspace/tools',
      outputs_root: '/Users/me/BioImageFlow/workspace/outputs',
      deployment_mode: 'desktop' as const,
      user_editable: true,
    }
    vi.mocked(api.get).mockResolvedValueOnce({ data: workspace })

    await expect(getWorkspaceInfo()).resolves.toEqual(workspace)
    expect(api.get).toHaveBeenCalledWith('/api/v1/workspace')
  })

  it('reveals a path through the backend filesystem API', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { status: 'ok' } })

    await revealFilesystemPath('/Users/me/bioimageflow_data')

    expect(api.post).toHaveBeenCalledWith('/api/v1/fs/reveal', {
      path: '/Users/me/bioimageflow_data',
    })
  })
})
