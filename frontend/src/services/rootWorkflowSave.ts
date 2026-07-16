import type { GraphState, WorkflowInfo } from '@/api/types'
import {
  getRootCanvasPersistenceResource,
  type RootCanvasPersistenceResource,
} from '@/composables/useCanvasPersistence'
import type { CanvasId } from '@/sessions/canvasSessionRegistry'
import { graphDocumentsEqual } from '@/sessions/graphDocument'
import { useUIStore } from '@/stores/ui'
import { useWorkflowStore } from '@/stores/workflow'

export interface RootWorkflowSaveTarget {
  canvasId: CanvasId
  workflowName: string
}

export type RootWorkflowSaveResult =
  | { status: 'saved'; info: WorkflowInfo; graph: GraphState }
  | { status: 'conflict' | 'unavailable' | 'newer-edit' }

function cloneGraph(graph: GraphState): GraphState {
  return JSON.parse(JSON.stringify(graph)) as GraphState
}

function targetIsAvailable(
  target: RootWorkflowSaveTarget,
  persistence: RootCanvasPersistenceResource,
): boolean {
  return getRootCanvasPersistenceResource(target.canvasId) === persistence
    && persistence.workflowId.value === target.workflowName
}

function captureNewerGraph(
  persistence: RootCanvasPersistenceResource,
  savedGraph: GraphState,
): GraphState | null {
  const latestGraph = cloneGraph(persistence.currentGraph.value)
  return graphDocumentsEqual(latestGraph, savedGraph) ? null : latestGraph
}

async function preserveNewerGraph(
  target: RootWorkflowSaveTarget,
  persistence: RootCanvasPersistenceResource,
  latestGraph: GraphState,
): Promise<void> {
  persistence.queueGraph(latestGraph)
  useUIStore().markCanvasDirty(target.canvasId)
  await persistence.flush()
}

export async function saveRootWorkflowTarget(
  target: RootWorkflowSaveTarget,
  initiatingGraph?: GraphState,
): Promise<RootWorkflowSaveResult> {
  const persistence = getRootCanvasPersistenceResource(target.canvasId)
  if (!persistence || !targetIsAvailable(target, persistence)) {
    return { status: 'unavailable' }
  }
  const graph = cloneGraph(initiatingGraph ?? persistence.currentGraph.value)
  const fresh = await persistence.ensureFreshForCriticalOperation()
  if (!targetIsAvailable(target, persistence)) return { status: 'unavailable' }
  if (!fresh) return { status: 'conflict' }

  const info = await useWorkflowStore().saveWorkflow(graph, target)
  if (!targetIsAvailable(target, persistence)) return { status: 'unavailable' }
  const newerGraphBeforeDraft = captureNewerGraph(persistence, graph)
  if (newerGraphBeforeDraft !== null) {
    await preserveNewerGraph(target, persistence, newerGraphBeforeDraft)
    return { status: 'newer-edit' }
  }

  persistence.queueDraft(graph)
  await persistence.flush()
  if (!targetIsAvailable(target, persistence)) return { status: 'unavailable' }
  const newerGraphAfterDraft = captureNewerGraph(persistence, graph)
  if (newerGraphAfterDraft !== null) {
    await preserveNewerGraph(target, persistence, newerGraphAfterDraft)
    return { status: 'newer-edit' }
  }

  useWorkflowStore().markClean(target.canvasId)
  return { status: 'saved', info, graph }
}
