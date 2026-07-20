<script setup lang="ts">
import { ref, watch } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import type { Settings } from '@/stores/settings'
import { isDesktop, selectFolder } from '@/utils/nativeDialogs'

const props = defineProps<{ modelValue: Settings }>()
const emit = defineEmits<{
  (e: 'update:field', payload: { field: keyof Settings; value: unknown }): void
}>()

const path = ref<string>(props.modelValue.napari_env_path ?? '')

watch(
  () => props.modelValue.napari_env_path,
  (value) => {
    path.value = value ?? ''
  },
)

function commit() {
  const trimmed = path.value.trim()
  emit('update:field', {
    field: 'napari_env_path',
    value: trimmed === '' ? null : trimmed,
  })
}

async function browse() {
  const picked = await selectFolder('Select Napari environment')
  if (picked) {
    path.value = picked
    commit()
  }
}
</script>

<template>
  <div class="settings-section">
    <label class="field-label" for="napari-env-input">Napari environment path</label>
    <div class="field-row">
      <InputText
        id="napari-env-input"
        v-model="path"
        data-testid="napari-env-input"
        class="grow"
        @blur="commit"
        @keydown.enter="commit"
      />
      <Button
        v-if="isDesktop()"
        label="Browse..."
        severity="secondary"
        data-testid="napari-browse-button"
        @click="browse"
      />
    </div>
    <p class="help-text">
      Path to a Python environment with Napari installed. Leave empty to disable.
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
.field-row {
  display: flex;
  gap: 0.5rem;
}
.grow {
  flex: 1;
}
.help-text {
  margin: 0;
  color: var(--p-text-muted-color, #888);
  font-size: 0.85rem;
}
</style>
