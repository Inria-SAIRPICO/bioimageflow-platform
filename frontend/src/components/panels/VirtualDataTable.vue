<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch, type CSSProperties } from 'vue'

interface IndexedTableRow { index: number; row: Record<string, any> }
interface TableColumn { id: string; label: string; type: string; viewer_status?: string; viewer?: { napari?: unknown } | null; [key: string]: any }
const props = defineProps<{
  columns: TableColumn[]
  entries: IndexedTableRow[]
  totalRows: number
  rowHeight: (row: Record<string, any>) => number
  estimatedRowHeight?: number
  columnStyle: (column: TableColumn) => CSSProperties
  tableStyle: { width: string; tableLayout?: string }
  resetKey: string
  loading?: boolean
}>()
const emit = defineEmits<{ range: [start: number, end: number] }>()
const viewport = ref<HTMLElement | null>(null)
const header = ref<HTMLElement | null>(null)
const scrollTop = ref(0)
const height = ref(400)
const visible = ref(false)
const measuredHeights = reactive(new Map<number, number>())
const rowElements = new Map<number, HTMLElement>()
const rowsByIndex = computed(() => new Map(props.entries.map(entry => [entry.index, entry.row])))
const layout = computed(() => {
  const estimate = props.estimatedRowHeight ?? 40
  const corrections = props.entries.map(entry => ({ index: entry.index, delta: (measuredHeights.get(entry.index) ?? props.rowHeight(entry.row)) - estimate }))
    .filter(item => item.delta !== 0).sort((a, b) => a.index - b.index)
  return { estimate, corrections, total: props.totalRows }
})
type Layout = typeof layout.value
function offset(selected: Layout, index: number): number {
  let result = index * selected.estimate
  for (const correction of selected.corrections) {
    if (correction.index >= index) break
    result += correction.delta
  }
  return result
}
function indexAt(selected: Layout, pixels: number): number {
  let low = 0
  let high = selected.total
  while (low < high) {
    const middle = Math.ceil((low + high) / 2)
    if (offset(selected, middle) <= pixels) low = middle
    else high = middle - 1
  }
  return Math.min(low, Math.max(0, selected.total - 1))
}
const start = computed(() => Math.max(0, indexAt(layout.value, scrollTop.value) - 2))
const end = computed(() => Math.min(props.totalRows, indexAt(layout.value, scrollTop.value + height.value) + 3))
const windowRows = computed(() => {
  if (!visible.value) return []
  return Array.from({ length: Math.max(0, end.value - start.value) }, (_, n) => {
    const index = start.value + n
    return { index, row: rowsByIndex.value.get(index) }
  })
})
const topSpace = computed(() => visible.value ? offset(layout.value, start.value) : 0)
const bottomSpace = computed(() => Math.max(0, offset(layout.value, props.totalRows)
  - (visible.value ? offset(layout.value, end.value) : 0)))
let resizeObserver: ResizeObserver | null = null
let intersectionObserver: IntersectionObserver | null = null
let rowObserver: ResizeObserver | null = null
function observeRow(element: unknown, index: number): void {
  const previous = rowElements.get(index)
  if (previous) rowObserver?.unobserve(previous)
  if (element instanceof HTMLElement) {
    rowElements.set(index, element)
    rowObserver?.observe(element)
  } else rowElements.delete(index)
}
watch(() => props.entries, entries => {
  const resident = new Set(entries.map(entry => entry.index))
  for (const index of measuredHeights.keys()) if (!resident.has(index)) measuredHeights.delete(index)
})

function scrolled(): void {
  const element = viewport.value
  if (!element) return
  scrollTop.value = element.scrollTop
  if (header.value) header.value.scrollLeft = element.scrollLeft
  const focused = document.activeElement as HTMLElement | null
  const focusedRow = focused?.closest<HTMLElement>('tr[data-virtual-index]')
  const index = Number(focusedRow?.dataset.virtualIndex)
  if (focusedRow && element.contains(focusedRow) && (index < start.value || index >= end.value)) element.focus()
}
function keydown(event: KeyboardEvent): void {
  if (event.target !== viewport.value || !viewport.value) return
  const movement: Record<string, number> = { PageDown: height.value, PageUp: -height.value, ArrowDown: 40, ArrowUp: -40 }
  if (event.key in movement) viewport.value.scrollTop += movement[event.key]!
  else if (event.key === 'Home') viewport.value.scrollTop = 0
  else if (event.key === 'End') viewport.value.scrollTop = offset(layout.value, props.totalRows)
  else return
  event.preventDefault()
  scrolled()
}
watch(layout, (next, previous) => {
  if (!viewport.value || !previous || previous.total === 0) return
  const anchor = indexAt(previous, scrollTop.value)
  const within = scrollTop.value - offset(previous, anchor)
  const adjusted = offset(next, Math.min(anchor, Math.max(0, next.total - 1))) + within
  if (adjusted !== scrollTop.value) {
    viewport.value.scrollTop = adjusted
    scrollTop.value = adjusted
  }
})
watch(() => props.resetKey, async () => {
  measuredHeights.clear()
  scrollTop.value = 0
  await nextTick()
  if (viewport.value) viewport.value.scrollTop = 0
})
watch([start, end, visible, () => props.resetKey], () => {
  if (visible.value) emit('range', start.value, end.value)
}, { immediate: true })
onMounted(() => {
  if (!viewport.value) return
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => { height.value = Math.max(40, viewport.value?.clientHeight ?? 400) })
    resizeObserver.observe(viewport.value)
    rowObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const element = entry.target as HTMLElement
        const index = Number(element.dataset.virtualIndex)
        if (rowElements.get(index) !== element) continue
        const actualHeight = element.getBoundingClientRect().height
        if (actualHeight > 0 && Math.abs((measuredHeights.get(index) ?? 0) - actualHeight) > .5) measuredHeights.set(index, actualHeight)
      }
    })
    for (const element of rowElements.values()) rowObserver.observe(element)
  }
  if (typeof IntersectionObserver === 'undefined') visible.value = true
  else {
    intersectionObserver = new IntersectionObserver(entries => { visible.value = entries.some(entry => entry.isIntersecting) })
    intersectionObserver.observe(viewport.value)
  }
})
onBeforeUnmount(() => { resizeObserver?.disconnect(); rowObserver?.disconnect(); intersectionObserver?.disconnect() })
</script>

<template>
  <div class="p-datatable virtual-data-table node-data-sized-grid" role="grid" :aria-rowcount="totalRows + 1" :aria-colcount="columns.length" :aria-busy="loading || undefined">
    <div ref="header" class="virtual-data-table__header">
      <table class="p-datatable-table" role="presentation" :style="{ width: tableStyle.width, tableLayout: 'fixed' }">
        <thead class="p-datatable-thead"><tr role="row" aria-rowindex="1">
          <th v-for="column in columns" :key="column.id" class="p-datatable-header-cell" :style="columnStyle(column)" scope="col" role="columnheader">
            <div class="p-datatable-column-header-content"><slot name="header" :column="column" /></div>
          </th>
        </tr></thead>
      </table>
    </div>
    <div ref="viewport" class="p-datatable-table-container virtual-data-table__viewport"
      tabindex="0" role="region" aria-label="Node Data rows" data-testid="node-data-viewport" @scroll="scrolled" @keydown="keydown">
      <table class="p-datatable-table" role="presentation" :style="{ width: tableStyle.width, tableLayout: 'fixed' }">
        <tbody class="p-datatable-tbody" role="rowgroup">
          <tr v-if="topSpace" aria-hidden="true" class="virtual-data-table__spacer"><td :colspan="columns.length" :style="{ height: `${topSpace}px` }" /></tr>
          <tr v-for="entry in windowRows" :ref="element => observeRow(element, entry.index)" :key="`${resetKey}:${entry.index}`" :data-virtual-index="entry.index" :aria-rowindex="entry.index + 2" role="row"
            :style="{ height: `${entry.row ? rowHeight(entry.row) : (estimatedRowHeight ?? 40)}px` }">
            <td v-for="(column, columnIndex) in columns" :key="column.id" :style="columnStyle(column)" class="virtual-data-table__cell" role="gridcell" :aria-colindex="columnIndex + 1">
              <slot v-if="entry.row" name="body" :row="entry.row" :column="column" />
              <span v-else class="virtual-data-table__placeholder" aria-label="Loading row">…</span>
            </td>
          </tr>
          <tr v-if="bottomSpace" aria-hidden="true" class="virtual-data-table__spacer"><td :colspan="columns.length" :style="{ height: `${bottomSpace}px` }" /></tr>
        </tbody>
      </table>
      <div v-if="totalRows === 0" class="virtual-data-table__empty">No rows.</div>
    </div>
  </div>
</template>

<style scoped>
.virtual-data-table { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; min-width: 0; }
.virtual-data-table__viewport { flex: 1; min-height: 48px; overflow: auto; position: relative; overflow-anchor: none; }
.p-datatable-table { border-collapse: separate; border-spacing: 0; }
.virtual-data-table__header { flex: 0 0 auto; overflow: hidden; background: var(--bif-surface-card, var(--p-content-background)); }
.p-datatable-header-cell { height: 36px; border-bottom: 1px solid var(--bif-border-muted); padding: .25rem .5rem; text-align: left; }
.virtual-data-table__cell { box-sizing: border-box; padding: 6px 8px; border-bottom: 1px solid var(--bif-border-muted); vertical-align: middle; }
.virtual-data-table__spacer > td { padding: 0; border: 0; }
.virtual-data-table__placeholder { color: var(--p-text-muted-color); }
.virtual-data-table__empty { padding: 1rem; color: var(--p-text-muted-color); }
</style>
