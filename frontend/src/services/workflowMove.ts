import { useCanvasLifecycleStore } from '@/stores/canvasLifecycle'
import { useNestedWorkflowSessionsStore } from '@/stores/nestedWorkflowSessions'
import { useUIStore } from '@/stores/ui'
import { getRootCanvasPersistenceResource } from '@/composables/useCanvasPersistence'
import { flushRetainedNestedSnapshot } from '@/composables/useGraphSync'
import { canvasIdFromPanelId, canvasSessionRegistry, type CanvasId } from '@/sessions/canvasSessionRegistry'

/** Persist private editing state without promoting Save or applying a child. */
export async function withWorkflowMove<T>(workflowIds: string[], move: () => Promise<T>): Promise<T> {
  const ui = useUIStore()
  const lifecycle = useCanvasLifecycleStore()
  const nested = useNestedWorkflowSessionsStore().sessions.filter(session => (
    session.parentWorkflowName !== null && workflowIds.includes(session.parentWorkflowName)
  ))
  const roots = [...new Set(workflowIds.flatMap(id => ui.canvasIdsForWorkflow(id)))]
  const canvases = [...new Set<CanvasId>([
    ...roots,
    ...nested.map(session => canvasIdFromPanelId(`nested-workflow:${encodeURIComponent(session.id)}`)),
  ])].filter(id => canvasSessionRegistry.get(id) !== null)
  const captured = canvases.map(id => ({ id, token: canvasSessionRegistry.get(id)!.registrationToken }))
  const owned: CanvasId[] = []
  try {
    for (const { id } of captured) {
      if (!lifecycle.begin(id, 'moving')) throw new Error('An affected workflow is busy. Try moving it again after its current operation finishes.')
      owned.push(id)
    }
    for (const id of roots) {
      const resource = getRootCanvasPersistenceResource(id)
      if (resource && !await resource.ensureFreshForCriticalOperation()) {
        throw new Error('Resolve the workflow draft conflict before moving it.')
      }
    }
    for (const session of nested) await flushRetainedNestedSnapshot(session.id)
    for (const { id, token } of captured) {
      if (canvasSessionRegistry.get(id)?.registrationToken !== token) {
        throw new Error('An affected canvas changed while preparing the move. Try again.')
      }
    }
    return await move()
  } finally {
    for (const id of owned) lifecycle.finish(id)
  }
}
