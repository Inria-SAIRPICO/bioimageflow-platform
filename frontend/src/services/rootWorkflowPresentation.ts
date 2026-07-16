import type { GraphState, MissingTool, WorkflowInfo } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import { canvasIdFromPanelId } from '@/sessions/canvasSessionRegistry'
import { useWorkflowStore } from '@/stores/workflow'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import { workflowPanelId } from '@/utils/canvasPanels'

export interface RootWorkflowPresentation {
  graph: GraphState
  workflowName: string
  workflowDisplayName: string
  missingTools: MissingTool[]
  dirty: boolean
  draft?: WorkflowDraftResponse
  identityGeneration: number
  serverIdentityGeneration: number | null
}

const graphPresentationIdentities = new WeakMap<object, {
  workflowName: string
  identityGeneration: number
}>()

export function workflowInfoId(workflow: WorkflowInfo): string {
  return (workflow as WorkflowInfo & { id?: string | null }).id || workflow.name
}

export async function loadRootWorkflowPresentation(
  workflowName: string,
): Promise<RootWorkflowPresentation> {
  const workflowStore = useWorkflowStore()
  const identityGeneration = workflowStore.captureWorkflowIdentity(workflowName)
  const canvasId = canvasIdFromPanelId(workflowPanelId(workflowName))
  const savedGraph = await workflowStore.loadWorkflow(
    workflowName,
    canvasId,
    { rememberAsLastOpened: false },
  )
  const info = workflowStore.workflows.find(
    workflow => workflowInfoId(workflow) === workflowName,
  )
  const presentation = {
    workflowName: info ? workflowInfoId(info) : workflowName,
    workflowDisplayName: info?.display_name ?? workflowName,
    missingTools: [...workflowStore.missingTools],
    identityGeneration,
    serverIdentityGeneration: workflowStore.workflowServerIdentityGeneration(workflowName),
  }
  let result: RootWorkflowPresentation
  try {
    const draft = await useWorkflowDraftStore().loadDraft(workflowName)
    result = {
      graph: draft.graph,
      dirty: draft.dirty_against_saved,
      draft,
      ...presentation,
    }
  } catch {
    result = {
      graph: savedGraph,
      dirty: false,
      ...presentation,
    }
  }
  workflowStore.assertWorkflowIdentityCurrent(workflowName, identityGeneration)
  graphPresentationIdentities.set(result.graph, { workflowName, identityGeneration })
  return result
}

export function isRootWorkflowPresentationCurrent(
  workflowName: string,
  graph: GraphState,
  identityGeneration?: number,
): boolean {
  const workflowStore = useWorkflowStore()
  if (workflowStore.isWorkflowDeletionInFlight(workflowName)) return false
  const tracked = graphPresentationIdentities.get(graph)
  if (identityGeneration === undefined) return false
  if (
    tracked !== undefined
    && (
      tracked.workflowName !== workflowName
      || tracked.identityGeneration !== identityGeneration
    )
  ) return false
  return workflowStore.isWorkflowIdentityCurrent(workflowName, identityGeneration)
}
