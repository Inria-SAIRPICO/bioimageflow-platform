import { api } from './client'
import type { FijiOpenRequest } from './types'

export async function openInFiji(request: FijiOpenRequest): Promise<void> {
  await api.post('/api/v1/fiji/open', request)
}
