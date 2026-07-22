<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Popover from 'primevue/popover'
import Select from 'primevue/select'
import type {
  DataTableFilter,
  DataTableFilterOperator,
  DataTablePageState,
} from '@/stores/dataTable'

const props = defineProps<{
  column: string
  label: string
  type: string
  pageState: DataTablePageState
}>()

const emit = defineEmits<{
  (event: 'sort', column: string | null, order: 'asc' | 'desc'): void
  (event: 'filters', filters: DataTableFilter[]): void
}>()

const popover = ref<InstanceType<typeof Popover> | null>(null)
const operator = ref<DataTableFilterOperator>('contains')
const value = ref<string | number | boolean | null>('')
const secondValue = ref<number | null>(null)
const activeFilter = computed(() => props.pageState.filters.find(item => item.column === props.column))
const numeric = computed(() => /^(u?int|float|double|number|decimal)/i.test(props.type))
const boolean = computed(() => /^(bool|boolean)$/i.test(props.type))
const valueFree = computed(() => operator.value === 'is_empty' || operator.value === 'is_not_empty')
const operatorOptions = computed<{ label: string; value: DataTableFilterOperator }[]>(() => {
  if (boolean.value) {
    return [
      { label: 'Equals', value: 'equals' },
      { label: 'Is empty', value: 'is_empty' },
      { label: 'Is not empty', value: 'is_not_empty' },
    ]
  }
  if (numeric.value) {
    return [
      { label: 'Equals', value: 'equals' },
      { label: 'Does not equal', value: 'not_equals' },
      { label: 'Greater than', value: 'gt' },
      { label: 'Greater than or equal', value: 'gte' },
      { label: 'Less than', value: 'lt' },
      { label: 'Less than or equal', value: 'lte' },
      { label: 'Between', value: 'between' },
      { label: 'Is empty', value: 'is_empty' },
      { label: 'Is not empty', value: 'is_not_empty' },
    ]
  }
  return [
    { label: 'Contains', value: 'contains' },
    { label: 'Starts with', value: 'starts_with' },
    { label: 'Equals', value: 'equals' },
    { label: 'Does not equal', value: 'not_equals' },
    { label: 'Is empty', value: 'is_empty' },
    { label: 'Is not empty', value: 'is_not_empty' },
  ]
})
const sortIcon = computed(() => {
  if (props.pageState.sortBy !== props.column) return 'pi pi-sort-alt'
  return props.pageState.sortOrder === 'asc'
    ? 'pi pi-sort-amount-up-alt'
    : 'pi pi-sort-amount-down'
})

watch([numeric, boolean], () => resetDraft(), { immediate: true })

function resetDraft(): void {
  const existing = activeFilter.value
  operator.value = existing?.operator ?? (boolean.value ? 'equals' : numeric.value ? 'equals' : 'contains')
  value.value = existing?.value ?? (boolean.value ? true : numeric.value ? 0 : '')
  secondValue.value = typeof existing?.second_value === 'number' ? existing.second_value : null
}

function toggleFilter(event: Event): void {
  resetDraft()
  popover.value?.toggle(event)
}

function toggleSort(): void {
  if (props.pageState.sortBy !== props.column) {
    emit('sort', props.column, 'asc')
  } else if (props.pageState.sortOrder === 'asc') {
    emit('sort', props.column, 'desc')
  } else {
    emit('sort', null, 'asc')
  }
}

function applyFilter(): void {
  const next = props.pageState.filters.filter(item => item.column !== props.column)
  if (!valueFree.value && (value.value === null || value.value === '')) {
    emit('filters', next)
    popover.value?.hide()
    return
  }
  const item: DataTableFilter = { column: props.column, operator: operator.value }
  if (!valueFree.value) item.value = value.value
  if (operator.value === 'between') item.second_value = secondValue.value
  emit('filters', [...next, item])
  popover.value?.hide()
}

function clearFilter(): void {
  emit('filters', props.pageState.filters.filter(item => item.column !== props.column))
  popover.value?.hide()
}
</script>

<template>
  <div class="node-data-column-header">
    <button
      class="node-data-column-header__sort"
      type="button"
      :aria-label="`Sort ${label}`"
      :aria-pressed="pageState.sortBy === column"
      @click="toggleSort"
    >
      <span class="node-data-column-header__labels">
        <span>{{ label }}</span>
        <span class="node-data-column-header__type">{{ type }}</span>
      </span>
      <i :class="sortIcon" aria-hidden="true" />
    </button>
    <Button
      icon="pi pi-filter"
      text
      rounded
      size="small"
      :class="{ 'node-data-column-header__filter--active': activeFilter }"
      :aria-label="`Filter ${label}`"
      :title="`Filter ${label}`"
      :aria-pressed="Boolean(activeFilter)"
      @click.stop="toggleFilter"
    />
    <Popover ref="popover">
      <form class="node-data-filter" @submit.prevent="applyFilter">
        <strong>Filter {{ label }}</strong>
        <Select
          v-model="operator"
          :options="operatorOptions"
          option-label="label"
          option-value="value"
          aria-label="Filter operator"
        />
        <Select
          v-if="boolean && !valueFree"
          v-model="value"
          :options="[{ label: 'True', value: true }, { label: 'False', value: false }]"
          option-label="label"
          option-value="value"
          aria-label="Filter value"
        />
        <InputNumber
          v-else-if="numeric && !valueFree"
          :model-value="typeof value === 'number' ? value : null"
          aria-label="Filter value"
          @update:model-value="value = $event ?? ''"
        />
        <InputText
          v-else-if="!valueFree"
          :model-value="typeof value === 'string' ? value : ''"
          aria-label="Filter value"
          autofocus
          @update:model-value="value = $event ?? ''"
        />
        <InputNumber
          v-if="operator === 'between'"
          v-model="secondValue"
          aria-label="Second filter value"
        />
        <div class="node-data-filter__actions">
          <Button
            v-if="activeFilter"
            label="Clear"
            severity="secondary"
            text
            size="small"
            type="button"
            @click="clearFilter"
          />
          <Button
            label="Apply"
            size="small"
            type="submit"
            :disabled="operator === 'between' && secondValue === null"
          />
        </div>
      </form>
    </Popover>
  </div>
</template>

<style scoped>
.node-data-column-header,
.node-data-column-header__sort,
.node-data-column-header__labels {
  display: flex;
  align-items: center;
}

.node-data-column-header {
  min-width: 0;
  justify-content: space-between;
  gap: 0.25rem;
}

.node-data-column-header__sort {
  min-width: 0;
  gap: 0.375rem;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
  font: inherit;
}

.node-data-column-header__labels {
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.15;
}

.node-data-column-header__type {
  color: var(--p-text-muted-color);
  font-size: 0.7rem;
  font-weight: 400;
}

.node-data-column-header__filter--active {
  color: var(--p-primary-color);
  background: color-mix(in srgb, var(--p-primary-color) 14%, transparent);
}

.node-data-filter {
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  width: 16rem;
}

.node-data-filter__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
