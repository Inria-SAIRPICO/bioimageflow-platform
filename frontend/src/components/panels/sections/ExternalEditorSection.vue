<script setup lang="ts">
import { ref, watch } from 'vue'
import InputText from 'primevue/inputtext'
import type { Settings } from '@/api/types'

const props = defineProps<{ modelValue: Settings }>()
const emit = defineEmits<{
  (e: 'update:field', payload: { field: keyof Settings; value: unknown }): void
}>()

const editor = ref<string>(props.modelValue.external_editor ?? '')

watch(
  () => props.modelValue.external_editor,
  (value) => {
    editor.value = value ?? ''
  },
)

function commit() {
  const trimmed = editor.value.trim()
  emit('update:field', {
    field: 'external_editor',
    // Empty string means "unset" — send null so the server stores null.
    value: trimmed === '' ? null : trimmed,
  })
}
</script>

<template>
  <div class="settings-section">
    <label class="field-label" for="external-editor-input">
      External editor command
    </label>
    <InputText
      id="external-editor-input"
      v-model="editor"
      placeholder="code {file_path}"
      data-testid="external-editor-input"
      @blur="commit"
      @keydown.enter="commit"
    />
    <p class="help-text">
      <code>{file_path}</code> is replaced with the actual path when launched.
    </p>
  </div>
</template>

<style scoped>
.settings-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.field-label {
  font-weight: 600;
}
.help-text {
  margin: 0;
  color: var(--p-text-muted-color, #888);
  font-size: 0.85rem;
}
</style>
