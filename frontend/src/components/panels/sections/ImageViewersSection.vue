<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import type { Settings } from '@/stores/settings'
import { selectFolder } from '@/utils/nativeDialogs'

const FIJI_DOWNLOAD_URL = 'https://imagej.net/software/fiji/downloads'

const props = defineProps<{ modelValue: Settings }>()
const emit = defineEmits<{
  (e: 'update:field', payload: { field: keyof Settings; value: unknown }): void
}>()

const fijiPath = ref(props.modelValue.fiji_path ?? '')

watch(
  () => props.modelValue.fiji_path,
  (value) => {
    fijiPath.value = value ?? ''
  },
)

function commit() {
  const trimmed = fijiPath.value.trim()
  emit('update:field', {
    field: 'fiji_path',
    value: trimmed || null,
  })
}

async function browse() {
  const selected = await selectFolder('Choose the Fiji.app folder')
  if (!selected) return
  fijiPath.value = selected
  commit()
}

function clear() {
  fijiPath.value = ''
  commit()
}
</script>

<template>
  <div class="settings-section" data-testid="image-viewers-section">
    <p class="help-text">
      Fiji is installed separately. Download and unpack Fiji, then choose the Fiji.app folder.
      <a :href="FIJI_DOWNLOAD_URL" target="_blank" rel="noopener noreferrer">Download Fiji</a>
    </p>
    <label class="field-label" for="fiji-path-input">Fiji installation</label>
    <div class="path-row">
      <InputText
        id="fiji-path-input"
        v-model="fijiPath"
        placeholder="/Applications/Fiji.app"
        data-testid="fiji-path-input"
        @blur="commit"
        @keydown.enter="commit"
      />
      <Button
        label="Browse…"
        severity="secondary"
        data-testid="fiji-path-browse"
        @click="browse"
      />
      <Button
        label="Clear"
        severity="secondary"
        :disabled="!fijiPath"
        data-testid="fiji-path-clear"
        @click="clear"
      />
    </div>
  </div>
</template>

<style scoped>
.settings-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.field-label {
  font-weight: 600;
}

.help-text {
  margin: 0;
  color: var(--p-text-muted-color, #888);
  line-height: 1.45;
}

.path-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 0.5rem;
}

@media (max-width: 520px) {
  .path-row {
    grid-template-columns: 1fr 1fr;
  }

  .path-row :deep(input) {
    grid-column: 1 / -1;
    width: 100%;
  }
}
</style>
