import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useAutoSave, type AutoSaveEntry } from '@/composables/useAutoSave'
import { useWorkflowStore } from '@/stores/workflow'
import { useUIStore } from '@/stores/ui'
import { useSettingsStore } from '@/stores/settings'
import { getRootCanvasPersistenceResource } from '@/composables/useCanvasPersistence'
import { canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { fetchWorkflowDraft, putWorkflowDraft } from '@/api/workflowDrafts'
import { acknowledgeWorkflowIdentityMigrations } from '@/api/workflowFormats'
import type { WorkflowFormatStatus, WorkflowIdentityMigration } from '@/api/types'

export const useWorkflowRecoveryStore = defineStore('workflow-recovery', () => {
  const conflicts = ref<AutoSaveEntry[]>([])
  const status = ref<WorkflowFormatStatus | null>(null)
  const restoring = ref(false)
  const error = ref<string | null>(null)

  async function restore(entry: AutoSaveEntry, workflowId: string, explicit = true): Promise<void> {
    if (restoring.value) return
    restoring.value = true
    error.value = null
    try {
      const workflows = useWorkflowStore()
      const generation = workflows.captureWorkflowIdentity(workflowId)
      const workspaceSelection = useSettingsStore().workspaceSelectionRevision
      const workspace = workflows.workflows.find(info => info.id === workflowId)?.workspace_path ?? useSettingsStore().settings?.workspace_path
      const assertWorkspace = () => {
        if (useSettingsStore().workspaceSelectionRevision !== workspaceSelection) throw new Error('The workspace changed. Review the recovery destination again.')
      }
      const { withWorkflowMove } = await import('@/services/workflowMove')
      await withWorkflowMove([workflowId], async () => {
        const draft = await fetchWorkflowDraft(workflowId, workspace ?? undefined)
        assertWorkspace()
        workflows.assertWorkflowIdentityCurrent(workflowId, generation)
        if (!explicit && draft.dirty_against_saved && Date.parse(draft.updated_at) >= entry.timestamp) {
          throw new Error('The workflow has newer accepted edits. Choose explicitly whether to restore this recovery.')
        }
        const graph = { ...entry.graph }
        if (graph.name === entry.name && graph.name.includes('/')) graph.name = draft.graph.name
        const accepted = await putWorkflowDraft(workflowId, {
          graph, expected_revision: draft.draft_revision, updated_by: 'frontend',
        }, workspace ?? undefined)
        assertWorkspace()
        workflows.assertWorkflowIdentityCurrent(workflowId, generation)
        if (accepted.workflow_id !== workflowId) throw new Error('The recovery target changed. Review the current workflow and try again.')
        for (const canvasId of useUIStore().canvasIdsForWorkflow(workflowId)) {
          const resource = getRootCanvasPersistenceResource(canvasId)
          if (!resource) continue
          const registration = canvasSessionRegistry.get(canvasId)?.registrationToken
          resource.resolveFromDraft(accepted, 'external')
          await new Promise<void>((resolve, reject) => {
            const detail = { canvasId, draft: accepted, dirty: accepted.dirty_against_saved, handled: false, resolve, reject }
            window.dispatchEvent(new CustomEvent('bioimageflow:restore-saved-canvas', { detail }))
            if (!detail.handled) reject(new Error('The destination canvas is unavailable. The original recovery is retained.'))
          })
          if (canvasSessionRegistry.get(canvasId)?.registrationToken !== registration) throw new Error('The destination canvas changed. The original recovery is retained.')
        }
        assertWorkspace()
        const receipt = status.value
        const entries = receipt?.identity_migrations?.filter(mapping => mapping.old_path === entry.name
          && mapping.workflow_id === workflowId
          && (entry.identity_generation === undefined || mapping.identity_generation === entry.identity_generation)) ?? []
        if (receipt?.identity_migration_id && entries.length) {
          status.value = await acknowledgeWorkflowIdentityMigrations({ migration_id: receipt.identity_migration_id, entries })
        }
        const autoSave = useAutoSave()
        await autoSave.clearAutoSaveStrict(entry.name)
        await autoSave.setLastOpenedWorkflow(workflowId)
        conflicts.value = conflicts.value.filter(candidate => candidate.name !== entry.name)
      })
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause)
      throw cause
    } finally {
      restoring.value = false
    }
  }

  async function reconcile(next: WorkflowFormatStatus): Promise<void> {
    status.value = next
    const autoSave = useAutoSave()
    const entries = await autoSave.loadAutoSaves()
    const knownIds = new Set(useWorkflowStore().workflows.map(workflow => workflow.id ?? workflow.name))
    conflicts.value = []
    for (const entry of entries) {
      const mappings = (next.identity_migrations ?? []).filter((mapping: WorkflowIdentityMigration) => mapping.old_path === entry.name)
      if (knownIds.has(entry.name) && entry.workspace_path === next.workspace_path
        && entry.identity_generation === useWorkflowStore().workflowServerIdentityGeneration(entry.name)) continue
      const matching = mappings.filter(mapping => entry.workspace_path === next.workspace_path
        && entry.identity_generation === mapping.identity_generation)
      if (matching.length === 1 && knownIds.has(matching[0]!.workflow_id)) {
        try { await restore(entry, matching[0]!.workflow_id, false) } catch { conflicts.value.push(entry) }
      } else conflicts.value.push(entry)
    }
  }

  return { conflicts, restoring, error, restore, reconcile }
})
