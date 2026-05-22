<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Menu from 'primevue/menu'
import Menubar from 'primevue/menubar'
import { useToast } from 'primevue/usetoast'
import type { MenuItem } from 'primevue/menuitem'
import { useUIStore, type ThemePreference } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useGraphSync } from '@/composables/useGraphSync'
import { useAutoSave } from '@/composables/useAutoSave'
import { useWorkflowStore, WorkflowConflictError } from '@/stores/workflow'
import { useWorkflowDraftStore } from '@/stores/workflowDraft'
import { useSettingsPanel } from '@/composables/useSettingsPanel'
import RunButton from '@/components/execution/RunButton.vue'
import ErrorIndicator from '@/components/layout/ErrorIndicator.vue'
import ErrorHistoryPanel from '@/components/layout/ErrorHistoryPanel.vue'
import DeleteWorkflowDialog from '@/components/workflow/DeleteWorkflowDialog.vue'
import MissingPackageDialog from '@/components/workflow/MissingPackageDialog.vue'
import OpenWorkflowDialog from '@/components/workflow/OpenWorkflowDialog.vue'
import WorkflowDialog from '@/components/workflow/WorkflowDialog.vue'
import type { GraphState, WorkflowInfo } from '@/api/types'

const uiStore = useUIStore()
const executionStore = useExecutionStore()
const workflowStore = useWorkflowStore()
const workflowDraftStore = useWorkflowDraftStore()
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

function workflowId(workflow: WorkflowInfo): string {
  return (workflow as WorkflowInfo & { id?: string | null }).id || workflow.name
}

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
const workflowDialogFolderId = ref<string | null>(null)
const openDialogVisible = ref(false)
const deleteDialogVisible = ref(false)
const discardDialogVisible = ref(false)
const aboutDialogVisible = ref(false)
const renameDialogVisible = ref(false)
const importRenameDialogVisible = ref(false)
const importRenameName = ref('')
const renameDisplayName = ref('')
const importFileInput = ref<HTMLInputElement | null>(null)
const pendingImportFile = ref<File | null>(null)
const dependencyDialogVisible = ref(false)
const pendingDiscardAction = ref<(() => void | Promise<void>) | null>(null)
const themeMenu = ref<{ toggle: (event: Event) => void } | null>(null)

const themePreferenceLabels: Record<ThemePreference, string> = {
  light: 'Light',
  dark: 'Dark',
  system: 'System',
}

const themeButtonLabel = computed(() => {
  const label = themePreferenceLabels[uiStore.themePreference]
  return uiStore.themePreference === 'system'
    ? `${label} (${themePreferenceLabels[uiStore.resolvedTheme]})`
    : label
})

const themeButtonIcon = computed(() => {
  if (uiStore.themePreference === 'system') return 'pi pi-desktop'
  return uiStore.themePreference === 'dark' ? 'pi pi-moon' : 'pi pi-sun'
})

const themeMenuItems = computed<MenuItem[]>(() => (
  (['light', 'dark', 'system'] as ThemePreference[]).map((preference) => ({
    label: themePreferenceLabels[preference],
    icon: uiStore.themePreference === preference ? 'pi pi-check' : undefined,
    command: () => uiStore.setThemePreference(preference),
  }))
))

type WorkflowPanelCommand = {
  action?: 'new' | 'save' | 'duplicate' | 'import' | 'export' | 'delete' | 'open'
  name?: string
  folderId?: string | null
}

function panelToggle(label: string, panelKey: keyof typeof uiStore.panels): MenuItem {
  return {
    label,
    icon: uiStore.panels[panelKey] ? 'pi pi-check' : undefined,
    command: () => uiStore.togglePanel(panelKey),
  }
}

function toggleThemeMenu(event: Event): void {
  themeMenu.value?.toggle(event)
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
      workflowName: workflowStore.currentName,
      workflowDisplayName: workflowStore.current?.display_name ?? workflowStore.currentName,
      missingTools: workflowStore.missingTools,
      dirty,
    },
  }))
}

async function loadWorkflowGraph(name: string): Promise<{ graph: GraphState; dirty: boolean }> {
  const savedGraph = await workflowStore.loadWorkflow(name)
  try {
    const draft = await workflowDraftStore.loadDraft(name)
    return { graph: draft.graph, dirty: draft.dirty_against_saved }
  } catch {
    return { graph: savedGraph, dirty: false }
  }
}

function showError(summary: string, err: unknown): void {
  const detail = err instanceof Error ? err.message : String(err)
  toast?.add({ severity: 'error', summary, detail })
}

function hasMissingImportDependencies(): boolean {
  return workflowStore.missingPackages.length > 0 || workflowStore.missingTools.length > 0
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

function workflowNameInDialogFolder(name: string): string {
  if (!workflowDialogFolderId.value || name.includes('/')) return name
  return `${workflowDialogFolderId.value}/${name}`
}

function createNewWorkflow(folderId: string | null = null): void {
  runAfterDiscard(() => {
    createIntent.value = 'new-empty'
    workflowDialogFolderId.value = folderId
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
      await workflowStore.createWorkflow({
        ...payload,
        name: workflowNameInDialogFolder(payload.name),
      })
      workflowDialogVisible.value = false
      workflowDialogSuggestedName.value = null
      workflowDialogFolderId.value = null
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
    workflowDialogFolderId.value = null
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
    const { graph, dirty } = await loadWorkflowGraph(name)
    openDialogVisible.value = false
    applyGraph(graph, dirty)
  } catch (err: unknown) {
    showError('Open workflow failed', err)
  }
}

async function saveWorkflow(): Promise<void> {
  if (!workflowStore.currentName) {
    createIntent.value = 'save-current'
    workflowDialogFolderId.value = null
    workflowDialogMode.value = 'new'
    workflowDialogInitialName.value = 'Untitled'
    workflowDialogInitialDisplayName.value = 'Untitled'
    workflowDialogSuggestedName.value = null
    workflowDialogVisible.value = true
    return
  }
  try {
    await workflowDraftStore.assertFreshForSaveOrRun()
    const info = await workflowStore.saveWorkflow(currentGraph.value)
    workflowDraftStore.scheduleSave(workflowId(info), currentGraph.value)
    await workflowDraftStore.flush()
    toast?.add({
      severity: 'success',
      summary: 'Workflow saved',
      detail: info.display_name,
      life: 2500,
    })
  } catch (err: unknown) {
    showError('Save workflow failed', err)
  }
}

async function exportCurrentWorkflow(): Promise<void> {
  const name = workflowStore.currentName
  if (!name) return
  try {
    await workflowDraftStore.assertFreshForSaveOrRun()
    await workflowStore.exportWorkflow(name)
  } catch (err: unknown) {
    showError('Export workflow failed', err)
  }
}

function chooseImportFile(): void {
  runAfterDiscard(() => {
    importFileInput.value?.click()
  })
}

async function openImportedWorkflow(name: string): Promise<void> {
  const { graph, dirty } = await loadWorkflowGraph(name)
  applyGraph(graph, dirty)
  if (hasMissingImportDependencies()) {
    dependencyDialogVisible.value = true
    return
  }
  toast?.add({
    severity: 'success',
    summary: 'Workflow imported',
    detail: workflowStore.current?.display_name ?? name,
    life: 2500,
  })
}

async function finishImport(file: File, nameOverride?: string): Promise<void> {
  const response = await workflowStore.importWorkflow(file, { nameOverride })
  await openImportedWorkflow(workflowId(response.info))
  pendingImportFile.value = null
}

async function onImportFileSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  pendingImportFile.value = file
  try {
    await finishImport(file)
  } catch (err: unknown) {
    if (err instanceof WorkflowConflictError && err.suggestedName) {
      importRenameName.value = err.suggestedName
      importRenameDialogVisible.value = true
      return
    }
    pendingImportFile.value = null
    showError('Import workflow failed', err)
  }
}

async function confirmImportRename(): Promise<void> {
  const file = pendingImportFile.value
  const nameOverride = importRenameName.value.trim()
  if (!file || !nameOverride) return
  try {
    await finishImport(file, nameOverride)
    importRenameDialogVisible.value = false
  } catch (err: unknown) {
    if (err instanceof WorkflowConflictError && err.suggestedName) {
      importRenameName.value = err.suggestedName
      toast?.add({
        severity: 'warn',
        summary: 'Workflow already exists',
        detail: `Suggested name: ${err.suggestedName}`,
        life: 5000,
      })
      return
    }
    pendingImportFile.value = null
    showError('Import workflow failed', err)
  }
}

async function rebindImportedDependencies(): Promise<void> {
  try {
    const graph = await workflowStore.rebindVersions()
    dependencyDialogVisible.value = false
    applyGraph(graph)
  } catch (err: unknown) {
    showError('Dependency rebind failed', err)
  }
}

function saveWorkflowAs(): void {
  workflowDialogFolderId.value = null
  workflowDialogMode.value = 'save-as'
  const baseName = workflowStore.currentName ?? 'Untitled'
  workflowDialogInitialName.value = `${baseName}_copy`
  workflowDialogInitialDisplayName.value = `${uiStore.activeWorkflowName ?? baseName} copy`
  workflowDialogSuggestedName.value = null
  workflowDialogVisible.value = true
}

async function duplicateWorkflowByName(name: string): Promise<void> {
  const source = workflowStore.workflows.find((workflow) => workflowId(workflow) === name)
  const displayName = `${source?.display_name ?? name} copy`
  try {
    const info = await workflowStore.patchWorkflow(name, {
      action: 'duplicate',
      new_name: `${name}_copy`,
      display_name: displayName,
      description: source?.description ?? null,
    })
    const { graph, dirty } = await loadWorkflowGraph(workflowId(info))
    applyGraph(graph, dirty)
  } catch (err: unknown) {
    showError('Duplicate workflow failed', err)
  }
}

async function exportWorkflowByName(name: string): Promise<void> {
  try {
    if (workflowStore.currentName === name) {
      await workflowDraftStore.assertFreshForSaveOrRun()
    }
    await workflowStore.exportWorkflow(name)
  } catch (err: unknown) {
    showError('Export workflow failed', err)
  }
}

async function deleteWorkflowByName(name: string): Promise<void> {
  const workflow = workflowStore.workflows.find((item) => workflowId(item) === name)
  const label = workflow?.display_name ?? name
  if (!window.confirm(`Delete workflow '${label}'?`)) return
  const wasCurrent = workflowStore.currentName === name
  try {
    await workflowStore.deleteWorkflow(name)
    if (wasCurrent) {
      const graph = { nodes: [], edges: [] }
      const names = new Set(workflowStore.workflows.map((item) => workflowId(item)))
      let nextName = 'Untitled'
      let suffix = 2
      while (names.has(nextName)) {
        nextName = `Untitled_${suffix}`
        suffix += 1
      }
      await workflowStore.createWorkflow({ name: nextName, display_name: nextName })
      applyGraph(graph)
    }
  } catch (err: unknown) {
    showError('Delete workflow failed', err)
  }
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
    deleteDialogVisible.value = false
    const graph = { nodes: [], edges: [] }
    const names = new Set(workflowStore.workflows.map((workflow) => workflowId(workflow)))
    let nextName = 'Untitled'
    let suffix = 2
    while (names.has(nextName)) {
      nextName = `Untitled_${suffix}`
      suffix += 1
    }
    await workflowStore.createWorkflow({ name: nextName, display_name: nextName })
    applyGraph(graph)
  } catch (err: unknown) {
    showError('Delete workflow failed', err)
  }
}

function onGlobalKeydown(event: KeyboardEvent): void {
  if (event.defaultPrevented) return
  const meta = event.metaKey || event.ctrlKey
  if (meta && event.key === 's') {
    event.preventDefault()
    if (!executionStore.isRunning) {
      void saveWorkflow()
    }
  }
}

function dispatchEditCommand(
  command: 'undo' | 'redo' | 'cut' | 'copy' | 'paste' | 'select-all',
): void {
  window.dispatchEvent(new CustomEvent('bioimageflow:edit-command', {
    detail: { command },
  }))
}

function editCommandDisabled(command: 'cut' | 'copy' | 'paste' | 'select-all' | 'undo' | 'redo'): boolean {
  if (executionStore.isRunning) return true
  if (command === 'cut' || command === 'copy') {
    return uiStore.selectedNodeIds.length === 0
  }
  return false
}

function openRenameDialog(): void {
  if (!workflowStore.currentName) return
  renameDisplayName.value = uiStore.activeWorkflowName || workflowStore.currentName
  renameDialogVisible.value = true
}

async function submitRename(): Promise<void> {
  if (!workflowStore.currentName) return
  const displayName = renameDisplayName.value.trim()
  if (!displayName) return
  try {
    await workflowStore.patchWorkflow(workflowStore.currentName, {
      action: 'update',
      display_name: displayName,
    })
    renameDialogVisible.value = false
  } catch (err: unknown) {
    showError('Rename workflow failed', err)
  }
}

function onBeforeUnload(): void {
  void autoSave.flushAutoSave()
}

function onWorkflowPanelCommand(event: Event): void {
  const detail = (event as CustomEvent<WorkflowPanelCommand>).detail
  const action = detail?.action
  if (!action) return
  if (action === 'new') {
    createNewWorkflow(detail.folderId ?? null)
  } else if (action === 'save') {
    void saveWorkflow()
  } else if (action === 'import') {
    chooseImportFile()
  } else if (action === 'open' && detail.name) {
    runAfterDiscard(() => onOpenWorkflow(detail.name as string))
  } else if (action === 'duplicate' && detail.name) {
    void duplicateWorkflowByName(detail.name)
  } else if (action === 'export' && detail.name) {
    void exportWorkflowByName(detail.name)
  } else if (action === 'delete' && detail.name) {
    void deleteWorkflowByName(detail.name)
  }
}

onMounted(() => {
  window.addEventListener('keydown', onGlobalKeydown)
  window.addEventListener('beforeunload', onBeforeUnload)
  window.addEventListener('bioimageflow:workflow-command', onWorkflowPanelCommand)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeydown)
  window.removeEventListener('beforeunload', onBeforeUnload)
  window.removeEventListener('bioimageflow:workflow-command', onWorkflowPanelCommand)
})

const menuItems = computed<MenuItem[]>(() => [
  {
    label: 'Workflow',
    items: [
      { label: 'New', icon: 'pi pi-plus', disabled: executionStore.isRunning, command: () => createNewWorkflow() },
      { label: 'Open', icon: 'pi pi-folder-open', disabled: executionStore.isRunning, command: openWorkflow },
      { label: 'Save', icon: 'pi pi-save', disabled: executionStore.isRunning, command: saveWorkflow },
      { label: 'Save As', icon: 'pi pi-copy', disabled: executionStore.isRunning, command: saveWorkflowAs },
      { label: 'Import', icon: 'pi pi-upload', disabled: executionStore.isRunning, command: chooseImportFile },
      { label: 'Export', icon: 'pi pi-download', disabled: executionStore.isRunning || !workflowStore.currentName, command: exportCurrentWorkflow },
      { label: 'Delete', icon: 'pi pi-trash', disabled: executionStore.isRunning || !workflowStore.currentName, command: deleteWorkflow },
    ],
  },
  {
    label: 'Edit',
    items: [
      { label: 'Undo', icon: 'pi pi-undo', disabled: editCommandDisabled('undo'), command: () => dispatchEditCommand('undo') },
      { label: 'Redo', icon: 'pi pi-refresh', disabled: editCommandDisabled('redo'), command: () => dispatchEditCommand('redo') },
      { separator: true },
      { label: 'Cut', icon: 'pi pi-clipboard', disabled: editCommandDisabled('cut'), command: () => dispatchEditCommand('cut') },
      { label: 'Copy', icon: 'pi pi-copy', disabled: editCommandDisabled('copy'), command: () => dispatchEditCommand('copy') },
      { label: 'Paste', icon: 'pi pi-clone', disabled: editCommandDisabled('paste'), command: () => dispatchEditCommand('paste') },
      { separator: true },
      { label: 'Select All', icon: 'pi pi-list-check', disabled: editCommandDisabled('select-all'), command: () => dispatchEditCommand('select-all') },
      { separator: true },
      {
        label: 'Preferences...',
        icon: 'pi pi-cog',
        command: () => useSettingsPanel().open(),
      },
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
      panelToggle('Workflows Panel', 'workflows'),
      panelToggle('Nodes', 'nodePanel'),
      panelToggle('Data Table', 'dataTable'),
      panelToggle('Logger', 'logger'),
      panelToggle('Code Editor', 'codeEditor'),
    ],
  },
  {
    label: 'Help',
    items: [{
      label: 'About',
      icon: 'pi pi-info-circle',
      command: () => {
        aboutDialogVisible.value = true
      },
    }],
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

const historyPanelOpen = ref(false)

function onHistoryNavigate(nodeId: string) {
  uiStore.setSelectedNodes([nodeId])
  historyPanelOpen.value = false
}

defineExpose({
  menuItems,
  historyPanelOpen,
  aboutDialogVisible,
  renameDialogVisible,
  importRenameDialogVisible,
  dependencyDialogVisible,
  themeButtonIcon,
  themeButtonLabel,
  themeMenuItems,
})
</script>

<template>
  <input
    ref="importFileInput"
    type="file"
    accept=".bioimageflow.zip,.zip,application/zip"
    hidden
    data-testid="workflow-import-input"
    @change="onImportFileSelected"
  >
  <Menubar :model="menuItems" data-testid="app-menubar">
    <template #end>
      <div class="workflow-actions">
        <span class="workflow-title" data-testid="workflow-title">
          {{ workflowTitle }}
        </span>
        <Button
          v-if="workflowStore.currentName"
          icon="pi pi-pencil"
          text
          rounded
          size="small"
          aria-label="Rename workflow"
          title="Rename workflow"
          data-testid="workflow-title-edit"
          :disabled="executionStore.isRunning"
          @click="openRenameDialog"
        />
        <ErrorIndicator @open="historyPanelOpen = true" />
        <Menu
          ref="themeMenu"
          :model="themeMenuItems"
          popup
        />
        <Button
          :icon="themeButtonIcon"
          text
          rounded
          size="small"
          :aria-label="`Theme: ${themeButtonLabel}`"
          :title="`Theme: ${themeButtonLabel}`"
          data-testid="theme-menu-button"
          @click="toggleThemeMenu"
        />
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
  <ErrorHistoryPanel
    :visible="historyPanelOpen"
    @update:visible="historyPanelOpen = $event"
    @navigate="onHistoryNavigate"
  />

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
    v-model:visible="dependencyDialogVisible"
    :packages="workflowStore.missingPackages"
    :tools="workflowStore.missingTools"
    @rebind="rebindImportedDependencies"
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

  <Dialog
    v-model:visible="renameDialogVisible"
    modal
    header="Rename workflow"
    :style="{ width: '380px' }"
    data-testid="rename-workflow-dialog"
  >
    <label class="rename-field">
      <span>Name</span>
      <InputText
        v-model="renameDisplayName"
        autofocus
        autocomplete="off"
        data-testid="rename-workflow-input"
        @keydown.enter="submitRename"
      />
    </label>
    <template #footer>
      <Button label="Cancel" text @click="renameDialogVisible = false" />
      <Button
        label="Save"
        icon="pi pi-check"
        :disabled="!renameDisplayName.trim()"
        data-testid="rename-workflow-submit"
        @click="submitRename"
      />
    </template>
  </Dialog>

  <Dialog
    v-model:visible="importRenameDialogVisible"
    modal
    header="Rename imported workflow"
    :style="{ width: '380px' }"
    data-testid="import-rename-dialog"
  >
    <label class="rename-field">
      <span>Name</span>
      <InputText
        v-model="importRenameName"
        autofocus
        autocomplete="off"
        data-testid="import-rename-input"
        @keydown.enter="confirmImportRename"
      />
    </label>
    <template #footer>
      <Button
        label="Cancel"
        text
        @click="importRenameDialogVisible = false; pendingImportFile = null"
      />
      <Button
        label="Import"
        icon="pi pi-check"
        :disabled="!importRenameName.trim()"
        data-testid="import-rename-submit"
        @click="confirmImportRename"
      />
    </template>
  </Dialog>

  <Dialog
    v-model:visible="aboutDialogVisible"
    modal
    header="About BioImageFlow"
    :style="{ width: '420px' }"
    data-testid="about-dialog"
  >
    <p class="about-copy">
      BioImageFlow is a desktop workflow editor for bioimage analysis pipelines.
    </p>
    <template #footer>
      <Button label="Close" text @click="aboutDialogVisible = false" />
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
.rename-field {
  display: grid;
  gap: 0.35rem;
}
.rename-field span {
  font-weight: 700;
}
.about-copy {
  margin: 0;
  color: var(--p-text-color);
}
</style>
