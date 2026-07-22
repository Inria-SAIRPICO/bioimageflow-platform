<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'

const props = defineProps<{
  page: number
  pageSize: number
  totalRows: number
  unfilteredTotalRows: number
}>()

const emit = defineEmits<{
  (event: 'page', page: number): void
  (event: 'page-size', pageSize: number): void
}>()

const pageSizes = [25, 50, 100, 250, 500]
const pageInputId = useId()
const totalPages = computed(() => Math.ceil(props.totalRows / props.pageSize))
const currentPage = computed(() => totalPages.value === 0 ? 0 : props.page + 1)
const firstRow = computed(() => props.totalRows === 0 ? 0 : props.page * props.pageSize + 1)
const lastRow = computed(() => Math.min((props.page + 1) * props.pageSize, props.totalRows))
const draftPage = ref<number | null>(currentPage.value)

watch(currentPage, value => {
  draftPage.value = value
})

function navigate(page: number): void {
  if (totalPages.value === 0) return
  emit('page', Math.min(Math.max(page, 0), totalPages.value - 1))
}

function updateDraftPage(value: string | number | undefined): void {
  const parsed = typeof value === 'number' ? value : Number(value)
  draftPage.value = Number.isFinite(parsed) ? parsed : null
}

function submitPage(): void {
  if (totalPages.value === 0) {
    draftPage.value = 0
    return
  }
  const requested = Math.trunc(draftPage.value ?? currentPage.value)
  const clamped = Math.min(Math.max(requested, 1), totalPages.value)
  draftPage.value = clamped
  if (clamped !== currentPage.value) emit('page', clamped - 1)
}
</script>

<template>
  <nav class="node-data-paginator" aria-label="Node Data pages" data-testid="node-data-paginator">
    <span class="node-data-paginator__range" aria-live="polite">
      {{ firstRow }}–{{ lastRow }} of {{ totalRows }}
      <template v-if="unfilteredTotalRows !== totalRows">
        ({{ unfilteredTotalRows }} unfiltered)
      </template>
    </span>
    <div class="node-data-paginator__navigation">
      <Button
        icon="pi pi-step-backward"
        text
        size="small"
        aria-label="First page"
        title="First page"
        :disabled="page <= 0 || totalPages === 0"
        @click="navigate(0)"
      />
      <Button
        icon="pi pi-angle-left"
        text
        size="small"
        aria-label="Previous page"
        title="Previous page"
        :disabled="page <= 0 || totalPages === 0"
        @click="navigate(page - 1)"
      />
      <label class="node-data-paginator__page">
        <span>Page</span>
        <InputNumber
          v-model="draftPage"
          :min="totalPages === 0 ? 0 : 1"
          :max="Math.max(totalPages, 1)"
          :disabled="totalPages === 0"
          :input-id="pageInputId"
          size="small"
          data-testid="node-data-page-input"
          @input="updateDraftPage($event.value)"
          @keydown.enter.prevent="submitPage"
          @blur="submitPage"
        />
        <span>of {{ totalPages }}</span>
      </label>
      <Button
        icon="pi pi-angle-right"
        text
        size="small"
        aria-label="Next page"
        title="Next page"
        :disabled="page >= totalPages - 1 || totalPages === 0"
        @click="navigate(page + 1)"
      />
      <Button
        icon="pi pi-step-forward"
        text
        size="small"
        aria-label="Last page"
        title="Last page"
        :disabled="page >= totalPages - 1 || totalPages === 0"
        @click="navigate(totalPages - 1)"
      />
    </div>
    <label class="node-data-paginator__size">
      <span>Rows</span>
      <Select
        :model-value="pageSize"
        :options="pageSizes"
        size="small"
        aria-label="Rows per page"
        @update:model-value="emit('page-size', Number($event))"
      />
    </label>
  </nav>
</template>

<style scoped>
.node-data-paginator {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.375rem 0.75rem;
  min-height: 2.75rem;
  padding: 0.25rem 0;
  border-top: 1px solid var(--bif-border-muted);
  background: var(--bif-surface);
}

.node-data-paginator__range {
  color: var(--p-text-muted-color);
  font-size: 0.8125rem;
  white-space: nowrap;
}

.node-data-paginator__navigation,
.node-data-paginator__page,
.node-data-paginator__size {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.node-data-paginator__page :deep(.p-inputnumber-input) {
  width: 4.5rem;
  text-align: center;
}

.node-data-paginator__size :deep(.p-select) {
  min-width: 5.25rem;
}
</style>
