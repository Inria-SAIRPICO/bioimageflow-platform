<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Checkbox from 'primevue/checkbox'
import Select from 'primevue/select'
import Slider from 'primevue/slider'
import ParameterFieldError from './ParameterFieldError.vue'
import type { GraphValidationError, InputFieldSchema } from '@/api/types'
import { fieldDisplayName } from '@/utils/displayNames'

const props = defineProps<{
  fieldKey: string; field: InputFieldSchema; value: unknown
  inherited?: boolean; connectedSource?: string | null; disabled?: boolean
  canPin?: boolean; pinned?: boolean; canPublish?: boolean; published?: boolean; publishedName?: string
  filePicker?: boolean; folderPicker?: boolean; widgetTestId?: string; errors: GraphValidationError[]
  unsupported?: string; owner?: string
}>()
const emit = defineEmits<{
  updateValue: [value: unknown, owner?: string]; reset: [owner?: string]; togglePin: [owner?: string]; togglePublication: [owner?: string]
  renamePublication: [name: string, owner?: string]; pickFile: [owner?: string]; pickFolder: [owner?: string]
}>()
// A mounted row belongs to one registration/node/input even after a queued blur.
const owner = props.owner
function update(value: unknown) {
  if (owner === undefined) emit('updateValue', value)
  else emit('updateValue', value, owner)
}
function action(name: 'reset' | 'togglePin' | 'togglePublication' | 'pickFile' | 'pickFolder') {
  const args: [] | [string] = owner === undefined ? [] : [owner]
  const actions = {
    reset: () => emit('reset', ...args), togglePin: () => emit('togglePin', ...args),
    togglePublication: () => emit('togglePublication', ...args), pickFile: () => emit('pickFile', ...args),
    pickFolder: () => emit('pickFolder', ...args),
  }
  actions[name]()
}
function rename(value: unknown) { emit('renamePublication', String(value), owner) }
const editingNull = ref(false)
const listError = ref('')
const listDraft = ref<string | null>(null)
watch(() => JSON.stringify(props.value), () => { listDraft.value = null; listError.value = ''; editingNull.value = false })
const nulled = computed(() => props.value === null && props.field.nullable && !editingNull.value)
const connected = computed(() => props.connectedSource != null)
const placeholder = computed(() => props.inherited && props.value === undefined ? 'Inherited / unset' : undefined)
const numeric = computed(() => typeof props.value === 'number' ? props.value : null)
const isPath = computed(() => ['Path', 'ImageFile', 'MaskPath'].includes(props.field.type))
const slider = computed(() => props.field.type === 'float' && props.field.min != null && props.field.max != null && props.field.step != null && numeric.value !== null)
const listText = computed(() => listDraft.value ?? (props.value === undefined ? '' : JSON.stringify(props.value, null, 2)))
// InputNumber's default precision truncates fine scientific parameters. Keep all
// authored fractional digits, including values finer than the suggested step.
const fractionDigits = computed(() => props.field.type === 'int' ? 0 : 20)
function toggleNone() {
  if (nulled.value) {
    if (props.field.default != null) update(props.field.default)
    else editingNull.value = true
  } else { editingNull.value = false; update(null) }
}
function reset() { editingNull.value = false; listDraft.value = null; listError.value = ''; action('reset') }
function changeList(event: Event) {
  const text = (event.target as HTMLTextAreaElement).value
  listDraft.value = text
  let value: unknown
  try {
    value = JSON.parse(text)
    if (!Array.isArray(value)) throw new Error('Value must be a JSON array')
    listError.value = ''
  } catch (error) { listError.value = error instanceof Error ? error.message : 'Invalid JSON array'; return }
  update(value)
}
</script>

<template>
  <div class="param-row">
    <div class="param-header">
      <Button v-if="canPublish" :icon="published ? 'pi pi-minus' : 'pi pi-plus'"
        class="p-button-text p-button-sm param-action-btn interface-toggle-btn" :disabled="disabled"
        :title="published ? 'Remove workflow input' : 'Expose as workflow input'" :aria-pressed="!!published"
        :data-testid="`interface-input-toggle-${fieldKey}`" @click="action('togglePublication')" />
      <Button v-if="canPin || connected" :icon="pinned || connected ? 'pi pi-times' : 'pi pi-arrow-right-arrow-left'"
        class="p-button-text p-button-sm param-action-btn pin-toggle-btn" :disabled="disabled || connected"
        :title="connected ? 'Connected input pins cannot be hidden' : pinned ? 'Remove input pin' : 'Add input pin'"
        :aria-pressed="!!pinned || connected" data-testid="pin-toggle" @click="action('togglePin')" />
      <label>{{ fieldDisplayName(fieldKey, field) }}</label>
      <span class="param-actions"><Button icon="pi pi-undo" class="p-button-text p-button-sm param-action-btn"
        :disabled="disabled || connected" title="Reset to default" data-testid="reset-default" @click="reset" /></span>
      <Button v-if="field.nullable" :icon="nulled ? 'pi pi-pencil' : 'pi pi-ban'"
        class="p-button-text p-button-sm param-action-btn none-toggle-btn" :disabled="disabled || connected"
        :title="nulled ? 'Set value (currently null)' : 'Set to null'" :aria-pressed="nulled"
        data-testid="none-toggle" @click="toggleNone" />
    </div>
    <InputText v-if="canPublish && published" :model-value="publishedName" class="workflow-interface-name-input"
      :disabled="disabled" :data-testid="`workflow-input-name-${fieldKey}`" @update:model-value="rename($event)" />
    <small v-if="field.description" class="param-help" data-testid="param-help-text">{{ field.description }}</small>
    <small v-if="inherited && !connected" class="inherited-state">{{ value === undefined ? 'Inherited from internal workflow' : 'Using workflow default' }}</small>
    <ParameterFieldError :errors="errors">
      <span v-if="connected" class="connected-source">{{ connectedSource }}</span>
      <span v-else-if="unsupported" class="unsupported-value">{{ unsupported }}</span>
      <span v-else-if="nulled" class="null-indicator">null</span>
      <span v-else-if="['ImageShared', 'SharedArray'].includes(field.type)" class="connect-hint" data-testid="image-shared-hint">Connect to upstream node</span>
      <div v-else-if="['list', 'tuple'].includes(field.type)" class="list-input-row">
        <textarea :value="listText" class="param-input list-input" :placeholder="placeholder" :disabled="disabled"
          :data-testid="widgetTestId ?? `list-input-${fieldKey}`" @change="changeList" />
        <small v-if="listError" class="list-input-error">{{ listError }}</small>
      </div>
      <Select v-else-if="field.choices?.length" :model-value="value == null ? undefined : String(value)" :options="field.choices"
        class="param-input" :disabled="disabled" :placeholder="placeholder" :data-testid="widgetTestId ?? `choices-select-${fieldKey}`"
        @update:model-value="update($event)" />
      <Checkbox v-else-if="field.type === 'bool'" :model-value="value === true" :indeterminate="value === undefined" binary
        :disabled="disabled" :data-testid="widgetTestId" @update:model-value="update($event)" />
      <div v-else-if="slider" class="slider-row" :data-testid="`slider-row-${fieldKey}`">
        <Slider :model-value="numeric!" :min="field.min!" :max="field.max!" :step="field.step!" class="slider-input"
          :disabled="disabled" @update:model-value="update($event)" />
        <InputNumber :model-value="numeric" :min="field.min ?? undefined" :max="field.max ?? undefined" :step="field.step ?? 1"
          :min-fraction-digits="1" :max-fraction-digits="fractionDigits" :use-grouping="false" show-buttons class="slider-number"
          :disabled="disabled" :data-testid="widgetTestId" @update:model-value="update($event)" />
      </div>
      <InputNumber v-else-if="field.type === 'int' || field.type === 'float'" :model-value="numeric"
        :min="field.min ?? undefined" :max="field.max ?? undefined" :step="field.step ?? 1" :min-fraction-digits="field.type === 'float' ? 1 : 0"
        :max-fraction-digits="fractionDigits" :use-grouping="false" show-buttons class="param-input param-number"
        :placeholder="placeholder" :disabled="disabled" :data-testid="widgetTestId" @update:model-value="update($event)" />
      <div v-else-if="isPath" class="path-input-row" :data-testid="`path-input-${fieldKey}`">
        <InputText :model-value="value == null ? '' : String(value)" class="path-input" :placeholder="placeholder" :disabled="disabled"
          :data-testid="widgetTestId" @update:model-value="update($event)" />
        <Button v-if="filePicker" icon="pi pi-file" class="p-button-text p-button-sm path-picker-btn" title="Select file"
          :disabled="disabled" :data-testid="`select-file-${fieldKey}`" @click="action('pickFile')" />
        <Button v-if="folderPicker" icon="pi pi-folder-open" class="p-button-text p-button-sm path-picker-btn" title="Select folder"
          :disabled="disabled" :data-testid="`select-folder-${fieldKey}`" @click="action('pickFolder')" />
      </div>
      <InputText v-else-if="field.type === 'str' || ['Path', 'ImageFile', 'MaskPath'].includes(field.type)" :model-value="value == null ? '' : String(value)"
        class="param-input" :disabled="disabled" :placeholder="placeholder" :data-testid="widgetTestId" @update:model-value="update($event)" />
      <span v-else class="connect-hint">{{ inherited ? 'Inherited / unset' : 'Connect to upstream node' }}</span>
    </ParameterFieldError>
    <slot />
  </div>
</template>

<style scoped>
.param-row { display: flex; flex-direction: column; gap: .35rem; margin-bottom: .9rem; }
.param-header { display: flex; align-items: center; gap: .25rem; }
.param-header label { flex: 1; font-weight: 500; font-size: .85rem; }
.param-actions { margin-left: auto; }
.param-action-btn { width: 1.6rem; height: 1.6rem; padding: .15rem; }
.param-help, .connect-hint, .null-indicator, .unsupported-value { font-size: .8rem; color: var(--p-text-muted-color); }
.param-help { white-space: pre-wrap; }
.param-input, .param-number, .workflow-interface-name-input { width: 100%; }
.param-number :deep(input) { width: 100%; min-width: 0; }
.slider-row, .path-input-row { display: flex; align-items: center; gap: .5rem; min-width: 0; }
.slider-input { flex: 1; margin: .5rem; }
.slider-number { width: 8rem; }
.slider-number :deep(input) { width: 100%; min-width: 0; }
.path-input { flex: 1; min-width: 0; }
.path-picker-btn { flex: 0 0 1.8rem; }
.list-input { min-height: 5rem; resize: vertical; font-family: monospace; background: var(--p-inputtext-background); color: var(--p-inputtext-color); border: 1px solid var(--p-inputtext-border-color); border-radius: var(--p-inputtext-border-radius); padding: .5rem; }
.list-input-error { color: var(--p-red-500); }
.connected-source { font-size: .85rem; color: var(--p-primary-color); }
</style>
