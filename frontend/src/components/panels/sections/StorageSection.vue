<script setup lang="ts">
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import type { SettingsResponse } from '@/api/types'
import { isDesktop, revealPath, selectFolder } from '@/utils/nativeDialogs'

const props = defineProps<{ modelValue: SettingsResponse }>()
const emit = defineEmits<{
  (e: 'update:field', payload: { field: keyof SettingsResponse; value: unknown }): void
}>()

let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}
let confirm: ReturnType<typeof useConfirm> | null = null
try {
  confirm = useConfirm()
} catch {
  confirm = null
}

async function reveal() {
  try {
    await revealPath(props.modelValue.resolved_output_data_folder)
  } catch (e) {
    toast?.add({
      severity: 'info',
      summary: 'Folder unavailable',
      detail:
        'The folder does not exist yet. It will be created when the next workflow runs.',
      life: 5000,
    })
  }
}

async function changeFolder() {
  const picked = await selectFolder('Select output data folder')
  if (!picked) return
  const apply = () =>
    emit('update:field', { field: 'output_data_folder', value: picked })
  if (confirm) {
    confirm.require({
      message:
        'Change output data folder? Existing data will not be moved to the new location.',
      header: 'Confirm change',
      icon: 'pi pi-exclamation-triangle',
      accept: apply,
    })
  } else {
    apply()
  }
}
</script>

<template>
  <div class="settings-section">
    <div class="field">
      <label class="field-label" for="output-data-folder-input">Output data folder</label>
      <div class="field-row">
        <InputText
          id="output-data-folder-input"
          :model-value="modelValue.resolved_output_data_folder"
          readonly
          data-testid="output-data-folder-input"
          class="grow"
        />
        <Button
          label="Reveal"
          severity="secondary"
          data-testid="output-reveal-button"
          @click="reveal"
        />
        <Button
          v-if="isDesktop()"
          label="Change..."
          severity="secondary"
          data-testid="output-change-button"
          @click="changeFolder"
        />
      </div>
      <p class="help-text">
        Workflow outputs are written here. Stored value:
        <code>{{ modelValue.output_data_folder }}</code>
      </p>
    </div>

    <div class="field">
      <label class="field-label" for="tool-store-path-input">Tool store path</label>
      <InputText
        id="tool-store-path-input"
        :model-value="modelValue.resolved_tool_store_path"
        readonly
        data-testid="tool-store-path-input"
      />
      <p class="help-text">
        Default: <code>~/.bioimageflow/tool_packages/</code>. Override with the
        <code>BIOIMAGEFLOW_TOOL_STORE</code> environment variable.
      </p>
    </div>
  </div>
</template>

<style scoped>
.settings-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
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
