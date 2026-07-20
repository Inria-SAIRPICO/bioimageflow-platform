import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import {
  getDemoWorkflowsStatus,
  installDemoWorkflows,
} from '@/api/demoWorkflows'

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

const status = {
  bundle_version: 1,
  status: 'missing' as const,
  workflows: [],
  can_install: true,
  can_remove: false,
}

describe('demo workflow API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads derived installation status', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: status } as never)

    await expect(getDemoWorkflowsStatus()).resolves.toEqual(status)
    expect(api.get).toHaveBeenCalledWith('/api/v1/demo-workflows')
  })

  it('installs missing bundled workflows', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: status } as never)

    await expect(installDemoWorkflows()).resolves.toEqual(status)
    expect(api.post).toHaveBeenCalledWith('/api/v1/demo-workflows/install')
  })
})
