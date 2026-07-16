import { api } from '@/api/client'
import type {
  NestedSnapshotOwner,
  NestedWorkflowSnapshotOpenRequest,
  NestedWorkflowSnapshotPutRequest,
  NestedWorkflowSnapshotResponse,
} from '@/api/types'

export type {
  NestedSnapshotOwner,
  NestedWorkflowSnapshotOpenRequest,
  NestedWorkflowSnapshotPutRequest,
  NestedWorkflowSnapshotResponse,
} from '@/api/types'

function snapshotUrl(sessionId: string): string {
  return `/api/v1/nested-workflow-snapshots/${encodeURIComponent(sessionId)}`
}

export async function openNestedWorkflowSnapshot(
  body: NestedWorkflowSnapshotOpenRequest,
  signal?: AbortSignal,
): Promise<NestedWorkflowSnapshotResponse> {
  const { data } = await api.post<NestedWorkflowSnapshotResponse>(
    '/api/v1/nested-workflow-snapshots/open',
    body,
    { signal },
  )
  return data
}

export async function getNestedWorkflowSnapshot(
  sessionId: string,
  signal?: AbortSignal,
): Promise<NestedWorkflowSnapshotResponse> {
  const { data } = await api.get<NestedWorkflowSnapshotResponse>(
    snapshotUrl(sessionId),
    { signal },
  )
  return data
}

export async function putNestedWorkflowSnapshot(
  sessionId: string,
  body: NestedWorkflowSnapshotPutRequest,
  signal?: AbortSignal,
): Promise<NestedWorkflowSnapshotResponse> {
  const { data } = await api.put<NestedWorkflowSnapshotResponse>(
    snapshotUrl(sessionId),
    body,
    { signal },
  )
  return data
}

export async function deleteNestedWorkflowSnapshot(
  sessionId: string,
  expectedRevision: number,
  signal?: AbortSignal,
): Promise<void> {
  await api.delete(snapshotUrl(sessionId), {
    params: { expected_revision: expectedRevision },
    signal,
  })
}
