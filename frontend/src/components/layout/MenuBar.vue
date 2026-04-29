<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Menubar from 'primevue/menubar'
import { useToast } from 'primevue/usetoast'
import type { MenuItem } from 'primevue/menuitem'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useGraphSync } from '@/composables/useGraphSync'
import { useAutoSave } from '@/composables/useAutoSave'
import { useWorkflowStore, WorkflowConflictError } from '@/stores/workflow'
import RunButton from '@/components/execution/RunButton.vue'
import DeleteWorkflowDialog from '@/components/workflow/DeleteWorkflowDialog.vue'
import MissingPackageDialog from '@/components/workflow/MissingPackageDialog.vue'
import OpenWorkflowDialog from '@/components/workflow/OpenWorkflowDialog.vue'
import WorkflowDialog from '@/components/workflow/WorkflowDialog.vue'
import type { GraphState } from '@/api/types'

const uiStore = useUIStore()
const executionStore = useExecutionStore()
const workflowStore = useWorkflowStore()
const autoSave = useAutoSave()
const { flushNow, validationResult, isPending, currentGraph } = useGraphSync()

// useToast throws when no ToastService is provided (e.g. in unit tests
// that mount MenuBar in isolation). The toasts are a nice-to-have here.
let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}

const runButtonRef = useTemplateRef<InstanceType<typeof RunButton> | null>(
  'runButtonRef',
)

const graphSync = { flushNow, validationResult }
const workflowTitle = computed(() => {
  const label = uiStore.activeWorkflowName ?? 'No workflow'
  return uiStore.hasUnsavedChanges ? `${label} *` : label
})
const workflowDialogVisible = ref(false)
const workflowDialogMode = ref<'new' | 'save-as'>('new')
const workflowDialogInitialName = ref('')
const workflowDialogInitialDisplayName = ref('')
const workflowDialogSuggestedName = ref<string | null>(null)
const createIntent = ref<'new-empty' | 'save-current'>('new-empty')
const openDialogVisible = ref(false)
const deleteDialogVisible = ref(false)
const missingDialogVisible = ref(false)
const discardDialogVisible = ref(false)
const pendingDiscardAction = ref<(() => void | Promise<void>) | null>(null)

function panelToggle(label: string, panelKey: keyof typeof uiStore.panels): MenuItem {
  return {
    label,
    icon: uiStore.panels[panelKey] ? 'pi pi-check' : undefined,
    command: () => uiStore.togglePanel(panelKey),
  }
}

function runDisabledReason(): string | null {
  if (executionStore.isRunning) return 'Execution in progress'
  if (isPending.value) return 'Waiting for validation…'
  return null
}

function applyGraph(graph: GraphState, dirty = false): void {
  window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
    detail: {
      graph,
      missingTools: workflowStore.missingTools,
      dirty,
    },
  }))
}

function showError(summary: string, err: unknown): void {
  const detail = err instanceof Error ? err.message : String(err)
  toast?.add({ severity: 'error', summary, detail })
}

function runAfterDiscard(action: () => void | Promise<void>): void {
  if (!uiStore.hasUnsavedChanges) {
    void action()
    return
  }
  pendingDiscardAction.value = action
  discardDialogVisible.value = true
}

async function confirmDiscard(): Promise<void> {
  const action = pendingDiscardAction.value
  pendingDiscardAction.value = null
  discardDialogVisible.value = false
  if (action) {
    await action()
  }
}

function createNewWorkflow(): void {
  runAfterDiscard(() => {
    createIntent.value = 'new-empty'
    workflowDialogMode.value = 'new'
    workflowDialogInitialName.value = 'Untitled'
    workflowDialogInitialDisplayName.value = 'Untitled'
    workflowDialogSuggestedName.value = null
    workflowDialogVisible.value = true
  })
}

async function onWorkflowDialogSubmit(payload: {
  name: string
  display_name: string
  description: string | null
}): Promise<void> {
  try {
    if (workflowDialogMode.value === 'new') {
      await workflowStore.createWorkflow(payload)
      workflowDialogVisible.value = false
      workflowDialogSuggestedName.value = null
      if (createIntent.value === 'save-current') {
        await workflowStore.saveWorkflow(currentGraph.value)
      } else {
        applyGraph({ nodes: [], edges: [] })
      }
      return
    }

    if (workflowStore.currentName) {
      await workflowStore.patchWorkflow(workflowStore.currentName, {
        action: 'duplicate',
        new_name: payload.name,
        display_name: payload.display_name,
        description: payload.description,
      })
    } else {
      await workflowStore.createWorkflow(payload)
    }
    await workflowStore.saveWorkflow(currentGraph.value)
    workflowDialogVisible.value = false
    workflowDialogSuggestedName.value = null
  } catch (err: unknown) {
    if (err instanceof WorkflowConflictError && err.suggestedName) {
      workflowDialogSuggestedName.value = err.suggestedName
      toast?.add({
        severity: 'warn',
        summary: 'Workflow already exists',
        detail: `Suggested name: ${err.suggestedName}`,
        life: 5000,
      })
      return
    }
    showError('Workflow action failed', err)
  }
}

async function openWorkflow(): Promise<void> {
  runAfterDiscard(async () => {
    try {
      await workflowStore.fetchWorkflows()
      openDialogVisible.value = true
    } catch (err: unknown) {
      showError('Open workflow failed', err)
    }
  })
}

async function onOpenWorkflow(name: string): Promise<void> {
  try {
    const graph = await workflowStore.loadWorkflow(name)
    openDialogVisible.value = false
    applyGraph(graph)
  } catch (err: unknown) {
    showError('Open workflow failed', err)
  }
}

async function saveWorkflow(): Promise<void> {
  if (!workflowStore.currentName) {
    createIntent.value = 'save-current'
    workflowDialogMode.value = 'new'
    workflowDialogInitialName.value = 'Untitled'
    workflowDialogInitialDisplayName.value = 'Untitled'
    workflowDialogSuggestedName.value = null
    workflowDialogVisible.value = true
    return
  }
  try {
    await workflowStore.saveWorkflow(currentGraph.value)
    toast?.add({
      severity: 'success',
      summary: 'Workflow saved',
      detail: workflowStore.currentName,
      life: 2500,
    })
  } catch (err: unknown) {
    showError('Save workflow failed', err)
  }
}

function saveWorkflowAs(): void {
  workflowDialogMode.value = 'save-as'
  const baseName = workflowStore.currentName ?? 'Untitled'
  workflowDialogInitialName.value = `${baseName}_copy`
  workflowDialogInitialDisplayName.value = `${uiStore.activeWorkflowName ?? baseName} copy`
  workflowDialogSuggestedName.value = null
  workflowDialogVisible.value = true
}

function deleteWorkflow(): void {
  const name = workflowStore.currentName
  if (!name) return
  deleteDialogVisible.value = true
}

async function confirmDeleteWorkflow(): Promise<void> {
  const name = workflowStore.currentName
  if (!name) return
  try {
    await workflowStore.deleteWorkflow(name)
    const graph = { nodes: [], edges: [] }
    const names = new Set(workflowStore.workflows.map((workflow) => workflow.name))
    let nextName = 'Untitled'
    let suffix = 2
    while (names.has(nextName)) {
      nextName = `Untitled_${suffix}`
      suffix += 1
    }
    await workflowStore.createWorkflow({ name: nextName, display_name: nextName })
    deleteDialogVisible.value = false
    applyGraph(graph)
  } catch (err: unknown) {
    showError('Delete workflow failed', err)
  }
}

async function rebindVersions(): Promise<void> {
  try {
    const graph = await workflowStore.rebindVersions()
    missingDialogVisible.value = false
    applyGraph(graph)
  } catch (err: unknown) {
    showError('Rebind versions failed', err)
  }
}

function onGlobalKeydown(event: KeyboardEvent): void {
  const meta = event.metaKey || event.ctrlKey
  if (meta && event.key === 's') {
    event.preventDefault()
    if (!executionStore.isRunning) {
      void saveWorkflow()
    }
  }
}

function onBeforeUnload(): void {
  void autoSave.flushAutoSave()
}

onMounted(() => {
  window.addEventListener('keydown', onGlobalKeydown)
  window.addEventListener('beforeunload', onBeforeUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
  window.removeEventListener('beforeunload', onBeforeUnload)
})

const menuItems = computed<MenuItem[]>(() => [
  {
    label: 'Workflow',
    items: [
      { label: 'New', icon: 'pi pi-plus', disabled: executionStore.isRunning, command: createNewWorkflow },
      { label: 'Open', icon: 'pi pi-folder-open', disabled: executionStore.isRunning, command: openWorkflow },
      { label: 'Save', icon: 'pi pi-save', disabled: executionStore.isRunning, command: saveWorkflow },
      { label: 'Save As', disabled: executionStore.isRunning, command: saveWorkflowAs },
      { label: 'Delete', icon: 'pi pi-trash', disabled: executionStore.isRunning || !workflowStore.currentName, command: deleteWorkflow },
      {
        label: 'Dependencies',
        icon: 'pi pi-box',
        disabled: workflowStore.missingPackages.length === 0 && workflowStore.missingTools.length === 0,
        command: () => {
          missingDialogVisible.value = true
        },
      },
      {
        label: 'Use Installed Versions',
        icon: 'pi pi-refresh',
        disabled: executionStore.isRunning || workflowStore.missingPackages.length === 0,
        command: rebindVersions,
      },
    ],
  },
  {
    label: 'Edit',
    items: [
      { label: 'Undo', icon: 'pi pi-undo', disabled: true },
      { label: 'Redo', icon: 'pi pi-refresh', disabled: true },
      { separator: true },
      { label: 'Cut', icon: 'pi pi-clipboard', disabled: true },
      { label: 'Copy', icon: 'pi pi-copy', disabled: true },
      { label: 'Paste', disabled: true },
      { separator: true },
      { label: 'Select All', disabled: true },
    ],
  },
  {
    label: 'Execution',
    items: [
      {
        label: 'Run Workflow',
        icon: 'pi pi-play',
        disabled: runDisabledReason() !== null,
        command: () => runButtonRef.value?.onRun(),
      },
      {
        label: 'Run Selected',
        icon: 'pi pi-forward',
        disabled:
          runDisabledReason() !== null || uiStore.selectedNodeIds.length === 0,
        command: () => runButtonRef.value?.onRunSelected(),
      },
      {
        label: 'Stop',
        icon: 'pi pi-stop',
        disabled: !executionStore.isRunning,
        command: () => runButtonRef.value?.onStop(),
      },
    ],
  },
  {
    label: 'View',
    items: [
      panelToggle('Tools Panel', 'tools'),
      panelToggle('Nodes', 'nodePanel'),
      panelToggle('Data Table', 'dataTable'),
      panelToggle('Logger', 'logger'),
    ],
  },
  {
    label: 'Help',
    items: [{ label: 'About', disabled: true }],
  },
])

function onRunButtonToast(payload: {
  severity: 'warn' | 'error'
  summary: string
  detail?: string
}) {
  if (!toast) return
  // Errors stay open until the user dismisses them (so they have time to
  // read a multi-line validation summary); warnings auto-dismiss.
  toast.add({
    severity: payload.severity,
    summary: payload.summary,
    detail: payload.detail,
    life: payload.severity === 'error' ? undefined : 5000,
  })
}

defineExpose({ menuItems })
</script>

<template>
  <Menubar :model="menuItems" data-testid="app-menubar">
    <template #end>
      <div class="workflow-actions">
        <span class="workflow-title" data-testid="workflow-title">
          {{ workflowTitle }}
        </span>
        <RunButton
          ref="runButtonRef"
          :graph="currentGraph"
          :graph-sync="graphSync"
          :sync-pending="isPending"
          @toast="onRunButtonToast"
        />
      </div>
    </template>
  </Menubar>

  <WorkflowDialog
    v-model:visible="workflowDialogVisible"
    :mode="workflowDialogMode"
    :initial-name="workflowDialogInitialName"
    :initial-display-name="workflowDialogInitialDisplayName"
    :suggested-name="workflowDialogSuggestedName"
    @submit="onWorkflowDialogSubmit"
  />

  <OpenWorkflowDialog
    v-model:visible="openDialogVisible"
    :workflows="workflowStore.workflows"
    :current-name="workflowStore.currentName"
    @open="onOpenWorkflow"
  />

  <DeleteWorkflowDialog
    v-model:visible="deleteDialogVisible"
    :workflow="workflowStore.current"
    @confirm="confirmDeleteWorkflow"
  />

  <MissingPackageDialog
    v-model:visible="missingDialogVisible"
    :packages="workflowStore.missingPackages"
    :tools="workflowStore.missingTools"
    @rebind="rebindVersions"
  />

  <Dialog
    v-model:visible="discardDialogVisible"
    modal
    header="Discard unsaved changes?"
    :style="{ width: '420px' }"
    data-testid="discard-workflow-dialog"
  >
    <p>
      This workflow has unsaved edits. Opening another workflow or creating a
      new one will leave those edits only in browser auto-save.
    </p>
    <template #footer>
      <Button label="Cancel" text @click="discardDialogVisible = false" />
      <Button
        label="Discard and continue"
        severity="danger"
        data-testid="discard-workflow-confirm"
        @click="confirmDiscard"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.workflow-actions {
  align-items: center;
  display: flex;
  gap: 0.75rem;
}
.workflow-title {
  color: var(--text-color-secondary);
  font-size: 0.875rem;
  white-space: nowrap;
}
</style>
