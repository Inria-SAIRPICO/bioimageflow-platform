import { api } from '@/api/client'
import type { WorkspaceInfo } from '@/api/types'

export async function getWorkspaceInfo(): Promise<WorkspaceInfo> {
  return (await api.get<WorkspaceInfo>('/api/v1/workspace')).data
}

export async function revealFilesystemPath(path: string): Promise<void> {
  await api.post('/api/v1/fs/reveal', { path })
}
