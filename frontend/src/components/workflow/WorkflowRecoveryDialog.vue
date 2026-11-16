<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { useWorkflowStore, workflowRelativePath } from '@/stores/workflow'
import { useWorkflowRecoveryStore } from '@/stores/workflowRecovery'
import { getWorkflowFormatStatus } from '@/api/workflowFormats'
import { loadRootWorkflowPresentation } from '@/services/rootWorkflowPresentation'
import { useAutoSave } from '@/composables/useAutoSave'

const workflows = useWorkflowStore()
const recovery = useWorkflowRecoveryStore()
const visible = ref(false)
const selectedSource = ref('')
const selectedTarget = ref('')
let pending: Promise<void> | null = null

function refresh(): Promise<void> {
  if (pending) return pending
  pending = (async () => {
    if ((await useAutoSave().loadAutoSaves()).length === 0) return
    await workflows.fetchWorkflowTree()
    await recovery.reconcile(await getWorkflowFormatStatus())
  })().catch(() => { /* Ordinary catalog/format errors retain their existing UI. */ }).finally(() => { pending = null })
  return pending
}

watch(() => recovery.conflicts, entries => {
  if (!entries.some(entry => entry.name === selectedSource.value)) selectedSource.value = entries[0]?.name ?? ''
}, { immediate: true })

onMounted(() => {
  void refresh()
  window.addEventListener('bioimageflow:reconcile-workflow-recovery', refresh)
})
onUnmounted(() => window.removeEventListener('bioimageflow:reconcile-workflow-recovery', refresh))

async function restore(): Promise<void> {
  const source = recovery.conflicts.find(entry => entry.name === selectedSource.value)
  if (!source || !selectedTarget.value || recovery.restoring) return
  try {
    await recovery.restore(source, selectedTarget.value)
    const loaded = await loadRootWorkflowPresentation(selectedTarget.value)
    window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', { detail: { ...loaded } }))
    if (recovery.conflicts.length === 0) visible.value = false
  } catch { /* Keep the source and its actionable error available for retry. */ }
}
</script>

<template>
  <div v-if="recovery.conflicts.length" class="workflow-recovery-notice" role="status" data-testid="workflow-recovery-conflict">
    Some browser edits need a workflow destination before they can be recovered.
    <Button label="Review recovery" text @click="visible = true" />
  </div>
  <Dialog v-model:visible="visible" modal header="Recover workflow edits" :closable="!recovery.restoring" :style="{ width: '34rem' }" data-testid="workflow-recovery-dialog">
    <p>The original browser snapshot will remain available until these edits are accepted as an unsaved workflow draft.</p>
    <label for="workflow-recovery-source">Browser snapshot</label>
    <select id="workflow-recovery-source" v-model="selectedSource" :disabled="recovery.restoring" data-testid="workflow-recovery-source">
      <option v-for="entry in recovery.conflicts" :key="entry.name" :value="entry.name">{{ entry.graph.display_name }} — {{ entry.name }}</option>
    </select>
    <label for="workflow-recovery-target">Restore into workflow</label>
    <select id="workflow-recovery-target" v-model="selectedTarget" :disabled="recovery.restoring" data-testid="workflow-recovery-target">
      <option value="" disabled>Choose a workflow</option>
      <option v-for="workflow in workflows.workflows" :key="workflow.id ?? workflow.name" :value="workflow.id ?? workflow.name">{{ workflow.display_name }} — {{ workflowRelativePath(workflow) }}</option>
    </select>
    <p>This replaces the selected workflow's current draft. Its saved workflow remains unchanged until you choose Save.</p>
    <p v-if="recovery.error" role="alert">{{ recovery.error }}</p>
    <template #footer>
      <Button label="Cancel" text :disabled="recovery.restoring" @click="visible = false" />
      <Button label="Restore as unsaved draft" :disabled="!selectedSource || !selectedTarget || recovery.restoring" @click="restore" data-testid="workflow-recovery-restore" />
    </template>
  </Dialog>
</template>

<style scoped>
.workflow-recovery-notice { padding: 0.4rem 1rem; background: var(--p-yellow-100); color: var(--p-yellow-950); }
label, select { display: block; width: 100%; margin-top: 0.75rem; }
</style>
