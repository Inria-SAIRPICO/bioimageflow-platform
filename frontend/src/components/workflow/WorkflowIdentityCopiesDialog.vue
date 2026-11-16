<script setup lang="ts">
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { api } from '@/api/client'
import { getWorkflowFormatStatus } from '@/api/workflowFormats'
import type { WorkflowFormatStatus, WorkflowIdentityCopyResolve, WorkflowInfo } from '@/api/types'
import { canvasSessionRegistry } from '@/sessions/canvasSessionRegistry'
import { useNestedWorkflowSessionsStore } from '@/stores/nestedWorkflowSessions'
import { useUIStore } from '@/stores/ui'
import { useWorkflowStore } from '@/stores/workflow'
import { useSettingsStore } from '@/stores/settings'
import { apiErrorMessage } from '@/utils/apiError'

const props = defineProps<{ status: WorkflowFormatStatus | null }>()
const emit = defineEmits<{ resolved: [status: WorkflowFormatStatus] }>()
const ui = useUIStore()
const workflows = useWorkflowStore()
const nested = useNestedWorkflowSessionsStore()
const visible = ref(false)
const selectedPath = ref('')
const busy = ref(false)
const error = ref<string | null>(null)
const conflicts = computed(() => props.status?.identity_conflicts ?? [])
const copies = computed(() => conflicts.value.flatMap(conflict => conflict.copies.map(copy => ({ ...copy, workflowId: conflict.workflow_id }))))
const selected = computed(() => copies.value.find(copy => copy.relative_path === selectedPath.value))
const openEditors = computed(() => {
  void canvasSessionRegistry.sessionCount.value
  const id = selected.value?.workflowId
  return id !== undefined && (ui.canvasIdsForWorkflow(id).some(canvasId => canvasSessionRegistry.get(canvasId) !== null)
    || nested.sessions.some(session => session.parentWorkflowName === id))
})

async function resolveCopy(): Promise<void> {
  const copy = selected.value
  const workspace = props.status?.workspace_path
  if (!copy || !workspace || busy.value || openEditors.value) return
  busy.value = true
  error.value = null
  const workspaceSelection = useSettingsStore().workspaceSelectionRevision
  const assertWorkspace = () => {
    if (useSettingsStore().workspaceSelectionRevision !== workspaceSelection) throw new Error('The workspace changed. Review copies in the current workspace before continuing.')
  }
  try {
    const request: WorkflowIdentityCopyResolve = {
      relative_path: copy.relative_path,
      expected_workflow_id: copy.workflowId,
      expected_document_hash: copy.document_hash,
    }
    await api.post<WorkflowInfo>('/api/v1/workflows/identity-copies/resolve', request, { headers: { 'X-BioImageFlow-Workspace': workspace } })
    assertWorkspace()
    const next = await getWorkflowFormatStatus(workspace)
    assertWorkspace()
    await workflows.fetchWorkflowTree({ fresh: true })
    assertWorkspace()
    emit('resolved', next)
    selectedPath.value = ''
    if (!next.identity_conflicts?.length) visible.value = false
  } catch (cause) {
    error.value = apiErrorMessage(cause)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="conflicts.length" role="alert" class="workflow-copies-notice" data-testid="workflow-identity-copies-warning">
    Copied workflow directories share an identity and need review before they can be opened.
    <Button label="Review copies" text @click="visible = true" />
  </div>
  <Dialog v-model:visible="visible" modal header="Review workflow copies" :closable="!busy" :style="{ width: '34rem' }" data-testid="workflow-identity-copies-dialog">
    <label for="workflow-identity-copy-path">Directory to make independent</label>
    <select id="workflow-identity-copy-path" v-model="selectedPath" :disabled="busy" data-testid="workflow-identity-copy-path">
      <option value="" disabled>Choose a copied workflow directory</option>
      <option v-for="copy in copies" :key="copy.relative_path" :value="copy.relative_path">{{ copy.relative_path }}</option>
    </select>
    <p>The selected directory receives a new workflow identity. Its graph, tools, drafts and results stay in place. Other directories remain unchanged.</p>
    <p v-if="openEditors" role="alert" data-testid="workflow-identity-copy-open-editors">Close the affected workflow and nested-workflow tabs before resolving copies.</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template #footer>
      <Button label="Cancel" text :disabled="busy" @click="visible = false" />
      <Button label="Make selected copy independent" :disabled="!selected || !status?.workspace_path || openEditors || busy" data-testid="workflow-identity-copy-resolve" @click="resolveCopy" />
    </template>
  </Dialog>
</template>

<style scoped>
.workflow-copies-notice { padding: 0.5rem; background: var(--p-yellow-100); color: var(--p-yellow-950); }
label, select { display: block; width: 100%; margin-top: 0.75rem; }
</style>
