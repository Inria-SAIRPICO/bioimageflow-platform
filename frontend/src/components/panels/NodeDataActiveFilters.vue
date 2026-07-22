<script setup lang="ts">
import Button from 'primevue/button'
import Chip from 'primevue/chip'
import type { DataTableFilter } from '@/stores/dataTable'

const props = defineProps<{
  filters: DataTableFilter[]
  labels: Record<string, string>
}>()

const emit = defineEmits<{
  (event: 'change', filters: DataTableFilter[]): void
}>()

function description(filter: DataTableFilter): string {
  const operator = filter.operator.replace(/_/g, ' ')
  const first = filter.value === undefined || filter.value === null ? '' : ` ${String(filter.value)}`
  const second = filter.second_value === undefined || filter.second_value === null
    ? ''
    : ` and ${String(filter.second_value)}`
  return `${props.labels[filter.column] ?? filter.column}: ${operator}${first}${second}`
}
</script>

<template>
  <div v-if="filters.length" class="node-data-active-filters" data-testid="node-data-active-filters">
    <span class="node-data-active-filters__label">Filters</span>
    <Chip
      v-for="filter in filters"
      :key="filter.column"
      :label="description(filter)"
      removable
      @remove="emit('change', filters.filter(item => item.column !== filter.column))"
    />
    <Button
      label="Clear filters"
      text
      size="small"
      severity="secondary"
      @click="emit('change', [])"
    />
  </div>
</template>

<style scoped>
.node-data-active-filters {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.375rem;
  padding: 0.25rem 0;
}

.node-data-active-filters__label {
  color: var(--p-text-muted-color);
  font-size: 0.8125rem;
}
</style>
