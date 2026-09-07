import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, watchEffect, type Ref } from 'vue'

export interface SizingColumn { id: string; label: string; type: string }
export const MIN_COLUMN_WIDTH = 120
export const MAX_COLUMN_WIDTH = 1200
const AUTO_MAX = 480

export function clampColumnWidth(width: number): number {
  return Math.round(Math.max(MIN_COLUMN_WIDTH, Math.min(MAX_COLUMN_WIDTH, width)))
}

export function automaticColumnWidth(column: SizingColumn, values: unknown[], measure: (text: string) => number): number {
  const header = Math.max(measure(column.label), measure(column.type)) + 88
  const rich = /^(Path|ImageFile|ImageShared|MaskPath)$/.test(column.type)
  const content = rich ? 320 : Math.max(0, ...values.slice(0, 50).map(value => measure(String(value ?? '').slice(0, 1000)) + 24))
  return Math.min(AUTO_MAX, Math.max(MIN_COLUMN_WIDTH, Math.ceil(header), Math.ceil(content)))
}

export function readColumnWidths(raw: string | null): Record<string, number> {
  try {
    const parsed: unknown = JSON.parse(raw ?? '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return Object.fromEntries(Object.entries(parsed).filter(([, width]) => (
      typeof width === 'number' && Number.isFinite(width) && width >= MIN_COLUMN_WIDTH && width <= MAX_COLUMN_WIDTH
    )))
  } catch { return {} }
}

/** Own widths explicitly: PrimeVue's stateful table saves hidden DOM measurements on updates. */
export function useTableColumnWidths(
  scope: Ref<string>, columns: Ref<SizingColumn[]>, rows: Ref<Record<string, unknown>[]>,
) {
  const root = ref<HTMLElement | null>(null)
  const automatic = ref<Record<string, number>>({})
  const manual = ref<Record<string, number>>({})
  const preview = ref<Record<string, number>>({})
  const storageKey = computed(() => `bif-node-data-widths-v2:${scope.value}`)
  const identity = (column: SizingColumn) => JSON.stringify([column.id, column.type])
  let observer: ResizeObserver | undefined
  let frame = 0
  let disposed = false
  let fontsReady = false

  function measureColumn(column: SizingColumn): number {
    const element = root.value!
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d')
    const style = getComputedStyle(element.querySelector('.node-data-column-header__sort') ?? element)
    if (context) context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
    return automaticColumnWidth(column, rows.value.map(row => row[column.id]), text => context?.measureText(text).width ?? text.length * 8)
  }

  function isVisible(): boolean {
    const rect = root.value?.getBoundingClientRect()
    return fontsReady && !!rect && rect.width > 0 && rect.height > 0
  }

  function scheduleMeasure(): void {
    if (disposed) return
    cancelAnimationFrame(frame)
    frame = requestAnimationFrame(() => {
      if (!isVisible()) return
      const next = { ...automatic.value }
      for (const column of columns.value) {
        const key = identity(column)
        if (next[key] === undefined) next[key] = measureColumn(column)
      }
      automatic.value = next
    })
  }

  watch(storageKey, () => {
    try { manual.value = readColumnWidths(localStorage.getItem(storageKey.value)) } catch { manual.value = {} }
    automatic.value = {}
    preview.value = {}
    void nextTick(scheduleMeasure)
  }, { immediate: true })
  watch(() => JSON.stringify(columns.value), () => {
    automatic.value = {}
    preview.value = {}
    void nextTick(scheduleMeasure)
  })
  // Subsequent pages and thumbnail loads do not invalidate existing automatic widths.
  watch(rows, () => { void nextTick(scheduleMeasure) })
  watch(root, element => {
    observer?.disconnect()
    if (element) observer?.observe(element)
    scheduleMeasure()
  }, { flush: 'post' })

  onMounted(() => {
    observer = new ResizeObserver(scheduleMeasure)
    if (root.value) observer.observe(root.value)
    void (document.fonts?.ready ?? Promise.resolve()).then(() => {
      if (disposed) return
      fontsReady = true
      scheduleMeasure()
    })
  })
  onBeforeUnmount(() => { disposed = true; observer?.disconnect(); cancelAnimationFrame(frame) })

  function width(column: SizingColumn): number {
    const key = identity(column)
    return preview.value[key] ?? manual.value[key] ?? automatic.value[key] ?? MIN_COLUMN_WIDTH
  }
  function persist(): void {
    try {
      if (Object.keys(manual.value).length) localStorage.setItem(storageKey.value, JSON.stringify(manual.value))
      else localStorage.removeItem(storageKey.value)
    } catch { /* Storage can be unavailable; in-session resizing still works. */ }
  }
  function resize(column: SizingColumn, value: number, commit = false): void {
    if (!Number.isFinite(value)) return
    const key = identity(column)
    preview.value = { ...preview.value, [key]: clampColumnWidth(value) }
    if (commit) {
      manual.value = { ...manual.value, [key]: clampColumnWidth(value) }
      persist()
      preview.value = {}
    }
  }
  function autoSize(column?: SizingColumn): void {
    preview.value = {}
    if (column) {
      const key = identity(column)
      delete manual.value[key]
      delete automatic.value[key]
    } else {
      manual.value = {}
      automatic.value = {}
    }
    persist()
    scheduleMeasure()
  }
  // Changing Column props recreates PrimeVue's header slot components mid-drag.
  // CSS variables update geometry without remounting headers or losing focus/capture.
  watchEffect(() => {
    const element = root.value
    if (!element) return
    let total = 0
    columns.value.forEach((column, index) => {
      const value = width(column)
      total += value
      element.style.setProperty(`--bif-column-${index}`, `${value}px`)
    })
    element.style.setProperty('--bif-table-width', `${total}px`)
  })
  const tableStyle = { width: 'var(--bif-table-width)', tableLayout: 'fixed' }
  const columnStyle = (column: SizingColumn) => ({ width: `var(--bif-column-${columns.value.findIndex(item => item.id === column.id)}, 120px)`, minWidth: `${MIN_COLUMN_WIDTH}px` })
  return { root, width, tableStyle, columnStyle, resize, autoSize, cancelResize: () => { preview.value = {} } }
}
