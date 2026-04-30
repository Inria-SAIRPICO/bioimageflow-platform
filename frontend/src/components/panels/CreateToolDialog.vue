<script setup lang="ts">
import { ref, computed } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Select from 'primevue/select'
import { useToolRegistryStore } from '@/stores/toolRegistry'
import type { ToolCreateResponse } from '@/api/types'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  created: [response: ToolCreateResponse]
}>()

const toolRegistry = useToolRegistryStore()
const toolName = ref('')
const toolType = ref('ProcessingTool')

const toolTypeOptions = [
  { label: 'Processing Tool', value: 'ProcessingTool' },
  { label: 'DataFrame Tool', value: 'DataFrameTool' },
]

const pythonKeywords = new Set([
  'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
  'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
  'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
  'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
  'try', 'while', 'with', 'yield',
])

const trimmedName = computed(() => toolName.value.trim())

const isValidToolName = computed(() => {
  const name = trimmedName.value
  if (!name || name !== toolName.value) return false
  if (name.includes('/') || name.includes('\\') || name.includes('..')) return false
  if (/\s/.test(name)) return false
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) return false
  if (pythonKeywords.has(name)) return false
  if (!/^[A-Z]/.test(name)) return false
  return toolRegistry.getToolByName(name) === undefined
})

const createDisabled = computed(() => !isValidToolName.value)

async function onCreate() {
  if (createDisabled.value) return
  const response = await toolRegistry.createTool({
    name: trimmedName.value,
    tool_type: toolType.value as 'ProcessingTool' | 'DataFrameTool',
  })
  emit('created', response)
  toolName.value = ''
  toolType.value = 'ProcessingTool'
}

function onCancel() {
  emit('update:visible', false)
  toolName.value = ''
  toolType.value = 'ProcessingTool'
}

defineExpose({ toolName, toolType, createDisabled, isValidToolName, onCreate, onCancel })
</script>

<template>
  <Dialog
    :visible="props.visible"
    header="Create Tool"
    modal
    @update:visible="emit('update:visible', $event)"
  >
    <div class="create-tool-form">
      <div class="field">
        <label for="tool-name">Name</label>
        <InputText
          id="tool-name"
          v-model="toolName"
          data-testid="tool-name-input"
          placeholder="Enter tool name"
          class="w-full"
        />
      </div>
      <div class="field">
        <label for="tool-type">Type</label>
        <Select
          id="tool-type"
          v-model="toolType"
          :options="toolTypeOptions"
          option-label="label"
          option-value="value"
          data-testid="tool-type-select"
          class="w-full"
        />
      </div>
    </div>
    <template #footer>
      <Button label="Cancel" text @click="onCancel" />
      <Button
        label="Create"
        :disabled="createDisabled"
        data-testid="create-tool-submit"
        @click="onCreate"
      />
    </template>
  </Dialog>
</template>
