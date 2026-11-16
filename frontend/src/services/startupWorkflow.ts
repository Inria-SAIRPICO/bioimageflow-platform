import { useAutoSave, type AutoSaveEntry } from '@/composables/useAutoSave'
import { useWorkflowStore } from '@/stores/workflow'
import type { WorkflowInfo } from '@/api/types'
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
  info: WorkflowInfo | undefined,
): Promise<RootWorkflowPresentation> {
  if (recovery?.name !== presentation.workflowName) return presentation
  if (!recovery.recovery_key) return presentation
  if (!recovery.workspace_path || recovery.workspace_path !== info?.workspace_path
    || recovery.identity_generation === undefined || recovery.identity_generation !== info.identity_generation) return presentation
  const persistedTimestamp = newestPersistedTimestamp(presentation, info.last_modified)
  if (persistedTimestamp !== 0 && recovery.timestamp <= persistedTimestamp) {
    await useAutoSave().clearAutoSaveEntryStrict(recovery)
    return presentation
  }
  // Older creation canvases used the workspace path as the definition name.
  // Restore that field from backend authority while retaining queued edits.
  const recoveredGraph = recovery.graph.name.includes('/')
    ? { ...recovery.graph, name: presentation.graph.name }
    : recovery.graph
  return {
    ...presentation,
    graph: recoveredGraph,
    dirty: true,
  }
}

/** Explicit Open must retain the recovery that a superseded startup would use. */
export async function loadRootWorkflowForOpen(workflowName: string): Promise<RootWorkflowPresentation> {
  const presentation = await loadRootWorkflowPresentation(workflowName)
  const info = useWorkflowStore().workflows.find(
    workflow => workflowInfoId(workflow) === workflowName,
  )
  const recovery = info?.workspace_path && info.identity_generation !== undefined
    ? await useAutoSave().loadAutoSave(workflowName, { workspace_path: info.workspace_path, identity_generation: info.identity_generation })
    : null
  const result = await applyFreshRecovery(presentation, recovery, info)
  useWorkflowStore().assertWorkflowIdentityCurrent(workflowName, presentation.identityGeneration)
  return result
}

export async function resolveStartupWorkflow(
  options: { canPresent?: () => boolean } = {},
): Promise<RootWorkflowPresentation | null> {
  const workflowStore = useWorkflowStore()
  const autoSave = useAutoSave()
  await workflowStore.fetchWorkflowTree().catch(() => workflowStore.fetchWorkflows())

  const orderedIds = workflowStore.flattenedWorkflows.map(workflowInfoId)
  const knownIds = new Set(orderedIds)
  let recovery = await autoSave.loadMostRecentAutoSave()
  const lastOpened = await autoSave.getLastOpenedWorkflow()

  if (recovery !== null && (!knownIds.has(recovery.name) || !recovery.recovery_key)) {
    // A legacy path or missing UUID is not proof that recovery may be deleted.
    // The recovery dialog retains it for explicit owner resolution.
    recovery = null
  }
  if (lastOpened !== null && !knownIds.has(lastOpened)) {
    await autoSave.setLastOpenedWorkflow(null)
  }

  const candidates = [
    knownIds.has(lastOpened ?? '') ? lastOpened : null,
    ...orderedIds,
  ].filter((id): id is string => typeof id === 'string' && id.length > 0)

  for (const workflowName of [...new Set(candidates)]) {
    try {
      const presentation = await loadRootWorkflowPresentation(workflowName, {
        background: true, canPresent: options.canPresent ?? (() => true),
      })
      const info = workflowStore.workflows.find(
        workflow => workflowInfoId(workflow) === workflowName,
      )
      const ownedRecovery = recovery?.name === workflowName && recovery.workspace_path === info?.workspace_path
        && recovery.identity_generation === info?.identity_generation ? recovery
        : info?.workspace_path && info.identity_generation !== undefined
          ? await autoSave.loadAutoSave(workflowName, { workspace_path: info.workspace_path, identity_generation: info.identity_generation })
          : null
      return applyFreshRecovery(presentation, ownedRecovery, info)
    } catch {
      if (recovery?.name === workflowName) {
        recovery = null
      }
      if (lastOpened === workflowName) {
        await autoSave.setLastOpenedWorkflow(null)
      }
    }
  }

  return null
}
