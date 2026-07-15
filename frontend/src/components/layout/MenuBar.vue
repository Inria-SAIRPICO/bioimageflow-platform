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
import { useCanvasPersistence } from '@/composables/useCanvasPersistence'
import { useCanvasCommands } from '@/composables/useCanvasCommands'
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
import type { GraphState, MissingTool, WorkflowInfo } from '@/api/types'
import type { WorkflowDraftResponse } from '@/api/workflowDrafts'
import {
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'

const uiStore = useUIStore()
const executionStore = useExecutionStore()
const workflowStore = useWorkflowStore()
const workflowDraftStore = useWorkflowDraftStore()
const autoSave = useAutoSave()
const { flushNow, validationResult, isPending, currentGraph } = useGraphSync()
const canvasPersistence = useCanvasPersistence()
const canvasCommands = useCanvasCommands()

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

const graphSync = { flushNow, validationResult, currentGraph }

function workflowId(workflow: WorkflowInfo): string {
  return (workflow as WorkflowInfo & { id?: string | null }).id || workflow.name
}

const workflowTitle = computed(() => {
  const label = uiStore.activeWorkflowName ?? 'No workflow'
  return uiStore.hasUnsavedChanges ? `${label} *` : label
})
const activeWorkflowId = computed(() => {
  if (uiStore.activeWorkflowId !== null) return uiStore.activeWorkflowId
  return canvasSessionRegistry.sessionCount.value === 0
    ? workflowStore.currentName
    : null
})
const activeWorkflow = computed(() => {
  const id = activeWorkflowId.value
  if (!id) return null
  return workflowStore.workflows.find((workflow) => workflowId(workflow) === id) ?? (
    workflowStore.currentName === id ? workflowStore.current : null
  )
})
const workflowDialogVisible = ref(false)
const workflowDialogMode = ref<'new' | 'save-as'>('new')
const workflowDialogInitialName = ref('')
const workflowDialogInitialDisplayName = ref('')
const workflowDialogInitialDescription = ref<string | null>(null)
const workflowDialogSuggestedName = ref<string | null>(null)
const createIntent = ref<'new-empty' | 'save-current'>('new-empty')
const workflowDialogFolderId = ref<string | null>(null)
const openDialogVisible = ref(false)
const deleteDialogVisible = ref(false)
const deleteTargetName = ref<string | null>(null)
const deleteDialogWorkflow = computed(() => {
  const name = deleteTargetName.value ?? activeWorkflowId.value
  if (!name) return null
  return workflowStore.workflows.find((workflow) => workflowId(workflow) === name) ?? (
    workflowStore.currentName === name ? workflowStore.current : null
  )
})
const discardDialogVisible = ref(false)
const exportSaveDialogVisible = ref(false)
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
const workflowDialogTarget = ref<{
  canvasId: CanvasId | null
  workflowName: string
  graph: GraphState
  missingTools: MissingTool[]
} | null>(null)
const renameTarget = ref<WorkflowSaveTarget | null>(null)
const deleteCanvasTarget = ref<WorkflowSaveTarget | null>(null)

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
  if (executionStore.isStarting) return 'Execution is starting'
  if (executionStore.isStopping) return 'Execution is stopping'
  if (executionStore.isRunning) return 'Execution in progress'
  if (isPending.value) return 'Waiting for validation…'
  if (!activeWorkflowId.value) return 'Open or save a workflow before running'
  return null
}

function applyGraph(
  graph: GraphState,
  dirty = false,
  presentation?: {
    workflowName: string
    workflowDisplayName: string
    missingTools: MissingTool[]
    draft?: WorkflowDraftResponse
  },
): void {
  if (executionStore.isMutationLocked) return
  window.dispatchEvent(new CustomEvent('bioimageflow:apply-graph', {
    detail: {
      graph,
      workflowName: presentation?.workflowName ?? workflowStore.currentName,
      workflowDisplayName: presentation?.workflowDisplayName
        ?? workflowStore.current?.display_name
        ?? workflowStore.currentName,
      missingTools: presentation?.missingTools ?? workflowStore.missingTools,
      dirty,
      draft: presentation?.draft,
    },
  }))
}

async function loadWorkflowGraph(name: string): Promise<{
  graph: GraphState
  dirty: boolean
  workflowName: string
  workflowDisplayName: string
  missingTools: MissingTool[]
  draft?: WorkflowDraftResponse
}> {
  const savedGraph = await workflowStore.loadWorkflow(name)
  const info = workflowStore.workflows.find((workflow) => workflowId(workflow) === name)
  const presentation = {
    workflowName: info ? workflowId(info) : name,
    workflowDisplayName: info?.display_name ?? name,
    missingTools: [...workflowStore.missingTools],
  }
  try {
    const draft = await workflowDraftStore.loadDraft(name)
    return {
      graph: draft.graph,
      dirty: draft.dirty_against_saved,
      draft,
      ...presentation,
    }
  } catch {
    return { graph: savedGraph, dirty: false, ...presentation }
  }
}

function showError(summary: string, err: unknown): void {
  const detail = err instanceof Error ? err.message : String(err)
  toast?.add({ severity: 'error', summary, detail })
}

function showDraftConflictWarning(action: 'saving' | 'running' | 'exporting' = 'saving'): void {
  toast?.add({
    severity: 'warn',
    summary: 'Resolve workflow changes first',
    detail: `This workflow changed outside the canvas. Choose which version to keep before ${action}.`,
    life: 5000,
  })
}

function hasMissingImportDependencies(): boolean {
  return workflowStore.missingPackages.length > 0 || workflowStore.missingTools.length > 0
}

function runAfterDiscard(action: () => void | Promise<void>): void {
  if (executionStore.isMutationLocked) return
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
  if (executionStore.isMutationLocked) return
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
    workflowDialogInitialDescription.value = null
    workflowDialogSuggestedName.value = null
    workflowDialogVisible.value = true
  })
}

async function onWorkflowDialogSubmit(payload: {
  name: string
  display_name: string
  description: string | null
}): Promise<void> {
  if (executionStore.isMutationLocked) return
  try {
    if (workflowDialogMode.value === 'new') {
      const info = await workflowStore.createWorkflow({
        ...payload,
        name: workflowNameInDialogFolder(payload.name),
      })
      workflowDialogVisible.value = false
      workflowDialogSuggestedName.value = null
      workflowDialogFolderId.value = null
      if (createIntent.value === 'save-current') {
        await workflowStore.saveWorkflow(currentGraph.value)
      } else {
        applyGraph({ nodes: [], edges: [] }, false, {
          workflowName: workflowId(info),
          workflowDisplayName: info.display_name,
          missingTools: [],
        })
      }
      return
    }

    const target = workflowDialogTarget.value
    if (!target) return
    const info = await workflowStore.patchWorkflow(target.workflowName, {
      action: 'duplicate',
      new_name: payload.name,
      display_name: payload.display_name,
      description: payload.description,
    })
    const copiedWorkflowName = workflowId(info)
    if (target.canvasId === null) {
      await workflowStore.saveWorkflow(target.graph)
    } else {
      await workflowStore.saveWorkflow(target.graph, {
        canvasId: target.canvasId,
        workflowName: copiedWorkflowName,
      })
      applyGraph(target.graph, false, {
        workflowName: copiedWorkflowName,
        workflowDisplayName: info.display_name,
        missingTools: target.missingTools,
      })
    }
    workflowDialogVisible.value = false
    workflowDialogTarget.value = null
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
  if (executionStore.isMutationLocked) return
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
  if (executionStore.isMutationLocked) return
  try {
    const loaded = await loadWorkflowGraph(name)
    if (executionStore.isMutationLocked) return
    openDialogVisible.value = false
    applyGraph(loaded.graph, loaded.dirty, loaded)
  } catch (err: unknown) {
    showError('Open workflow failed', err)
  }
}

interface WorkflowSaveTarget {
  canvasId: CanvasId | null
  workflowName: string | null
}

function currentSaveTarget(): WorkflowSaveTarget {
  return {
    canvasId: canvasPersistence.canvasId,
    workflowName: activeWorkflowId.value,
  }
}

function isSaveTargetActive(target: WorkflowSaveTarget): boolean {
  return canvasPersistence.canvasId === target.canvasId
    && activeWorkflowId.value === target.workflowName
}

async function saveCurrentWorkflowGraph(options: {
  showSuccessToast?: boolean
  conflictAction?: 'saving' | 'exporting'
} = {}, target = currentSaveTarget()): Promise<WorkflowInfo | null> {
  const fresh = await canvasPersistence.ensureFreshForCriticalOperation()
  if (!isSaveTargetActive(target)) return null
  if (!fresh) {
    showDraftConflictWarning(options.conflictAction ?? 'saving')
    return null
  }
  if (!target.workflowName) return null
  const graph = currentGraph.value
  const info = target.canvasId === null
    ? await workflowStore.saveWorkflow(graph)
    : await workflowStore.saveWorkflow(graph, {
        canvasId: target.canvasId,
        workflowName: target.workflowName,
      })
  if (!isSaveTargetActive(target)) return null
  canvasPersistence.queueDraft(graph)
  await canvasPersistence.flush()
  if (!isSaveTargetActive(target)) return null
  if (options.showSuccessToast !== false) {
    toast?.add({
      severity: 'success',
      summary: 'Workflow saved',
      detail: info.display_name,
      life: 2500,
    })
  }
  return info
}

async function saveWorkflow(): Promise<void> {
  if (executionStore.isMutationLocked) return
  const target = currentSaveTarget()
  const route = await canvasCommands.routeSave()
  if (executionStore.isMutationLocked) return
  if (!isSaveTargetActive(target)) return
  if (route === 'nested' || route === 'unavailable') return
  if (!target.workflowName) {
    createIntent.value = 'save-current'
    workflowDialogFolderId.value = null
    workflowDialogMode.value = 'new'
    workflowDialogInitialName.value = 'Untitled'
    workflowDialogInitialDisplayName.value = 'Untitled'
    workflowDialogInitialDescription.value = null
    workflowDialogSuggestedName.value = null
    workflowDialogVisible.value = true
    return
  }
  try {
    await saveCurrentWorkflowGraph({ showSuccessToast: true }, target)
  } catch (err: unknown) {
    showError('Save workflow failed', err)
  }
}

function exportCurrentWorkflow(): void {
  if (executionStore.isMutationLocked) return
  const name = activeWorkflowId.value
  if (!name) return
  exportSaveDialogVisible.value = true
}

async function confirmExportCurrentWorkflow(): Promise<void> {
  if (executionStore.isMutationLocked) return
  exportSaveDialogVisible.value = false
  try {
    const info = await saveCurrentWorkflowGraph({
      showSuccessToast: false,
      conflictAction: 'exporting',
    })
    if (!info) return
    await workflowStore.exportWorkflow(workflowId(info))
  } catch (err: unknown) {
    showError('Export workflow failed', err)
  }
}

function chooseImportFile(): void {
  if (executionStore.isMutationLocked) return
  runAfterDiscard(() => {
    importFileInput.value?.click()
  })
}

async function openImportedWorkflow(name: string): Promise<void> {
  const loaded = await loadWorkflowGraph(name)
  applyGraph(loaded.graph, loaded.dirty, loaded)
  if (hasMissingImportDependencies()) {
    dependencyDialogVisible.value = true
    return
  }
  toast?.add({
    severity: 'success',
    summary: 'Workflow imported',
    detail: loaded.workflowDisplayName,
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
  if (executionStore.isMutationLocked) return
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
  if (executionStore.isMutationLocked) return
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
  if (executionStore.isMutationLocked) return
  try {
    const graph = await workflowStore.rebindVersions()
    dependencyDialogVisible.value = false
    applyGraph(graph)
  } catch (err: unknown) {
    showError('Dependency rebind failed', err)
  }
}

function saveWorkflowAs(): void {
  if (executionStore.isMutationLocked) return
  const target = currentSaveTarget()
  if (!target.workflowName) return
  workflowDialogFolderId.value = null
  workflowDialogMode.value = 'save-as'
  const baseName = target.workflowName
  workflowDialogInitialName.value = `${baseName}_copy`
  workflowDialogInitialDisplayName.value = `${uiStore.activeWorkflowName ?? baseName} copy`
  workflowDialogInitialDescription.value = activeWorkflow.value?.description ?? null
  workflowDialogSuggestedName.value = null
  workflowDialogTarget.value = {
    ...target,
    workflowName: target.workflowName,
    graph: JSON.parse(JSON.stringify(currentGraph.value)) as GraphState,
    missingTools: [...workflowStore.missingTools],
  }
  workflowDialogVisible.value = true
}

async function duplicateWorkflowByName(name: string): Promise<void> {
  if (executionStore.isMutationLocked) return
  const source = workflowStore.workflows.find((workflow) => workflowId(workflow) === name)
  const displayName = `${source?.display_name ?? name} copy`
  try {
    const info = await workflowStore.patchWorkflow(name, {
      action: 'duplicate',
      new_name: `${name}_copy`,
      display_name: displayName,
      description: source?.description ?? null,
    })
    const loaded = await loadWorkflowGraph(workflowId(info))
    applyGraph(loaded.graph, loaded.dirty, loaded)
  } catch (err: unknown) {
    showError('Duplicate workflow failed', err)
  }
}

async function exportWorkflowByName(name: string): Promise<void> {
  if (executionStore.isMutationLocked) return
  try {
    if (activeWorkflowId.value === name) {
      exportCurrentWorkflow()
      return
    }
    await workflowStore.exportWorkflow(name)
  } catch (err: unknown) {
    showError('Export workflow failed', err)
  }
}

function deleteWorkflowByName(name: string): void {
  if (executionStore.isMutationLocked) return
  deleteTargetName.value = name
  deleteCanvasTarget.value = activeWorkflowId.value === name
    ? currentSaveTarget()
    : null
  deleteDialogVisible.value = true
}

function deleteWorkflow(): void {
  if (executionStore.isMutationLocked) return
  const name = activeWorkflowId.value
  if (!name) return
  deleteTargetName.value = name
  deleteCanvasTarget.value = currentSaveTarget()
  deleteDialogVisible.value = true
}

async function confirmDeleteWorkflow(): Promise<void> {
  if (executionStore.isMutationLocked) return
  const name = deleteTargetName.value ?? activeWorkflowId.value
  if (!name) return
  const target = deleteCanvasTarget.value
  try {
    await workflowStore.deleteWorkflow(name)
    if (executionStore.isMutationLocked) return
    deleteDialogVisible.value = false
    deleteTargetName.value = null
    deleteCanvasTarget.value = null
    if (target?.canvasId !== null && target?.canvasId !== undefined) {
      window.dispatchEvent(new CustomEvent('bioimageflow:close-canvas', {
        detail: { canvasId: target.canvasId },
      }))
    } else if (target?.workflowName === name) {
      applyGraph({ nodes: [], edges: [] })
    }
  } catch (err: unknown) {
    showError('Delete workflow failed', err)
  }
}

function onDeleteWorkflowDialogVisible(value: boolean): void {
  deleteDialogVisible.value = value
  if (!value) {
    deleteTargetName.value = null
    deleteCanvasTarget.value = null
  }
}

function onGlobalKeydown(event: KeyboardEvent): void {
  if (event.defaultPrevented) return
  const meta = event.metaKey || event.ctrlKey
  if (meta && event.key === 's') {
    event.preventDefault()
    if (!executionStore.isMutationLocked) {
      void saveWorkflow()
    }
  }
}

function dispatchEditCommand(
  command: 'undo' | 'redo' | 'cut' | 'copy' | 'paste' | 'select-all',
): void {
  if (executionStore.isMutationLocked) return
  window.dispatchEvent(new CustomEvent('bioimageflow:edit-command', {
    detail: { command },
  }))
}

function editCommandDisabled(command: 'cut' | 'copy' | 'paste' | 'select-all' | 'undo' | 'redo'): boolean {
  if (executionStore.isMutationLocked) return true
  if (command === 'cut' || command === 'copy') {
    return uiStore.selectedNodeIds.length === 0
  }
  return false
}

function openRenameDialog(): void {
  if (executionStore.isMutationLocked) return
  if (!activeWorkflowId.value) return
  renameTarget.value = currentSaveTarget()
  renameDisplayName.value = uiStore.activeWorkflowName || activeWorkflowId.value
  renameDialogVisible.value = true
}

async function submitRename(): Promise<void> {
  if (executionStore.isMutationLocked) return
  const target = renameTarget.value
  const workflowName = target?.workflowName
  if (!workflowName) return
  const displayName = renameDisplayName.value.trim()
  if (!displayName) return
  try {
    const info = await workflowStore.patchWorkflow(workflowName, {
      action: 'update',
      display_name: displayName,
    }, target.canvasId === null
      ? undefined
      : { canvasId: target.canvasId, workflowName })
    if (
      target.canvasId !== null
      && uiStore.canvasWorkflowId(target.canvasId) === workflowId(info)
    ) {
      window.dispatchEvent(new CustomEvent('bioimageflow:canvas-context-updated', {
        detail: {
          panelId: target.canvasId,
          workflowName: workflowId(info),
          workflowDisplayName: info.display_name,
        },
      }))
    }
    renameDialogVisible.value = false
    renameTarget.value = null
  } catch (err: unknown) {
    showError('Rename workflow failed', err)
  }
}

function onBeforeUnload(): void {
  void autoSave.flushAutoSave()
}

function onWorkflowPanelCommand(event: Event): void {
  if (executionStore.isMutationLocked) return
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
      { label: 'New', icon: 'pi pi-plus', disabled: executionStore.isMutationLocked, command: () => createNewWorkflow() },
      { label: 'Open', icon: 'pi pi-folder-open', disabled: executionStore.isMutationLocked, command: openWorkflow },
      { label: 'Save', icon: 'pi pi-save', disabled: executionStore.isMutationLocked, command: saveWorkflow },
      { label: 'Save As', icon: 'pi pi-copy', disabled: executionStore.isMutationLocked, command: saveWorkflowAs },
      { label: 'Import', icon: 'pi pi-upload', disabled: executionStore.isMutationLocked, command: chooseImportFile },
      { label: 'Export', icon: 'pi pi-download', disabled: executionStore.isMutationLocked || !activeWorkflowId.value, command: exportCurrentWorkflow },
      { label: 'Delete', icon: 'pi pi-trash', disabled: executionStore.isMutationLocked || !activeWorkflowId.value, command: deleteWorkflow },
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
        disabled: !executionStore.canStop,
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
  exportSaveDialogVisible,
  confirmExportCurrentWorkflow,
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
          v-if="activeWorkflowId"
          icon="pi pi-pencil"
          text
          rounded
          size="small"
          aria-label="Rename workflow"
          title="Rename workflow"
          data-testid="workflow-title-edit"
          :disabled="executionStore.isMutationLocked"
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
    :initial-description="workflowDialogInitialDescription"
    :suggested-name="workflowDialogSuggestedName"
    @submit="onWorkflowDialogSubmit"
  />

  <OpenWorkflowDialog
    v-model:visible="openDialogVisible"
    :workflows="workflowStore.workflows"
    :current-name="activeWorkflowId"
    @open="onOpenWorkflow"
  />

  <DeleteWorkflowDialog
    v-model:visible="deleteDialogVisible"
    :workflow="deleteDialogWorkflow"
    @confirm="confirmDeleteWorkflow"
    @update:visible="onDeleteWorkflowDialogVisible"
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
    v-model:visible="exportSaveDialogVisible"
    modal
    header="Save before export?"
    :style="{ width: '420px' }"
    data-testid="export-save-confirm"
  >
    <p>
      The current workflow will be saved before the export file is created.
    </p>
    <template #footer>
      <Button label="Cancel" text @click="exportSaveDialogVisible = false" />
      <Button
        label="Save and export"
        icon="pi pi-download"
        data-testid="export-save-confirm-submit"
        @click="confirmExportCurrentWorkflow"
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
