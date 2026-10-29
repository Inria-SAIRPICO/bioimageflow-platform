<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch, type ComputedRef } from 'vue'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'
import ToggleButton from 'primevue/togglebutton'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { openNodeWithEditor } from '@/api/editor'
import { useSettingsStore } from '@/stores/settings'
import { useWorkflowStore } from '@/stores/workflow'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useLoggerStore, ALL_LEVELS, type LogEntry } from '@/stores/logger'
import { useNestedWorkflowSessionsStore } from '@/stores/nestedWorkflowSessions'
import { usePathPicker } from '@/composables/usePathPicker'
import { useGraphSync } from '@/composables/useGraphSync'
import { useCanvasStatusProjection } from '@/composables/useCanvasStatusProjection'
import {
  useCanvasCommands,
  type CanvasInterfaceCommandResult,
} from '@/composables/useCanvasCommands'
import { useValidationErrors } from '@/composables/useValidationErrors'
import {
  useFieldFocusTracker,
  type FieldFocusTarget,
} from '@/composables/useFieldFocusTracker'
import {
  canvasSessionRegistry,
  type CanvasId,
} from '@/sessions/canvasSessionRegistry'
import ParameterRow from '@/components/panels/shared/ParameterRow.vue'
import { decodeWorkflowConstant } from '@/utils/workflowConstants'
import type { WorkflowInputPresentation } from '@/utils/workflowInputPresentation'
import NodeOutputErrorBlock from '@/components/panels/shared/NodeOutputErrorBlock.vue'
import NodeResourcesTab from '@/components/panels/NodeResourcesTab.vue'
import type {
  GraphValidationError,
  InputFieldSchema,
  WorkflowInput,
  WorkflowOutput,
} from '@/api/types'
import { fieldDisplayName } from '@/utils/displayNames'
import { IMAGE_PATH_GLOBS } from '@/utils/imagePaths'
import { dataframePositions, nextDataframePosition } from '@/utils/dataframeInputs'
import { encodeEndpointHandle } from '@/utils/endpointHandles'
import { apiGraphValidationErrors } from '@/utils/apiError'

// `OutputFieldSchema` is not exposed in the generated OpenAPI types because
// `ToolMetadata.outputs` is `dict[str, Any]` server-side (to accommodate the
// `{"_passthrough": true}` Passthrough marker for DataFrame tools). Mirror
// the library's wire shape here.
interface OutputFieldSchema {
  type: string
  default: unknown
  image_spec: Record<string, string[]> | null
  display_name?: string | null
}

// Eligibility is separate from transient visibility and publication.
// Connected eligible inputs keep their pin even when its local toggle was off.
function canConnect(field: InputFieldSchema): boolean {
  return field.connectable !== 'never'
}

const {
  pickFile: pickFileNative,
  pickFiles: pickFilesNative,
  pickFolder: pickFolderNative,
  showDatasetsPanel,
  isDesktop,
} = usePathPicker()

const MASK_EXTS = ['*.tif', '*.tiff', '*.png']

function fileTypesForField(type: string): string[] {
  if (type === 'ImageFile') return [...IMAGE_PATH_GLOBS]
  if (type === 'MaskPath') return MASK_EXTS
  return []
}

const uiStore = useUIStore()
const executionStore = useExecutionStore()
const statusProjection = useCanvasStatusProjection()
const loggerStore = useLoggerStore()
const nestedWorkflowSessionsStore = useNestedWorkflowSessionsStore()
const { validationResult } = useGraphSync()
const canvasCommands = useCanvasCommands()
const { nodeErrors, getFieldErrors } = useValidationErrors(validationResult)
const fieldFocusTracker = useFieldFocusTracker()
const isNodeEditingDisabled = computed(() => executionStore.isMutationLocked)
const canClearNodeOutputs = computed(() => canvasCommands.canClearNodeOutputs())
const destructiveDialog = ref<{
  action: 'delete' | 'clear'
  nodeIds: string[]
  canvasId: CanvasId
} | null>(null)
const destructiveActionPending = ref(false)
const destructiveActionError = ref('')
const destructiveValidationErrors = ref<GraphValidationError[]>([])
const focusedParameterRows = new Map<EventTarget, FieldFocusTarget>()

const selectedNodeErrors = computed(() => {
  const nodeId = uiStore.selectedNodeIds[0]
  if (!nodeId) return []
  return nodeErrors.value[nodeId] ?? []
})

function fieldErrorsFor(fieldName: string): GraphValidationError[] {
  const nodeId = uiStore.selectedNodeIds[0]
  if (!nodeId) return []
  return getFieldErrors(nodeId, fieldName)
}

const selectedNode = computed(() => {
  if (!uiStore.isSingleSelection) return null
  const nodeId = uiStore.selectedNodeIds[0]
  return uiStore.graphNodes.find((n: any) => n.id === nodeId) ?? null
})

const nodeData = computed(() => selectedNode.value?.data ?? null)
let nextNodeIdentity = 0
const nodeIdentities = new WeakMap<object, number>()
const parameterOwner = computed(() => {
  const id = canvasSessionRegistry.activeCanvasId.value
  const node = selectedNode.value
  if (node && !nodeIdentities.has(node)) nodeIdentities.set(node, ++nextNodeIdentity)
  return `${id}:${id ? canvasSessionRegistry.get(id)?.registrationToken : ''}:${node?.id}:${node ? nodeIdentities.get(node) : ''}`
})
const editableWorkflowInputs = computed(() => (
  (nodeData.value?.workflow?.interface.inputs ?? []).filter((input: WorkflowInput) => input.kind === 'field') as WorkflowInput[]
))
function workflowPresentation(input: WorkflowInput): WorkflowInputPresentation | undefined {
  return nodeData.value?.workflowInputPresentation?.[input.id]
}
function workflowField(input: WorkflowInput): InputFieldSchema {
  return workflowPresentation(input)?.field ?? {
    type: typeof input.schema?.type === 'string' ? input.schema.type : 'any',
    display_name: input.name, nullable: input.schema?.nullable === true,
    required: input.default == null, connectable: 'never',
  }
}
function workflowValue(input: WorkflowInput): { value: unknown; inherited: boolean; unsupported?: string } {
  const bindings = nodeData.value?.bindings ?? {}
  const inherited = !Object.prototype.hasOwnProperty.call(bindings, input.id)
  const constant = inherited ? input.default : bindings[input.id]
  if (constant == null) return { value: undefined, inherited }
  try { return { value: decodeWorkflowConstant(constant), inherited } }
  catch (error) { return { value: undefined, inherited, unsupported: error instanceof Error ? error.message : String(error) } }
}
function workflowErrors(input: WorkflowInput): GraphValidationError[] {
  const errors = [...fieldErrorsFor(input.id)]
  for (const target of workflowPresentation(input)?.targets ?? []) {
    for (const error of getFieldErrors(target.node, target.field)) {
      if (!errors.includes(error)) errors.push({ ...error, detail: `${target.node}.${target.field}: ${error.detail}` })
    }
  }
  return errors
}
function updateWorkflowInputValue(inputId: string, value: unknown, owner?: string): void {
  if (owner !== undefined && owner !== parameterOwner.value) return
  const nodeId = selectedNode.value?.id
  if (nodeId) canvasCommands.updateWorkflowBinding(nodeId, inputId, value)
}
function resetWorkflowInput(inputId: string, owner?: string): void {
  if (owner !== undefined && owner !== parameterOwner.value) return
  const nodeId = selectedNode.value?.id
  if (nodeId) canvasCommands.resetWorkflowBinding(nodeId, inputId)
}
function toolValue(key: string, field: InputFieldSchema): unknown {
  const params = nodeData.value?.parameters ?? {}
  return Object.prototype.hasOwnProperty.call(params, key) ? params[key] : field.default
}
const settingsStore = useSettingsStore()
const workflowStore = useWorkflowStore()
const openingToolScript = ref(false)
const toolScriptError = ref('')
const canOpenToolScript = computed(() => !!nodeData.value?.toolName && (
  settingsStore.settings?.deployment_mode !== 'webapp'
  || settingsStore.settings?.enable_unsafe_webapp_features === true
))
watch(selectedNode, () => { toolScriptError.value = '' })

async function openToolScript() {
  if (!canOpenToolScript.value || openingToolScript.value) return
  const node = selectedNode.value
  openingToolScript.value = true
  toolScriptError.value = ''
  try {
    await openNodeWithEditor(node!.id, {
      showEmbeddedLoading: !settingsStore.settings?.external_editor?.trim(),
    })
  } catch (error) {
    if (selectedNode.value === node) {
      toolScriptError.value = error instanceof Error ? error.message : String(error)
    }
  } finally {
    openingToolScript.value = false
  }
}

const interfaceNameError = ref<string | null>(null)

const editingName = ref(false)
const activeTab = ref<'parameters' | 'resources' | 'execution'>('parameters')
const nameInput = ref('')
const nameError = ref<string | null>(null)


/** Documentation section collapsed state (open by default) */
const docCollapsed = ref(false)
const executionOutputCollapsed = ref(false)
const nodeLogLevels = ref(new Set<string>(['INFO', 'WARNING', 'ERROR']))
const activeNodeLogEntries = shallowRef<ComputedRef<LogEntry[]> | null>(null)

const selectedNodeLogTarget = computed<{
  nodeId: string
  executionCanvasId: CanvasId
} | null>(() => {
  const selectedNodeId = selectedNode.value?.id
  const activeCanvasId = canvasSessionRegistry.activeCanvasId.value
  if (!selectedNodeId || activeCanvasId === null) return null

  let canvasId = activeCanvasId
  const segments = [selectedNodeId]
  const visitedCanvasIds = new Set<string>()
  while (!visitedCanvasIds.has(canvasId)) {
    visitedCanvasIds.add(canvasId)
    const descriptor = canvasSessionRegistry.get(canvasId)?.descriptor
    if (!descriptor) return null
    if (descriptor.kind === 'root') {
      return { nodeId: segments.join('/'), executionCanvasId: descriptor.canvasId }
    }
    const session = nestedWorkflowSessionsStore.sessionById(descriptor.sessionId)
    if (!session) return null
    segments.unshift(session.parentNodeId)
    canvasId = descriptor.parentCanvasId
  }
  return null
})

watch(
  [
    () => selectedNodeLogTarget.value?.nodeId ?? null,
    () => selectedNodeLogTarget.value?.executionCanvasId ?? null,
    () => uiStore.activeWorkflowId,
    () => executionStore.executionId,
    () => executionStore.executionWorkflowId,
  ],
  ([nodeId, executionCanvasId, workflowId]) => {
    if (!nodeId) {
      activeNodeLogEntries.value = null
      return
    }
    const executionId = executionCanvasId !== null
      && executionStore.executionId !== null
      && executionStore.appliesToCanvas(executionCanvasId)
      ? executionStore.executionId
      : undefined
    activeNodeLogEntries.value = loggerStore.nodeEntries(nodeId, {
      workflowId,
      ...(executionId === undefined ? {} : { executionId }),
    })
  },
  { immediate: true },
)

const selectedNodeStatus = computed(() => {
  const nodeId = selectedNode.value?.id
  return nodeId ? statusProjection.statusForNode(nodeId) : null
})
const selectedNodeDisplayStatus = computed(() => (
  selectedNodeStatus.value?.presentationStatus
  ?? (nodeData.value?.enabled === false ? 'disabled' : 'unexecuted')
))
const selectedNodeStatusClass = computed(() => (
  `status-${selectedNodeDisplayStatus.value.replace(/_/g, '-')}`
))

const selectedNodeLogs = computed(() => activeNodeLogEntries.value?.value ?? [])

const filteredSelectedNodeLogs = computed(() =>
  selectedNodeLogs.value.filter((entry) => nodeLogLevels.value.has(entry.level.toUpperCase())),
)

function toggleNodeLogLevel(level: string) {
  const next = new Set(nodeLogLevels.value)
  if (next.has(level)) next.delete(level)
  else next.add(level)
  nodeLogLevels.value = next
}

function formatLogTimestamp(seconds: number): string {
  return new Date(seconds * 1000).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3,
  } as Intl.DateTimeFormatOptions)
}

function startEditName() {
  if (!nodeData.value || isNodeEditingDisabled.value) return
  nameInput.value = nodeData.value.name
  nameError.value = null
  editingName.value = true
}

function finishEditName() {
  const nodeId = selectedNode.value?.id
  if (!nodeId || !nodeData.value) return
  const trimmedName = nameInput.value.trim()
  if (!trimmedName) {
    nameError.value = 'Node name is required.'
    return
  }
  if (uiStore.graphNodes.some((node: any) => (
    node.id !== nodeId && node.data?.name === trimmedName
  ))) {
    nameError.value = `A node named “${trimmedName}” already exists.`
    return
  }
  if (trimmedName !== nodeData.value.name && !canvasCommands.renameNode(nodeId, trimmedName)) {
    return
  }
  nameError.value = null
  editingName.value = false
}

function setSelectedNodesEnabled(enabled: boolean): void {
  canvasCommands.setNodesEnabled(uiStore.selectedNodeIds, enabled)
}

function requestDestructiveAction(action: 'delete' | 'clear'): void {
  const canvasId = statusProjection.canvasId
  const nodeIds = [...uiStore.selectedNodeIds]
  if (
    canvasId === null
    || nodeIds.length === 0
    || isNodeEditingDisabled.value
    || (action === 'clear' && !canClearNodeOutputs.value)
  ) return
  destructiveActionError.value = ''
  destructiveValidationErrors.value = []
  destructiveDialog.value = { action, nodeIds, canvasId }
}

function closeDestructiveDialog(): void {
  if (destructiveActionPending.value) return
  destructiveDialog.value = null
  destructiveActionError.value = ''
  destructiveValidationErrors.value = []
}

async function confirmDestructiveAction(): Promise<void> {
  const request = destructiveDialog.value
  if (request === null || destructiveActionPending.value) return
  destructiveActionPending.value = true
  destructiveActionError.value = ''
  destructiveValidationErrors.value = []
  try {
    const accepted = request.action === 'delete'
      ? canvasCommands.deleteNodes(request.nodeIds, request.canvasId)
      : await canvasCommands.clearNodeOutputs(request.nodeIds, request.canvasId)
    if (!accepted) {
      destructiveActionError.value = executionStore.isMutationLocked
        ? 'This action is locked while execution is running.'
        : 'The selected canvas is no longer active. Review the selection and try again.'
      return
    }
    destructiveDialog.value = null
  } catch (error) {
    destructiveActionError.value = error instanceof Error ? error.message : String(error)
    destructiveValidationErrors.value = apiGraphValidationErrors(error)
  } finally {
    destructiveActionPending.value = false
  }
}

const destructiveDialogTitle = computed(() => (
  destructiveDialog.value?.action === 'delete' ? 'Delete selected nodes' : 'Clear node outputs'
))

const destructiveDialogMessage = computed(() => {
  const request = destructiveDialog.value
  if (request === null) return ''
  const count = request.nodeIds.length
  if (request.action === 'delete') {
    return `Delete ${count} selected node${count === 1 ? '' : 's'} and their connected edges?`
  }
  return `Clear cached outputs for ${count} selected node${count === 1 ? '' : 's'}? This cannot be undone.`
})

function updateParameter(key: string, value: unknown, owner?: string) {
  if (owner !== undefined && owner !== parameterOwner.value) return
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  canvasCommands.updateParameter(nodeId, key, value)
}

function isFilesSourceNode(): boolean {
  if (String(nodeData.value?.toolName ?? '').toLocaleLowerCase() !== 'files') {
    return false
  }
  const inputs = nodeData.value?.tool?.inputs
  return inputs?.files?.type === 'list' && inputs?.path?.path_picker === 'folder'
}

function isFilesListField(key: string, field: InputFieldSchema): boolean {
  return key === 'files' && field.type === 'list' && isFilesSourceNode()
}

watch(() => selectedNode.value?.id, () => {
  nameError.value = null
  editingName.value = false
  activeTab.value = 'parameters'
})

function updateResources(resources: Record<string, number | string>): void {
  const nodeId = selectedNode.value?.id
  if (!nodeId || nodeData.value?.nodeType !== 'tool') return
  canvasCommands.setNodeResources(nodeId, resources)
}

function trackParameterFocus(fieldName: string, event: FocusEvent): void {
  const canvasId = canvasSessionRegistry.activeCanvasId.value
  const nodeId = selectedNode.value?.id
  if (canvasId === null || !nodeId || event.currentTarget === null) return
  const target = { canvasId, nodeId, fieldName }
  focusedParameterRows.set(event.currentTarget, target)
  fieldFocusTracker.trackFocus(target)
}

function trackParameterBlur(event: FocusEvent): void {
  const row = event.currentTarget
  if (row instanceof HTMLElement && event.relatedTarget instanceof Node) {
    if (row.contains(event.relatedTarget)) return
  }
  if (row === null) return
  const target = focusedParameterRows.get(row)
  if (target === undefined) return
  focusedParameterRows.delete(row)
  fieldFocusTracker.trackBlur(target)
}

function clearTrackedParameterFocus(): void {
  for (const target of new Set(focusedParameterRows.values())) {
    fieldFocusTracker.trackBlur(target)
  }
  focusedParameterRows.clear()
}

watch(
  [
    () => canvasSessionRegistry.activeCanvasId.value,
    () => selectedNode.value?.id ?? null,
  ],
  clearTrackedParameterFocus,
)

onBeforeUnmount(clearTrackedParameterFocus)

function toggleEnabled() {
  const nodeId = selectedNode.value?.id
  if (!nodeId || !nodeData.value) return
  canvasCommands.setNodeEnabled(nodeId, !nodeData.value.enabled)
}

function resetToDefault(key: string, owner?: string) {
  if (owner !== undefined && owner !== parameterOwner.value) return
  const field = nodeData.value?.tool?.inputs[key] as InputFieldSchema | undefined
  if (field) updateParameter(key, field.default ?? null)
}

function togglePinned(key: string, owner?: string) {
  if (owner !== undefined && owner !== parameterOwner.value) return
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  canvasCommands.setInputPinned(nodeId, key, !isPinned(key))
}

function isPinned(key: string): boolean {
  if (connectedInputSource(key) !== null) return true
  if (!nodeData.value?.pinnedInputs) return true
  return nodeData.value.pinnedInputs[key] !== false
}

function connectedInputSource(key: string): string | null {
  const handle = encodeEndpointHandle(nodeData.value?.nodeType === 'workflow'
    ? { kind: 'workflow-input', id: key } : { kind: 'tool-input', name: key })
  return nodeData.value?.connectedInputs?.[handle] ?? null
}

function updateOutputTemplate(key: string, value: string) {
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  canvasCommands.setOutputTemplate(nodeId, key, value)
}

function isPathType(type: string): boolean {
  return ['Path', 'ImageFile', 'MaskPath'].includes(type)
}

type PathPickerMode = 'file' | 'folder' | 'both'

function pathPickerMode(field: InputFieldSchema): PathPickerMode {
  if (field.path_picker) return field.path_picker
  return field.type === 'Path' ? 'both' : 'file'
}

function showsFilePicker(field: InputFieldSchema): boolean {
  return ['file', 'both'].includes(pathPickerMode(field))
}

function showsFolderPicker(field: InputFieldSchema): boolean {
  return isDesktop() && ['folder', 'both'].includes(pathPickerMode(field))
}

function isOutputTemplateApplicable(field: OutputFieldSchema): boolean {
  // Path-template editing only applies to ProcessingTool outputs. DataFrameTool
  // Outputs are column declarations, not files written to disk.
  if (nodeData.value?.tool?.tool_type === 'DataFrameTool') return false
  return isPathType(field.type)
}

const workflowInterfaceContext = computed(() => (
  nodeData.value?.workflowInterfaceContext
  ?? nodeData.value?.nestedWorkflowContext
  ?? null
))

function selectedInternalNodeId(): string {
  return selectedNode.value?.id ?? ''
}

function workflowInputIndex(fieldName: string | number): number {
  const ctx = workflowInterfaceContext.value
  if (!ctx) return -1
  return (ctx.inputs ?? []).findIndex((item: WorkflowInput) => item.targets.some(target => (
    target.node === selectedInternalNodeId()
    && ((target.port.kind === 'field' && target.port.name === fieldName)
      || (target.port.kind === 'positional' && target.port.index === fieldName)
      || (target.port.kind === 'workflow' && target.port.id === fieldName))
  )))
}

function workflowOutputIndex(outputName: string): number {
  const ctx = workflowInterfaceContext.value
  if (!ctx) return -1
  return (ctx.outputs ?? []).findIndex((item: WorkflowOutput) => (
    item.source.node === selectedInternalNodeId() && item.source.column === outputName
  ))
}

function isWorkflowInputExposed(fieldName: string): boolean {
  return workflowInputIndex(fieldName) >= 0
}

function isWorkflowOutputExposed(outputName: string): boolean {
  return workflowOutputIndex(outputName) >= 0
}

function applyInterfaceResult(result: CanvasInterfaceCommandResult): void {
  if (result.status === 'rejected' && result.reason === 'duplicate_name') {
    interfaceNameError.value = `Workflow interface name '${result.name ?? ''}' is already used.`
    return
  }
  if (result.status === 'rejected' && result.reason === 'empty_name') {
    interfaceNameError.value = 'Workflow interface name cannot be empty.'
    return
  }
  if (result.status !== 'rejected') interfaceNameError.value = null
}

function toggleWorkflowInputExposure(fieldName: string | number, owner?: string) {
  if (owner !== undefined && owner !== parameterOwner.value) return
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  applyInterfaceResult(canvasCommands.toggleWorkflowInput(nodeId, fieldName))
}

function updateWorkflowInputName(fieldName: string | number, value: string, owner?: string) {
  if (owner !== undefined && owner !== parameterOwner.value) return
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  applyInterfaceResult(
    canvasCommands.renameWorkflowInput(nodeId, fieldName, value),
  )
}

const acceptsDataframes = computed(() => (
  nodeData.value?.tool?.tool_type === 'DataFrameTool'
  && nodeData.value?.tool?.accepts_upstream === true
))
const publishedDataframes = computed(() => (
  (workflowInterfaceContext.value?.inputs ?? []).flatMap((input: WorkflowInput) => (
    input.kind !== 'dataframe' ? [] : input.targets.flatMap(target => {
      if (target.node !== selectedInternalNodeId()) return []
      if (target.port.kind === 'positional') {
        return [{ input, endpoint: target.port.index as string | number, label: `DataFrame ${target.port.index + 1}` }]
      }
      if (target.port.kind === 'workflow') {
        const portId = target.port.id
        const child = nodeData.value?.workflow?.interface.inputs.find((port: WorkflowInput) => port.id === portId)
        return [{ input, endpoint: portId as string | number, label: child?.name ?? portId }]
      }
      return []
    })
  ))
))
const availableChildDataframes = computed(() => (
  (nodeData.value?.workflow?.interface.inputs ?? []).filter((input: WorkflowInput) => (
    input.kind === 'dataframe' && workflowInputIndex(input.id) < 0
    && !(encodeEndpointHandle({ kind: 'workflow-input', id: input.id }) in (nodeData.value?.connectedInputs ?? {}))
  ))
))
function publishDataframe() {
  const index = nextDataframePosition(dataframePositions(
    selectedInternalNodeId(), nodeData.value?.connectedInputs ?? {},
    workflowInterfaceContext.value?.inputs ?? [],
  ))
  toggleWorkflowInputExposure(index)
}

function toggleWorkflowOutputExposure(outputName: string) {
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  applyInterfaceResult(canvasCommands.toggleWorkflowOutput(nodeId, outputName))
}

function updateWorkflowOutputName(outputName: string, value: string) {
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  applyInterfaceResult(
    canvasCommands.renameWorkflowOutput(nodeId, outputName, value),
  )
}

function captureParameterEdit(key: string): ((value: unknown, filesMode?: boolean) => void) | null {
  const node = selectedNode.value
  const canvasId = canvasSessionRegistry.activeCanvasId.value
  const registration = canvasId ? canvasSessionRegistry.get(canvasId)?.registrationToken : undefined
  if (!node || isNodeEditingDisabled.value) return null
  const workflow = node.data.nodeType === 'workflow'
  const declaration = workflow ? node.data.workflow?.interface.inputs.find((input: WorkflowInput) => input.id === key) : node.data.tool?.inputs[key]
  if (!declaration) return null
  const filesSource = isFilesSourceNode()
  return (value, filesMode = false) => {
    if (isNodeEditingDisabled.value || selectedNode.value !== node || canvasSessionRegistry.activeCanvasId.value !== canvasId) return
    if (canvasId && canvasSessionRegistry.get(canvasId)?.registrationToken !== registration) return
    const current = workflow ? node.data.workflow?.interface.inputs.find((input: WorkflowInput) => input.id === key) : node.data.tool?.inputs[key]
    if (current !== declaration || connectedInputSource(key) !== null) return
    if (workflow) canvasCommands.updateWorkflowBinding(node.id, key, value)
    else if (filesMode || (filesSource && key === 'path')) canvasCommands.updateParameters(node.id,
      filesMode ? { path: null, files: value } : { path: value, files: null })
    else canvasCommands.updateParameter(node.id, key, value)
  }
}
async function pickFile(key: string, type: string, owner?: string) {
  if (owner !== undefined && owner !== parameterOwner.value) return
  const apply = captureParameterEdit(key)
  if (!apply) return
  const path = await pickFileNative({ parameterName: key, fileTypes: fileTypesForField(type) })
  if (path !== null) apply(path)
}
async function pickFolder(key: string, owner?: string) {
  if (owner !== undefined && owner !== parameterOwner.value) return
  const apply = captureParameterEdit(key)
  if (!apply) return
  const path = await pickFolderNative({ parameterName: key })
  if (path !== null) apply(path)
}
async function pickFiles(key: string) {
  if (!isDesktop()) { showDatasetsPanel(); return }
  const apply = captureParameterEdit(key)
  if (!apply) return
  const paths = await pickFilesNative({ parameterName: key })
  if (paths.length > 0) apply(paths, true)
}
</script>

<template>
  <div class="node-panel" data-testid="panel-nodePanel">
    <div v-if="!uiStore.hasSelection" class="empty-state">
      Select a node to view its properties
    </div>

    <div v-else-if="uiStore.isMultiSelection" class="multi-select">
      <p>{{ uiStore.selectedNodeIds.length }} nodes selected</p>
      <div class="multi-select-actions">
        <Button
          label="Enable all"
          :disabled="isNodeEditingDisabled"
          data-testid="bulk-enable-nodes"
          @click="setSelectedNodesEnabled(true)"
        />
        <Button
          label="Disable all"
          severity="secondary"
          :disabled="isNodeEditingDisabled"
          data-testid="bulk-disable-nodes"
          @click="setSelectedNodesEnabled(false)"
        />
        <Button
          label="Delete all"
          severity="danger"
          :disabled="isNodeEditingDisabled"
          data-testid="bulk-delete-nodes"
          @click="requestDestructiveAction('delete')"
        />
        <Button
          v-if="canClearNodeOutputs"
          label="Clear all"
          severity="secondary"
          :disabled="isNodeEditingDisabled"
          data-testid="bulk-clear-node-outputs"
          @click="requestDestructiveAction('clear')"
        />
      </div>
    </div>

    <div v-else-if="nodeData" class="node-details">
      <!-- Validation errors -->
      <div
        v-if="selectedNodeErrors.length > 0"
        class="node-validation-errors"
        data-testid="node-validation-errors"
      >
        <div class="node-validation-errors__title">
          <i class="pi pi-exclamation-triangle" />
          Validation errors
        </div>
        <ul>
          <li v-for="(err, i) in selectedNodeErrors" :key="i">
            <strong v-if="err.field">{{ err.field }}:</strong>
            {{ err.detail }}
          </li>
        </ul>
      </div>

      <!-- Header -->
      <div class="node-panel-header">
        <div class="node-name-row">
          <InputText
            v-if="editingName"
            v-model="nameInput"
            class="name-input"
            :invalid="nameError !== null"
            :disabled="isNodeEditingDisabled"
            @input="nameError = null"
            @blur="finishEditName"
            @keydown.enter.exact="finishEditName"
            autofocus
          />
          <span
            v-else
            class="node-name"
            @dblclick="startEditName"
            title="Double-click to rename"
          >
            {{ nodeData.name }}
          </span>
          <!-- Fix 12: Enable/Disable toggle -->
          <ToggleSwitch
            :model-value="nodeData.enabled"
            :disabled="isNodeEditingDisabled"
            @update:model-value="toggleEnabled"
            class="enabled-toggle"
            data-testid="node-enabled-toggle"
          />
        </div>
        <small
          v-if="nameError"
          class="node-name-error"
          data-testid="node-name-error"
          role="alert"
        >
          {{ nameError }}
        </small>
        <div class="tool-info">
          <span class="tool-name">{{ nodeData.toolName }}</span>
          <span class="status-badge" :class="selectedNodeStatusClass">
            {{ selectedNodeDisplayStatus }}
          </span>
        </div>
        <!-- Fix 13: Package + version display. The active version is
             workflow-scoped and is changed via the Manage Tools dialog. -->
        <div v-if="nodeData.tool" class="package-info">
          {{ nodeData.tool.package }} v{{ nodeData.tool.package_version }}
        </div>
        <Button
          v-if="canOpenToolScript"
          label="Open tool script"
          icon="pi pi-code"
          severity="secondary"
          text
          size="small"
          :loading="openingToolScript"
          :disabled="openingToolScript"
          data-testid="open-tool-script"
          @click="openToolScript"
        />
        <p v-if="toolScriptError" role="alert">{{ toolScriptError }}</p>
      </div>

      <div class="node-action-bar">
        <Button
          v-if="canClearNodeOutputs"
          label="Clear"
          icon="pi pi-eraser"
          severity="secondary"
          :disabled="isNodeEditingDisabled"
          data-testid="clear-node-outputs"
          @click="requestDestructiveAction('clear')"
        />
      </div>

      <div class="node-tabs" role="tablist" aria-label="Node details">
        <button
          v-for="tab in ['parameters', 'resources', 'execution'] as const"
          :key="tab"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab"
          :class="['node-tab', { 'node-tab--active': activeTab === tab }]"
          :data-testid="`node-tab-${tab}`"
          @click="activeTab = tab"
        >
          {{ tab[0]!.toUpperCase() + tab.slice(1) }}
        </button>
      </div>

      <div v-show="activeTab === 'parameters'" class="node-tab-panel" data-testid="node-parameters-tab">
      <!-- Documentation section, open by default. The chevron is rendered
           before the label and toggles the section. -->
      <section v-if="nodeData.tool?.documentation" class="doc-panel" data-testid="doc-panel">
        <button
          type="button"
          class="doc-panel-header"
          :aria-expanded="!docCollapsed"
          @click="docCollapsed = !docCollapsed"
        >
          <i :class="docCollapsed ? 'pi pi-chevron-right' : 'pi pi-chevron-down'" />
          <span class="p-panel-title doc-panel-title">Documentation</span>
        </button>
        <div v-show="!docCollapsed" class="doc-panel-body">
          <p class="doc-text">{{ nodeData.tool.documentation }}</p>
        </div>
      </section>

      <section
        v-if="workflowInterfaceContext && (acceptsDataframes || publishedDataframes.length || availableChildDataframes.length)"
        class="parameters-section"
        data-testid="published-dataframe-inputs"
      >
        <h4>Published DataFrame inputs</h4>
        <div v-for="row in publishedDataframes" :key="`${row.input.id}-${row.endpoint}`" class="param-row">
          <label :for="`dataframe-input-name-${row.input.id}`">Workflow input name</label>
          <InputText
            :id="`dataframe-input-name-${row.input.id}`"
            :model-value="row.input.name"
            :disabled="isNodeEditingDisabled"
            :data-testid="`dataframe-input-name-${row.endpoint}`"
            @update:model-value="updateWorkflowInputName(row.endpoint, $event as string)"
          />
          <div class="param-header">
            <span>→ {{ row.label }}</span>
            <Button label="Unpublish" class="p-button-text p-button-sm"
              :disabled="isNodeEditingDisabled" :data-testid="`unpublish-dataframe-${row.endpoint}`"
              @click="toggleWorkflowInputExposure(row.endpoint)" />
          </div>
        </div>
        <Button v-if="acceptsDataframes" label="Publish DataFrame input" icon="pi pi-plus"
          :disabled="isNodeEditingDisabled" data-testid="publish-dataframe-input" @click="publishDataframe" />
        <Button v-for="input in availableChildDataframes" :key="input.id"
          :label="`Publish DataFrame input: ${input.name}`" icon="pi pi-plus"
          :disabled="isNodeEditingDisabled" @click="toggleWorkflowInputExposure(input.id)" />
        <small v-if="interfaceNameError" class="interface-name-error" role="alert">{{ interfaceNameError }}</small>
      </section>

      <!-- Both node variants use the same parameter controls. -->
      <div v-if="nodeData.nodeType === 'workflow' || nodeData.tool" class="parameters-section">
        <h4>Parameters</h4>
        <div v-if="interfaceNameError" class="interface-name-error" data-testid="interface-name-error">{{ interfaceNameError }}</div>
        <ParameterRow v-for="input in editableWorkflowInputs" :key="`${parameterOwner}:${input.id}`"
          :owner="parameterOwner" :field-key="input.id" :field="workflowField(input)" :value="workflowValue(input).value"
          :inherited="workflowValue(input).inherited" :unsupported="workflowValue(input).unsupported"
          :connected-source="connectedInputSource(input.id)" :disabled="isNodeEditingDisabled"
          :can-pin="workflowPresentation(input)?.canPin === true" :pinned="isPinned(input.id)"
          :can-publish="!!workflowInterfaceContext" :published="isWorkflowInputExposed(input.id)"
          :published-name="workflowInterfaceContext?.inputs[workflowInputIndex(input.id)]?.name"
          :file-picker="showsFilePicker(workflowField(input))" :folder-picker="showsFolderPicker(workflowField(input))"
          :widget-test-id="`workflow-binding-${input.id}`" :errors="workflowErrors(input)"
          @update-value="(value, owner) => updateWorkflowInputValue(input.id, value, owner)" @reset="owner => resetWorkflowInput(input.id, owner)"
          @toggle-pin="owner => togglePinned(input.id, owner)" @toggle-publication="owner => toggleWorkflowInputExposure(input.id, owner)"
          @rename-publication="(value, owner) => updateWorkflowInputName(input.id, value, owner)"
          @pick-file="owner => pickFile(input.id, workflowField(input).type, owner)" @pick-folder="owner => pickFolder(input.id, owner)"
          @focusin="trackParameterFocus(input.id, $event)" @focusout="trackParameterBlur($event)" />
        <ParameterRow v-for="[key, field] in Object.entries(nodeData.tool?.inputs ?? {})" :key="`${parameterOwner}:${key}`"
          :owner="parameterOwner" :field-key="key" :field="field as InputFieldSchema" :value="toolValue(key, field as InputFieldSchema)"
          :connected-source="connectedInputSource(key)" :disabled="isNodeEditingDisabled"
          :can-pin="canConnect(field as InputFieldSchema)" :pinned="isPinned(key)"
          :can-publish="!!workflowInterfaceContext" :published="isWorkflowInputExposed(key)"
          :published-name="workflowInterfaceContext?.inputs[workflowInputIndex(key)]?.name"
          :file-picker="showsFilePicker(field as InputFieldSchema)" :folder-picker="showsFolderPicker(field as InputFieldSchema)"
          :errors="fieldErrorsFor(key)" @update-value="(value, owner) => updateParameter(key, value, owner)" @reset="owner => resetToDefault(key, owner)"
          @toggle-pin="owner => togglePinned(key, owner)" @toggle-publication="owner => toggleWorkflowInputExposure(key, owner)"
          @rename-publication="(value, owner) => updateWorkflowInputName(key, value, owner)"
          @pick-file="owner => pickFile(key, (field as InputFieldSchema).type, owner)" @pick-folder="owner => pickFolder(key, owner)"
          @focusin="trackParameterFocus(key, $event)" @focusout="trackParameterBlur($event)">
          <Button v-if="isFilesListField(key, field as InputFieldSchema)" :label="isDesktop() ? 'Select files' : 'Select in Datasets panel'"
            :icon="isDesktop() ? 'pi pi-file' : 'pi pi-folder-open'" class="p-button-sm files-source-picker" :disabled="isNodeEditingDisabled"
            data-testid="select-files-source" @click="pickFiles(key)" />
        </ParameterRow>
      </div>

      <!-- Outputs section (Fix 19: output template editing) -->
      <div v-if="nodeData.tool?.outputs" class="outputs-section">
        <h4>Outputs</h4>
        <div
          v-for="[key, field] in Object.entries(nodeData.tool.outputs)"
          :key="key"
          class="output-row"
        >
          <div class="output-header">
            <Button
              v-if="workflowInterfaceContext"
              :icon="isWorkflowOutputExposed(key) ? 'pi pi-minus' : 'pi pi-plus'"
              class="p-button-text p-button-sm param-action-btn interface-toggle-btn"
              :disabled="isNodeEditingDisabled"
              :title="isWorkflowOutputExposed(key) ? 'Remove workflow output' : 'Expose as workflow output'"
              :aria-pressed="isWorkflowOutputExposed(key)"
              :data-testid="`interface-output-toggle-${key}`"
              @click="toggleWorkflowOutputExposure(key)"
            />
            <span class="output-name">{{ fieldDisplayName(key, field as OutputFieldSchema) }}</span>
            <span class="output-type">{{ (field as OutputFieldSchema).type }}</span>
          </div>
          <InputText
            v-if="workflowInterfaceContext && isWorkflowOutputExposed(key)"
            :model-value="workflowInterfaceContext.outputs[workflowOutputIndex(key)].name"
            class="workflow-interface-name-input"
            :disabled="isNodeEditingDisabled"
            :data-testid="`workflow-output-name-${key}`"
            @update:model-value="updateWorkflowOutputName(key, $event as string)"
          />
          <!-- Editable path template — ProcessingTool outputs only.
               DataFrameTool Outputs are column declarations, not file paths. -->
          <InputText
            v-if="isOutputTemplateApplicable(field as OutputFieldSchema)"
            :model-value="nodeData.output_templates?.[key] ?? ''"
            :disabled="isNodeEditingDisabled"
            @update:model-value="updateOutputTemplate(key, $event as string)"
            placeholder="Output path template..."
            class="output-template-input"
            data-testid="output-template"
          />
        </div>
      </div>
      </div>

      <NodeResourcesTab
        v-show="activeTab === 'resources'"
        v-if="nodeData.nodeType === 'tool' && nodeData.tool?.tool_type !== 'DataFrameTool'"
        :resources="nodeData.resources ?? {}"
        :tool="nodeData.tool"
        :disabled="isNodeEditingDisabled"
        class="node-tab-panel"
        @change="updateResources"
      />
      <div
        v-show="activeTab === 'resources'"
        v-else
        class="node-tab-panel empty-tab"
        data-testid="node-resources-unavailable"
      >
        Worker resource overrides apply only to processing tools.
      </div>

      <div v-show="activeTab === 'execution'" class="node-tab-panel">
      <NodeOutputErrorBlock
        v-if="uiStore.selectedNodeIds[0]"
        :node-id="uiStore.selectedNodeIds[0]"
      />
      <!-- Execution output section: failed-node details and selected-node logs. -->
      <section class="execution-output-panel" data-testid="node-execution-output">
        <button
          type="button"
          class="execution-output-panel__header"
          :aria-expanded="!executionOutputCollapsed"
          @click="executionOutputCollapsed = !executionOutputCollapsed"
        >
          <i :class="executionOutputCollapsed ? 'pi pi-chevron-right' : 'pi pi-chevron-down'" />
          <span class="p-panel-title execution-output-panel__title">Execution Output</span>
        </button>

        <div v-show="!executionOutputCollapsed" class="execution-output-panel__body">
          <div
            v-if="selectedNodeStatus?.error || selectedNodeStatus?.traceback"
            class="node-runtime-error"
            data-testid="node-runtime-error"
          >
            <div v-if="selectedNodeStatus?.error" class="node-runtime-error__message">
              {{ selectedNodeStatus.error }}
            </div>
            <pre v-if="selectedNodeStatus?.traceback" class="node-runtime-error__traceback">{{ selectedNodeStatus.traceback }}</pre>
          </div>

          <div class="node-log-toolbar" aria-label="Node log levels">
            <ToggleButton
              v-for="level in ALL_LEVELS"
              :key="level"
              :model-value="nodeLogLevels.has(level)"
              :on-label="level"
              :off-label="level"
              size="small"
              :data-testid="`node-log-level-${level}`"
              @update:model-value="toggleNodeLogLevel(level)"
            />
          </div>

          <div v-if="filteredSelectedNodeLogs.length === 0" class="node-log-empty" data-testid="node-log-empty">
            No log messages
          </div>
          <div v-else class="node-log-list" data-testid="node-log-list">
            <div
              v-for="(entry, index) in filteredSelectedNodeLogs"
              :key="`${entry.timestamp}-${index}`"
              :class="['node-log-entry', `node-log-entry--${entry.level.toLowerCase()}`]"
              data-testid="node-log-entry"
            >
              <span class="node-log-entry__time" data-testid="node-log-timestamp">
                {{ formatLogTimestamp(entry.timestamp) }}
              </span>
              <span class="node-log-entry__level" data-testid="node-log-level">
                {{ entry.level }}
              </span>
              <span class="node-log-entry__message" data-testid="node-log-message">
                {{ entry.message }}
              </span>
            </div>
          </div>
        </div>
      </section>
      </div>

    </div>

    <Dialog
      :visible="destructiveDialog !== null"
      modal
      :header="destructiveDialogTitle"
      :closable="!destructiveActionPending"
      data-testid="node-destructive-dialog"
      @update:visible="value => { if (!value) closeDestructiveDialog() }"
    >
      <p>{{ destructiveDialogMessage }}</p>
      <p v-if="destructiveActionError" role="alert" data-testid="node-destructive-error">
        {{ destructiveActionError }}
      </p>
      <ul
        v-if="destructiveValidationErrors.length"
        class="node-destructive-validation-errors"
        data-testid="node-destructive-validation-errors"
      >
        <li v-for="(issue, index) in destructiveValidationErrors" :key="index">
          <strong v-if="issue.node">{{ issue.node }}{{ issue.field ? ` · ${issue.field}` : '' }}: </strong>
          <strong v-else-if="issue.field">{{ issue.field }}: </strong>
          {{ issue.detail }}
        </li>
      </ul>
      <template #footer>
        <Button
          label="Cancel"
          severity="secondary"
          :disabled="destructiveActionPending"
          data-testid="node-destructive-cancel"
          @click="closeDestructiveDialog"
        />
        <Button
          :label="destructiveDialog?.action === 'delete' ? 'Delete' : 'Clear'"
          :severity="destructiveDialog?.action === 'delete' ? 'danger' : 'primary'"
          :loading="destructiveActionPending"
          :disabled="destructiveActionPending"
          data-testid="node-destructive-confirm"
          @click="confirmDestructiveAction"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.node-panel {
  padding: 12px;
  font-size: 13px;
  height: 100%;
  overflow-y: auto;
}

.node-destructive-validation-errors {
  max-height: 18rem;
  overflow: auto;
  padding-left: 1.5rem;
  white-space: pre-wrap;
  user-select: text;
}

.node-destructive-validation-errors li + li {
  margin-top: 0.5rem;
}

.node-action-bar {
  display: flex;
  gap: 0.5rem;
  margin: 0.75rem 0;
}

.empty-state,
.multi-select {
  color: var(--p-text-muted-color);
  text-align: center;
  padding: 40px 20px;
}

.multi-select-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.node-validation-errors {
  background: color-mix(in srgb, var(--p-red-500, #dc2626) 10%, transparent);
  border: 1px solid var(--p-red-500, #dc2626);
  color: var(--p-red-700, #b91c1c);
  border-radius: 4px;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 12px;
}
.node-validation-errors__title {
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 4px;
}
.node-validation-errors ul {
  margin: 0;
  padding-left: 1rem;
}
.node-validation-errors li {
  margin: 2px 0;
}

.node-panel-header {
  border-bottom: 1px solid var(--p-content-border-color);
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.node-tabs {
  display: flex;
  border-bottom: 1px solid var(--p-content-border-color);
  margin-bottom: 0.75rem;
}

.node-tab {
  flex: 1;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--p-text-muted-color);
  padding: 0.55rem 0.35rem;
  cursor: pointer;
}

.node-tab--active {
  border-bottom-color: var(--p-primary-color);
  color: var(--p-primary-color);
  font-weight: 600;
}

.node-tab-panel { min-width: 0; }
.empty-tab { color: var(--p-text-muted-color); padding: 1rem 0; }

.node-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.node-name {
  font-weight: 700;
  font-size: 16px;
  cursor: pointer;
}

.name-input {
  width: 100%;
  font-size: 16px;
  font-weight: 700;
  flex: 1;
  margin-right: 8px;
}

.node-name-error {
  display: block;
  color: var(--p-red-500, #dc2626);
  margin-bottom: 4px;
}

.enabled-toggle {
  flex-shrink: 0;
}

.tool-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-name {
  color: var(--p-text-muted-color);
  font-size: 12px;
}

/* Fix 13: Package info styling */
.package-info {
  color: var(--p-text-muted-color);
  font-size: 11px;
  margin-top: 2px;
}

.status-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.status-unexecuted {
  background: var(--p-blue-50);
  color: var(--p-blue-700);
}
.status-executed {
  background: var(--p-green-50);
  color: var(--p-green-700);
}
.status-out-of-date {
  background: var(--p-yellow-50);
  color: var(--p-yellow-700);
}
.status-running {
  background: var(--p-blue-50);
  color: var(--p-blue-700);
}
.status-failed {
  background: var(--p-red-50);
  color: var(--p-red-700);
}

.execution-output-panel {
  margin-top: 12px;
  border-top: 1px solid var(--p-content-border-color);
  padding-top: 8px;
}

.execution-output-panel__header {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: 0;
  padding: 4px 0;
  cursor: pointer;
  color: inherit;
  width: 100%;
  text-align: left;
}

.execution-output-panel__header .pi {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.execution-output-panel__title {
  font-weight: 600;
  font-size: 12px;
}

.execution-output-panel__body {
  padding: 4px 0 8px;
}

.node-runtime-error {
  background: color-mix(in srgb, var(--p-red-500, #dc2626) 10%, transparent);
  border: 1px solid var(--p-red-500, #dc2626);
  color: var(--p-red-800, #991b1b);
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 8px;
}

.node-runtime-error__message {
  font-weight: 600;
  margin-bottom: 4px;
}

.node-runtime-error__traceback {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
}

.node-log-toolbar {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.node-log-empty {
  color: var(--p-text-muted-color);
  font-size: 12px;
}

.node-log-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.node-log-entry {
  display: grid;
  grid-template-columns: 6.5rem 4.25rem minmax(0, 1fr);
  gap: 6px;
  padding: 2px 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
}

.node-log-entry__time {
  color: var(--p-text-muted-color);
}

.node-log-entry__level {
  font-weight: 700;
}

.node-log-entry__message {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.node-log-entry--warning {
  color: var(--p-yellow-800, #92400e);
}

.node-log-entry--error {
  color: var(--p-red-700, #b91c1c);
}

/* Documentation panel (open by default, chevron before title) */
.doc-panel {
  margin-top: 12px;
  border-top: 1px solid var(--p-content-border-color);
  padding-top: 8px;
}

.doc-panel-header {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: 0;
  padding: 4px 0;
  cursor: pointer;
  color: inherit;
  width: 100%;
  text-align: left;
}

.doc-panel-header .pi {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.doc-panel-title {
  font-weight: 600;
  font-size: 12px;
}

.doc-panel-body {
  padding: 4px 0 8px;
}

.doc-text {
  margin: 0;
  font-size: 12px;
  color: var(--p-text-muted-color);
  line-height: 1.5;
  white-space: pre-wrap;
}

.parameters-section,
.outputs-section {
  margin-bottom: 16px;
}

h4 {
  margin: 0 0 8px;
  font-size: 12px;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
  letter-spacing: 0.5px;
}

.param-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 10px;
  min-width: 0;
}

.param-row :deep(.parameter-field-error) {
  width: 100%;
  min-width: 0;
}

.param-header {
  display: flex;
  align-items: center;
  gap: 4px;
}

.param-header label {
  font-weight: 500;
  font-size: 12px;
  color: var(--p-text-color);
  flex: 1;
}

.pin-toggle-btn[aria-pressed='true'] {
  color: var(--p-red-500);
}

.param-actions {
  display: flex;
  gap: 0;
}

.param-action-btn {
  width: 24px;
  height: 24px;
  padding: 0;
}

.param-action-btn .pi {
  font-size: 12px;
}

/* Fix 18: Help text */
.param-help {
  display: block;
  color: var(--p-text-muted-color);
  font-size: 11px;
  line-height: 1.4;
  padding: 2px 0 4px;
  overflow-wrap: anywhere;
}

/* Fix 16: None toggle button (now an icon-only button living in the
   .param-header alongside .param-actions). */
.param-toggles {
  display: flex;
  align-items: center;
  gap: 0;
  margin-left: 2px;
}

.none-toggle-btn[aria-pressed='true'] {
  color: var(--p-orange-500);
}

.interface-toggle-btn[aria-pressed='true'] {
  color: var(--p-primary-color);
}

.workflow-interface-name-input {
  width: 100%;
  font-size: 12px;
}

.interface-name-error {
  color: var(--p-red-700, #b91c1c);
  font-size: 12px;
  margin-bottom: 8px;
}

.null-indicator {
  font-size: 12px;
  color: var(--p-text-muted-color);
  font-style: italic;
}

.connected-source {
  font-size: 12px;
  color: var(--p-primary-color);
  font-style: italic;
}

.connect-hint {
  font-size: 12px;
  color: var(--p-text-muted-color);
  font-style: italic;
}

/* Gap 4: Slider + number side by side */
.slider-row {
  display: flex;
  align-items: center;
  gap: 8px;
  /* Keep the slider handle from hugging the left edge of the row. The handle
     is centered on the track endpoint, so half of it would overflow without
     inline padding. */
  padding-inline: 7px;
  box-sizing: border-box;
  max-width: 100%;
}

.slider-input {
  flex: 1;
  min-width: 0;
}

.slider-number {
  width: 72px;
  flex-shrink: 0;
  min-width: 0;
}

/* PrimeVue's InputNumber wraps an inner .p-inputtext that defaults to its
   intrinsic width; force it to fill the parent so it stays inside. */
.slider-number :deep(.p-inputtext) {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.param-input {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.list-input-row { display: grid; gap: 4px; }
.list-input { min-height: 7rem; resize: vertical; font: 12px ui-monospace, monospace; }
.list-input-error { color: var(--p-red-700, #b91c1c); }
.files-source-picker { justify-self: start; max-width: 100%; }

.param-number {
  display: flex;
}

.param-number :deep(.p-inputtext) {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.output-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
  border-bottom: 1px solid var(--p-surface-100);
}

.output-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.output-name {
  font-weight: 500;
  color: var(--p-text-color);
}
.output-type {
  color: var(--p-text-muted-color);
  font-size: 12px;
}

/* Fix 19: Output template input */
.output-template-input {
  width: 100%;
  font-size: 12px;
}

/* Path input row: text + picker buttons */
.path-input-row {
  display: flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
}

.path-input {
  flex: 1;
  min-width: 0;
}

.path-picker-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  flex-shrink: 0;
}

.path-picker-btn .pi {
  font-size: 12px;
}
</style>
