import type { NestedWorkflowSession } from '@/stores/nestedWorkflowSessions'
import { canvasIdFromPanelId, type CanvasId } from './canvasSessionRegistry'

export interface NestedExecutionScope {
  rootCanvasId: CanvasId
  workflowId: string | null
  path: string[]
  sessions: NestedWorkflowSession[]
}

/** Resolve a private editor to the instance path used by root execution results. */
export function resolveNestedExecutionScope(
  sessionId: string,
  sessions: readonly NestedWorkflowSession[],
): NestedExecutionScope | null {
  const byId = new Map(sessions.map(session => [session.id, session]))
  const chain: NestedWorkflowSession[] = []
  const visited = new Set<string>()
  let current = byId.get(sessionId)
  while (current) {
    if (visited.has(current.id)) return null
    visited.add(current.id)
    chain.unshift(current)
    if (current.owner.kind === 'root') {
      if (!current.owner.canvas_id) return null
      return {
        rootCanvasId: canvasIdFromPanelId(current.owner.canvas_id),
        workflowId: current.owner.workflow_id ?? null,
        path: chain.map(session => session.parentNodeId),
        sessions: chain,
      }
    }
    current = current.owner.session_id
      ? byId.get(current.owner.session_id)
      : undefined
  }
  return null
}

export function scopedExecutionNodeId(
  scope: NestedExecutionScope | null,
  nodeId: string,
): string {
  return scope ? [...scope.path, nodeId].join('/') : nodeId
}
