<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch, type ComputedRef } from 'vue'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Checkbox from 'primevue/checkbox'
import ToggleSwitch from 'primevue/toggleswitch'
import ToggleButton from 'primevue/togglebutton'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Slider from 'primevue/slider'
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
import ParameterFieldError from '@/components/panels/shared/ParameterFieldError.vue'
import NodeOutputErrorBlock from '@/components/panels/shared/NodeOutputErrorBlock.vue'
import type {
  GraphValidationError,
  InputFieldSchema,
  WorkflowInput,
  WorkflowOutput,
} from '@/api/types'
import { fieldDisplayName } from '@/utils/displayNames'
import { IMAGE_PATH_GLOBS } from '@/utils/imagePaths'

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

// Connectable is a three-state string: `"never" | "not_by_default" | "by_default"`.
// For this PR we treat every non-`"never"` value as "pin visible"; the richer
// three-state UX (`not_by_default` → hidden pin with a reveal toggle) is a
// separate plan.
function canConnect(field: InputFieldSchema): boolean {
  return field.connectable !== 'never'
}

const { pickFile: pickFileNative, pickFolder: pickFolderNative, isDesktop } = usePathPicker()

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
const interfaceNameError = ref<string | null>(null)
const listInputErrors = ref<Record<string, string>>({})

const editingName = ref(false)
const nameInput = ref('')

/** Track which optional fields have been set to null by the user */
const nulledFields = ref<Record<string, boolean>>({})

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
  editingName.value = true
}

function finishEditName() {
  const nodeId = selectedNode.value?.id
  if (nodeId) canvasCommands.renameNode(nodeId, nameInput.value)
  editingName.value = false
}

function updateParameter(key: string, value: unknown) {
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  canvasCommands.updateParameter(nodeId, key, value)
}

function listParameterText(key: string, field: InputFieldSchema): string {
  return JSON.stringify(nodeData.value.parameters[key] ?? field.default ?? [], null, 2)
}

function updateListParameter(key: string, event: Event) {
  let value: unknown
  try {
    value = JSON.parse((event.target as HTMLTextAreaElement).value)
    if (!Array.isArray(value)) throw new Error('Value must be a JSON array')
    delete listInputErrors.value[key]
  } catch (error) {
    listInputErrors.value[key] = error instanceof Error ? error.message : 'Invalid JSON array'
    return
  }
  // Keep command/graph failures out of the field's JSON validation message.
  // In particular, an editor blur caused by selecting another node must never
  // display an unrelated graph error below that node's list input.
  updateParameter(key, value)
}

watch(() => selectedNode.value?.id, () => {
  listInputErrors.value = {}
})

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

function resetToDefault(key: string) {
  if (!nodeData.value?.tool) return
  const field = nodeData.value.tool.inputs[key] as InputFieldSchema | undefined
  if (field) {
    updateParameter(key, field.default ?? null)
    // If it was nulled, un-null it
    nulledFields.value[key] = false
  }
}

function toggleNull(key: string) {
  if (!nodeData.value) return
  const isCurrentlyNull = nulledFields.value[key] ?? (nodeData.value.parameters[key] === null || nodeData.value.parameters[key] === undefined)
  if (isCurrentlyNull) {
    // Restore to default
    const field = nodeData.value.tool?.inputs[key] as InputFieldSchema | undefined
    const defaultVal = field?.default ?? ''
    updateParameter(key, defaultVal)
    nulledFields.value[key] = false
  } else {
    // Set to null
    updateParameter(key, null)
    nulledFields.value[key] = true
  }
}

function isFieldNulled(key: string): boolean {
  if (!nodeData.value) return false
  const field = nodeData.value.tool?.inputs[key] as InputFieldSchema | undefined
  // Non-nullable fields can never be in a "null" state. For required-but-
  // nullable fields, an undefined value is treated as null until the user
  // toggles to a real value (the toggle is the only affordance to set one).
  if (!field || !field.nullable) return false
  if (nulledFields.value[key]) return true
  return nodeData.value.parameters[key] === null || nodeData.value.parameters[key] === undefined
}

function togglePinned(key: string) {
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  canvasCommands.setInputPinned(nodeId, key, !isPinned(key))
}

function isPinned(key: string): boolean {
  if (key in (nodeData.value?.connectedInputs ?? {})) return true
  if (!nodeData.value?.pinnedInputs) return true
  return nodeData.value.pinnedInputs[key] !== false
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

function isImageSharedType(type: string): boolean {
  return ['ImageShared', 'SharedArray'].includes(type)
}

function hasChoices(field: InputFieldSchema): boolean {
  return Array.isArray(field.choices) && field.choices.length > 0
}

function isSliderField(field: InputFieldSchema): boolean {
  return field.type === 'float' && field.min != null && field.max != null && field.step != null
}

const workflowInterfaceContext = computed(() => (
  nodeData.value?.workflowInterfaceContext
  ?? nodeData.value?.nestedWorkflowContext
  ?? null
))

function selectedInternalNodeId(): string {
  return selectedNode.value?.id ?? ''
}

function workflowInputIndex(fieldName: string): number {
  const ctx = workflowInterfaceContext.value
  if (!ctx) return -1
  return (ctx.inputs ?? []).findIndex((item: WorkflowInput) => item.targets.some(target => (
    target.node === selectedInternalNodeId()
    && target.port.kind === 'field'
    && target.port.name === fieldName
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

function toggleWorkflowInputExposure(fieldName: string) {
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  applyInterfaceResult(canvasCommands.toggleWorkflowInput(nodeId, fieldName))
}

function updateWorkflowInputName(fieldName: string, value: string) {
  const nodeId = selectedNode.value?.id
  if (!nodeId) return
  applyInterfaceResult(
    canvasCommands.renameWorkflowInput(nodeId, fieldName, value),
  )
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

async function pickFile(key: string, type: string) {
  const path = await pickFileNative({
    parameterName: key,
    fileTypes: fileTypesForField(type),
  })
  if (path !== null) {
    updateParameter(key, path)
  }
}

async function pickFolder(key: string) {
  const path = await pickFolderNative({ parameterName: key })
  if (path !== null) {
    updateParameter(key, path)
  }
}
</script>

<template>
  <div class="node-panel" data-testid="panel-nodePanel">
    <div v-if="!uiStore.hasSelection" class="empty-state">
      Select a node to view its properties
    </div>

    <div v-else-if="uiStore.isMultiSelection" class="multi-select">
      <p>{{ uiStore.selectedNodeIds.length }} nodes selected</p>
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
            :disabled="isNodeEditingDisabled"
            @blur="finishEditName"
            @keydown.enter="finishEditName"
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
      </div>

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

      <!-- Parameters section -->
      <div v-if="nodeData.tool" class="parameters-section">
        <h4>Parameters</h4>
        <div
          v-if="interfaceNameError"
          class="interface-name-error"
          data-testid="interface-name-error"
        >
          {{ interfaceNameError }}
        </div>
        <div
          v-for="[key, field] in Object.entries(nodeData.tool.inputs)"
          :key="key"
          class="param-row"
          @focusin="trackParameterFocus(key, $event)"
          @focusout="trackParameterBlur($event)"
        >
          <div class="param-header">
            <Button
              v-if="workflowInterfaceContext && canConnect(field as InputFieldSchema)"
              :icon="isWorkflowInputExposed(key) ? 'pi pi-minus' : 'pi pi-plus'"
              class="p-button-text p-button-sm param-action-btn interface-toggle-btn"
              :disabled="isNodeEditingDisabled"
              :title="isWorkflowInputExposed(key) ? 'Remove workflow input' : 'Expose as workflow input'"
              :aria-pressed="isWorkflowInputExposed(key)"
              @click="toggleWorkflowInputExposure(key)"
              :data-testid="`interface-input-toggle-${key}`"
            />
            <!-- Pin visibility toggle (icon-only, before the label) -->
            <Button
              v-if="canConnect(field as InputFieldSchema)"
              :icon="isPinned(key) ? 'pi pi-times' : 'pi pi-arrow-right-arrow-left'"
              class="p-button-text p-button-sm param-action-btn pin-toggle-btn"
              :disabled="isNodeEditingDisabled"
              :title="isPinned(key) ? 'Remove input pin' : 'Add input pin'"
              :aria-pressed="isPinned(key)"
              @click="togglePinned(key)"
              data-testid="pin-toggle"
            />
            <label>{{ fieldDisplayName(key, field as InputFieldSchema) }}</label>
            <span class="param-actions">
              <!-- Fix 15: Reset to default button -->
              <Button
                icon="pi pi-undo"
                class="p-button-text p-button-sm param-action-btn"
                :disabled="isNodeEditingDisabled"
                @click="resetToDefault(key)"
                title="Reset to default"
                data-testid="reset-default"
              />
            </span>
            <!-- None toggle for nullable fields. Two-state icon button —
                 the icon shows the action that will happen on click: pencil
                 when the field is null (click to edit), Ø (pi-ban) when the
                 field is editable (click to set to null). -->
            <span v-if="(field as InputFieldSchema).nullable" class="param-toggles">
              <Button
                :icon="isFieldNulled(key) ? 'pi pi-pencil' : 'pi pi-ban'"
                class="p-button-text p-button-sm param-action-btn none-toggle-btn"
                :disabled="isNodeEditingDisabled"
                :title="isFieldNulled(key) ? 'Set value (currently null)' : 'Set to null'"
                :aria-pressed="isFieldNulled(key)"
                @click="toggleNull(key)"
                data-testid="none-toggle"
              />
            </span>
          </div>

          <InputText
            v-if="workflowInterfaceContext && isWorkflowInputExposed(key)"
            :model-value="workflowInterfaceContext.inputs[workflowInputIndex(key)].name"
            class="workflow-interface-name-input"
            :disabled="isNodeEditingDisabled"
            :data-testid="`workflow-input-name-${key}`"
            @update:model-value="updateWorkflowInputName(key, $event as string)"
          />

          <!-- Fix 18: Always-visible help text -->
          <small
            v-if="(field as InputFieldSchema).description"
            class="param-help"
            data-testid="param-help-text"
          >
            {{ (field as InputFieldSchema).description }}
          </small>

          <!-- Input widget (hidden when field is nulled) -->
          <ParameterFieldError v-if="!isFieldNulled(key)" :errors="fieldErrorsFor(key)">
            <!-- Connected input: show source label -->
            <span v-if="key in nodeData.connectedInputs" class="connected-source">
              {{ nodeData.connectedInputs[key] }}
            </span>
            <!-- Gap 5: ImageShared/SharedArray — connection-only, no manual input -->
            <span
              v-else-if="isImageSharedType((field as InputFieldSchema).type)"
              class="connect-hint"
              data-testid="image-shared-hint"
            >
              Connect to upstream node
            </span>
            <!-- Generic list editor. Lists remain editable even when their element type has no special widget. -->
            <div v-else-if="(field as InputFieldSchema).type === 'list'" class="list-input-row">
              <textarea
                :value="listParameterText(key, field as InputFieldSchema)"
                class="param-input list-input"
                :disabled="isNodeEditingDisabled"
                :data-testid="`list-input-${key}`"
                @change="updateListParameter(key, $event)"
              />
              <small v-if="listInputErrors[key]" class="list-input-error">{{ listInputErrors[key] }}</small>
            </div>
            <!-- Gap 3: Enum/Literal dropdown when choices are available -->
            <Select
              v-else-if="hasChoices(field as InputFieldSchema)"
              :model-value="String(nodeData.parameters[key] ?? (field as InputFieldSchema).default ?? '')"
              :options="(field as InputFieldSchema).choices!"
              class="param-input"
              :disabled="isNodeEditingDisabled"
              :data-testid="`choices-select-${key}`"
              @update:model-value="updateParameter(key, $event)"
            />
            <!-- Boolean checkbox -->
            <Checkbox
              v-else-if="(field as InputFieldSchema).type === 'bool'"
              :model-value="nodeData.parameters[key] ?? (field as InputFieldSchema).default ?? false"
              binary
              :disabled="isNodeEditingDisabled"
              @update:model-value="updateParameter(key, $event)"
            />
            <!-- Gap 4: Slider + InputNumber for float fields with min, max, and step all defined -->
            <div
              v-else-if="isSliderField(field as InputFieldSchema)"
              class="slider-row"
              :data-testid="`slider-row-${key}`"
            >
              <Slider
                :model-value="(nodeData.parameters[key] as number) ?? ((field as InputFieldSchema).default as number) ?? (field as InputFieldSchema).min!"
                :min="(field as InputFieldSchema).min!"
                :max="(field as InputFieldSchema).max!"
                :step="(field as InputFieldSchema).step!"
                class="slider-input"
                :disabled="isNodeEditingDisabled"
                @update:model-value="updateParameter(key, $event)"
              />
              <InputNumber
                :model-value="(nodeData.parameters[key] as number) ?? ((field as InputFieldSchema).default as number)"
                :min="(field as InputFieldSchema).min ?? undefined"
                :max="(field as InputFieldSchema).max ?? undefined"
                :step="(field as InputFieldSchema).step ?? 1"
                :min-fraction-digits="1"
                class="slider-number"
                :disabled="isNodeEditingDisabled"
                @update:model-value="updateParameter(key, $event)"
              />
            </div>
            <!-- Standard numeric input (int, or float without full slider metadata) -->
            <InputNumber
              v-else-if="(field as InputFieldSchema).type === 'int' || (field as InputFieldSchema).type === 'float'"
              :model-value="nodeData.parameters[key] as number ?? (field as InputFieldSchema).default as number"
              :min="(field as InputFieldSchema).min ?? undefined"
              :max="(field as InputFieldSchema).max ?? undefined"
              :step="(field as InputFieldSchema).step ?? 1"
              :min-fraction-digits="(field as InputFieldSchema).type === 'float' ? 1 : 0"
              show-buttons
              class="param-input param-number"
              :disabled="isNodeEditingDisabled"
              @update:model-value="updateParameter(key, $event)"
            />
            <!-- Path-typed input: text input + native file/folder picker buttons -->
            <div
              v-else-if="isPathType((field as InputFieldSchema).type)"
              class="path-input-row"
              :data-testid="`path-input-${key}`"
            >
              <InputText
                :model-value="String(nodeData.parameters[key] ?? (field as InputFieldSchema).default ?? '')"
                class="path-input"
                :disabled="isNodeEditingDisabled"
                @update:model-value="updateParameter(key, $event)"
              />
              <Button
                v-if="showsFilePicker(field as InputFieldSchema)"
                icon="pi pi-file"
                class="p-button-text p-button-sm path-picker-btn"
                title="Select file"
                :disabled="isNodeEditingDisabled"
                :data-testid="`select-file-${key}`"
                @click="pickFile(key, (field as InputFieldSchema).type)"
              />
              <Button
                v-if="showsFolderPicker(field as InputFieldSchema)"
                icon="pi pi-folder-open"
                class="p-button-text p-button-sm path-picker-btn"
                title="Select folder"
                :disabled="isNodeEditingDisabled"
                :data-testid="`select-folder-${key}`"
                @click="pickFolder(key)"
              />
            </div>
            <!-- Text / non-connectable string input -->
            <InputText
              v-else-if="!canConnect(field as InputFieldSchema) || (field as InputFieldSchema).type === 'str'"
              :model-value="String(nodeData.parameters[key] ?? (field as InputFieldSchema).default ?? '')"
              class="param-input"
              :disabled="isNodeEditingDisabled"
              @update:model-value="updateParameter(key, $event)"
            />
            <!-- Fallback: connectable-only field with no manual widget -->
            <span v-else class="connect-hint">Connect to upstream node</span>
          </ParameterFieldError>
          <span v-else class="null-indicator">null</span>
        </div>
      </div>

      <!-- Execution error display: above Outputs section, only when failed -->
      <NodeOutputErrorBlock
        v-if="uiStore.selectedNodeIds[0]"
        :node-id="uiStore.selectedNodeIds[0]"
      />

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
</template>

<style scoped>
.node-panel {
  padding: 12px;
  font-size: 13px;
  height: 100%;
  overflow-y: auto;
}

.empty-state,
.multi-select {
  color: var(--p-text-muted-color);
  text-align: center;
  padding: 40px 20px;
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
