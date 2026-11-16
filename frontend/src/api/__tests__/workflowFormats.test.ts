import { expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { acknowledgeWorkflowIdentityMigrations } from '../workflowFormats'

vi.mock('@/api/client', () => ({ api: { post: vi.fn() } }))

it('binds migration acknowledgment to its captured workspace', async () => {
  vi.mocked(api.post).mockResolvedValueOnce({ data: { notices: [] } })
  const body = { migration_id: 'sha256:receipt', entries: [] }
  await acknowledgeWorkflowIdentityMigrations(body, '/workspace/A')
  expect(api.post).toHaveBeenCalledWith('/api/v1/workflows/identity-migrations/ack', body, {
    headers: { 'X-BioImageFlow-Workspace': '/workspace/A' },
  })
})
