import { useAutoSave, type AutoSaveEntry } from '@/composables/useAutoSave'
import { useWorkflowStore } from '@/stores/workflow'
import {
  loadRootWorkflowPresentation,
  workflowInfoId,
  type RootWorkflowPresentation,
} from './rootWorkflowPresentation'

function newestPersistedTimestamp(
  presentation: RootWorkflowPresentation,
  savedModified: string | undefined,
): number {
  const savedTimestamp = Date.parse(savedModified ?? '')
  const draftTimestamp = Date.parse(presentation.draft?.updated_at ?? '')
  return Math.max(
    Number.isFinite(savedTimestamp) ? savedTimestamp : 0,
    Number.isFinite(draftTimestamp) ? draftTimestamp : 0,
  )
}

async function applyFreshRecovery(
  presentation: RootWorkflowPresentation,
  recovery: AutoSaveEntry | null,
  savedModified: string | undefined,
): Promise<RootWorkflowPresentation> {
  if (recovery?.name !== presentation.workflowName) return presentation
  const persistedTimestamp = newestPersistedTimestamp(presentation, savedModified)
  if (persistedTimestamp !== 0 && recovery.timestamp <= persistedTimestamp) {
    await useAutoSave().clearAutoSave(recovery.name)
    return presentation
  }
  return {
    ...presentation,
    graph: recovery.graph,
    dirty: true,
  }
}

export async function resolveStartupWorkflow(): Promise<RootWorkflowPresentation | null> {
  const workflowStore = useWorkflowStore()
  const autoSave = useAutoSave()
  await workflowStore.fetchWorkflowTree().catch(() => workflowStore.fetchWorkflows())

  const orderedIds = workflowStore.flattenedWorkflows.map(workflowInfoId)
  const knownIds = new Set(orderedIds)
  let recovery = await autoSave.loadMostRecentAutoSave()
  const lastOpened = await autoSave.getLastOpenedWorkflow()

  if (recovery !== null && !knownIds.has(recovery.name)) {
    await autoSave.clearAutoSave(recovery.name)
    recovery = null
  }
  if (lastOpened !== null && !knownIds.has(lastOpened)) {
    await autoSave.setLastOpenedWorkflow(null)
  }

  const candidates = [
    recovery?.name,
    knownIds.has(lastOpened ?? '') ? lastOpened : null,
    ...orderedIds,
  ].filter((id): id is string => typeof id === 'string' && id.length > 0)

  for (const workflowName of [...new Set(candidates)]) {
    try {
      const presentation = await loadRootWorkflowPresentation(workflowName)
      const info = workflowStore.workflows.find(
        workflow => workflowInfoId(workflow) === workflowName,
      )
      return applyFreshRecovery(presentation, recovery, info?.last_modified)
    } catch {
      if (recovery?.name === workflowName) {
        await autoSave.clearAutoSave(workflowName)
        recovery = null
      }
      if (lastOpened === workflowName) {
        await autoSave.setLastOpenedWorkflow(null)
      }
    }
  }

  return null
}
