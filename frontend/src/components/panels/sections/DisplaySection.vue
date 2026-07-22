<script setup lang="ts">
import Select from 'primevue/select'
import type { Settings } from '@/stores/settings'

defineProps<{ modelValue: Settings }>()
const emit = defineEmits<{
  (event: 'update:field', payload: { field: keyof Settings; value: unknown }): void
}>()

const pageSizes = [25, 50, 100, 250, 500]
</script>

<template>
  <div class="settings-section">
    <div class="field">
      <label class="field-label" for="node-data-page-size">Node Data rows per page</label>
      <Select
        input-id="node-data-page-size"
        :model-value="modelValue.node_data_page_size"
        :options="pageSizes"
        data-testid="node-data-page-size-setting"
        @update:model-value="emit('update:field', { field: 'node_data_page_size', value: Number($event) })"
      />
      <small>
        Sets the default for newly inspected tables. Individual tables can temporarily use another page size.
      </small>
    </div>
  </div>
</template>

<style scoped>
.settings-section,
.field {
  display: flex;
  flex-direction: column;
}

.settings-section {
  gap: 1rem;
}

.field {
  gap: 0.4rem;
}

.field-label {
  font-weight: 600;
}

small {
  color: var(--p-text-muted-color, #666);
}
</style>
