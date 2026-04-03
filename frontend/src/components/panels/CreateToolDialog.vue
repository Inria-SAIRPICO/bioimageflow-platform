<script setup lang="ts">
import { ref, computed } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Select from 'primevue/select'
import { api } from '@/api/client'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  created: [toolName: string]
}>()

const toolName = ref('')
const toolType = ref('ProcessingTool')

const toolTypeOptions = [
  { label: 'Processing Tool', value: 'ProcessingTool' },
  { label: 'Source Tool', value: 'SourceTool' },
  { label: 'Sink Tool', value: 'SinkTool' },
]

const createDisabled = computed(() => !toolName.value.trim())

async function onCreate() {
  if (createDisabled.value) return
  await api.post('/api/v1/tools', {
    name: toolName.value.trim(),
    tool_type: toolType.value,
  })
  emit('created', toolName.value.trim())
  toolName.value = ''
  toolType.value = 'ProcessingTool'
}

function onCancel() {
  emit('update:visible', false)
  toolName.value = ''
  toolType.value = 'ProcessingTool'
}

defineExpose({ toolName, toolType, createDisabled, onCreate, onCancel })
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
