<script setup lang="ts">
import { computed, ref } from 'vue'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Checkbox from 'primevue/checkbox'
import ToggleSwitch from 'primevue/toggleswitch'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Slider from 'primevue/slider'
import { useUIStore } from '@/stores/ui'
import { usePathPicker } from '@/composables/usePathPicker'
import { useGraphSync } from '@/composables/useGraphSync'
import { useValidationErrors } from '@/composables/useValidationErrors'
import type { InputFieldSchema } from '@/api/types'

// `OutputFieldSchema` is not exposed in the generated OpenAPI types because
// `ToolMetadata.outputs` is `dict[str, Any]` server-side (to accommodate the
// `{"_passthrough": true}` Passthrough marker for DataFrame tools). Mirror
// the library's wire shape here.
interface OutputFieldSchema {
  type: string
  default: unknown
  image_spec: Record<string, string[]> | null
}

// Connectable is a three-state string: `"never" | "not_by_default" | "by_default"`.
// For this PR we treat every non-`"never"` value as "pin visible"; the richer
// three-state UX (`not_by_default` → hidden pin with a reveal toggle) is a
// separate plan.
function canConnect(field: InputFieldSchema): boolean {
  return field.connectable !== 'never'
}

const { pickFile: pickFileNative, pickFolder: pickFolderNative, isDesktop } = usePathPicker()

const IMAGE_EXTS = ['*.tif', '*.tiff', '*.png', '*.jpg', '*.jpeg', '*.czi', '*.lsm', '*.nd2', '*.ome.tif', '*.ome.tiff']
const MASK_EXTS = ['*.tif', '*.tiff', '*.png']

function fileTypesForField(type: string): string[] {
  if (type === 'ImagePath') return IMAGE_EXTS
  if (type === 'MaskPath') return MASK_EXTS
  return []
}

const uiStore = useUIStore()
const { validationResult } = useGraphSync()
const { nodeErrors, getFieldErrors } = useValidationErrors(validationResult)

const selectedNodeErrors = computed(() => {
  const nodeId = uiStore.selectedNodeIds[0]
  if (!nodeId) return []
  return nodeErrors.value[nodeId] ?? []
})

const selectedNode = computed(() => {
  if (!uiStore.isSingleSelection) return null
  const nodeId = uiStore.selectedNodeIds[0]
  return uiStore.graphNodes.find((n: any) => n.id === nodeId) ?? null
})

const nodeData = computed(() => selectedNode.value?.data ?? null)

const editingName = ref(false)
const nameInput = ref('')

/** Track which optional fields have been set to null by the user */
const nulledFields = ref<Record<string, boolean>>({})

/** Track which parameter help sections are expanded */
const expandedHelp = ref<Record<string, boolean>>({})

/** Documentation section collapsed state (open by default) */
const docCollapsed = ref(false)

function startEditName() {
  if (!nodeData.value) return
  nameInput.value = nodeData.value.name
  editingName.value = true
}

function finishEditName() {
  if (!nodeData.value || !selectedNode.value) return
  const newName = nameInput.value.trim()
  if (newName && newName !== nodeData.value.name) {
    const exists = uiStore.graphNodes.some(
      (n: any) => n.id !== selectedNode.value!.id && n.data?.name === newName,
    )
    if (!exists) {
      nodeData.value.name = newName
    }
  }
  editingName.value = false
}

function updateParameter(key: string, value: unknown) {
  if (!nodeData.value) return
  nodeData.value.parameters[key] = value
}

function toggleEnabled() {
  if (!nodeData.value) return
  nodeData.value.enabled = !nodeData.value.enabled
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
  // Required fields are never in a "null" state — an undefined value just
  // means "not yet set" and the widget should render so the user can set it.
  if (!field || field.required) return false
  if (nulledFields.value[key]) return true
  return nodeData.value.parameters[key] === null || nodeData.value.parameters[key] === undefined
}

function togglePinned(key: string) {
  if (!nodeData.value) return
  if (!nodeData.value.pinnedInputs) {
    nodeData.value.pinnedInputs = {}
  }
  const current = nodeData.value.pinnedInputs[key] !== false
  nodeData.value.pinnedInputs[key] = !current
}

function isPinned(key: string): boolean {
  if (!nodeData.value?.pinnedInputs) return true
  return nodeData.value.pinnedInputs[key] !== false
}

function toggleHelp(key: string) {
  expandedHelp.value[key] = !expandedHelp.value[key]
}

function updateOutputTemplate(key: string, value: string) {
  if (!nodeData.value) return
  if (!nodeData.value.output_templates) {
    nodeData.value.output_templates = {}
  }
  nodeData.value.output_templates[key] = value
}

function isPathType(type: string): boolean {
  return ['Path', 'ImagePath', 'MaskPath'].includes(type)
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
            @update:model-value="toggleEnabled"
            class="enabled-toggle"
            data-testid="node-enabled-toggle"
          />
        </div>
        <div class="tool-info">
          <span class="tool-name">{{ nodeData.toolName }}</span>
          <span class="status-badge" :class="`status-${nodeData.status}`">
            {{ nodeData.status }}
          </span>
        </div>
        <!-- Fix 13: Package + version display -->
        <div v-if="nodeData.tool" class="package-info">
          {{ nodeData.tool.package }} v{{ nodeData.tool.package_version }}
        </div>
      </div>

      <!-- Parameters section -->
      <div v-if="nodeData.tool" class="parameters-section">
        <h4>Parameters</h4>
        <div
          v-for="[key, field] in Object.entries(nodeData.tool.inputs)"
          :key="key"
          class="param-row"
        >
          <div class="param-header">
            <!-- Pin visibility toggle (icon-only, before the label) -->
            <Button
              v-if="canConnect(field as InputFieldSchema)"
              :icon="isPinned(key) ? 'pi pi-times' : 'pi pi-arrow-right-arrow-left'"
              class="p-button-text p-button-sm param-action-btn pin-toggle-btn"
              :title="isPinned(key) ? 'Remove input pin' : 'Add input pin'"
              :aria-pressed="isPinned(key)"
              @click="togglePinned(key)"
              data-testid="pin-toggle"
            />
            <label>{{ key }}</label>
            <span class="param-actions">
              <!-- Fix 18: Help toggle button -->
              <Button
                v-if="(field as InputFieldSchema).description"
                icon="pi pi-info-circle"
                class="p-button-text p-button-sm param-action-btn"
                @click="toggleHelp(key)"
                :title="expandedHelp[key] ? 'Hide help' : 'Show help'"
                data-testid="help-toggle"
              />
              <!-- Fix 15: Reset to default button -->
              <Button
                icon="pi pi-undo"
                class="p-button-text p-button-sm param-action-btn"
                @click="resetToDefault(key)"
                title="Reset to default"
                data-testid="reset-default"
              />
            </span>
          </div>

          <!-- Fix 18: Collapsible help text -->
          <small
            v-if="expandedHelp[key] && (field as InputFieldSchema).description"
            class="param-help"
            data-testid="param-help-text"
          >
            {{ (field as InputFieldSchema).description }}
          </small>

          <!-- None toggle for Optional fields (Pin toggle is now an icon
               button in the param header — see above) -->
          <div v-if="!(field as InputFieldSchema).required" class="param-toggles">
            <label class="toggle-label" data-testid="none-toggle">
              <Checkbox
                :model-value="isFieldNulled(key)"
                binary
                @update:model-value="toggleNull(key)"
              />
              <span>None</span>
            </label>
          </div>

          <!-- Input widget (hidden when field is nulled) -->
          <template v-if="!isFieldNulled(key)">
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
            <!-- Gap 3: Enum/Literal dropdown when choices are available -->
            <Select
              v-else-if="hasChoices(field as InputFieldSchema)"
              :model-value="String(nodeData.parameters[key] ?? (field as InputFieldSchema).default ?? '')"
              :options="(field as InputFieldSchema).choices!"
              :data-testid="`choices-select-${key}`"
              @update:model-value="updateParameter(key, $event)"
            />
            <!-- Boolean checkbox -->
            <Checkbox
              v-else-if="(field as InputFieldSchema).type === 'bool'"
              :model-value="nodeData.parameters[key] ?? (field as InputFieldSchema).default ?? false"
              binary
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
                @update:model-value="updateParameter(key, $event)"
              />
              <InputNumber
                :model-value="(nodeData.parameters[key] as number) ?? ((field as InputFieldSchema).default as number)"
                :min="(field as InputFieldSchema).min ?? undefined"
                :max="(field as InputFieldSchema).max ?? undefined"
                :step="(field as InputFieldSchema).step ?? 1"
                :min-fraction-digits="1"
                class="slider-number"
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
                @update:model-value="updateParameter(key, $event)"
              />
              <Button
                icon="pi pi-file"
                class="p-button-text p-button-sm path-picker-btn"
                title="Select file"
                :data-testid="`select-file-${key}`"
                @click="pickFile(key, (field as InputFieldSchema).type)"
              />
              <Button
                v-if="(field as InputFieldSchema).type === 'Path' && isDesktop()"
                icon="pi pi-folder-open"
                class="p-button-text p-button-sm path-picker-btn"
                title="Select folder"
                :data-testid="`select-folder-${key}`"
                @click="pickFolder(key)"
              />
            </div>
            <!-- Text / non-connectable string input -->
            <InputText
              v-else-if="!canConnect(field as InputFieldSchema) || (field as InputFieldSchema).type === 'str'"
              :model-value="String(nodeData.parameters[key] ?? (field as InputFieldSchema).default ?? '')"
              @update:model-value="updateParameter(key, $event)"
            />
            <!-- Fallback: connectable-only field with no manual widget -->
            <span v-else class="connect-hint">Connect to upstream node</span>
          </template>
          <span v-else class="null-indicator">null</span>
        </div>
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
            <span class="output-name">{{ key }}</span>
            <span class="output-type">{{ (field as OutputFieldSchema).type }}</span>
          </div>
          <!-- Fix 19: Editable template for path-typed outputs -->
          <InputText
            v-if="isPathType((field as OutputFieldSchema).type)"
            :model-value="nodeData.output_templates?.[key] ?? ''"
            @update:model-value="updateOutputTemplate(key, $event as string)"
            placeholder="Output path template..."
            class="output-template-input"
            data-testid="output-template"
          />
        </div>
      </div>

      <!-- Documentation section, docked at the bottom, open by default.
           Chevron is rendered before the "Documentation" label and toggles
           the section. -->
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

/* Documentation panel (bottom, open by default, chevron before title) */
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
}

/* Fix 16 + 17: Toggle row */
.param-toggles {
  display: flex;
  gap: 12px;
  align-items: center;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--p-text-muted-color);
  cursor: pointer;
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
