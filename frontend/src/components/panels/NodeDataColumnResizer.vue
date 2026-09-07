<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { clampColumnWidth, MIN_COLUMN_WIDTH, MAX_COLUMN_WIDTH } from '@/composables/useTableColumnWidths'

const props = defineProps<{ label: string; getWidth: () => number }>()
const width = computed(() => props.getWidth())
const emit = defineEmits<{
  resize: [width: number, commit: boolean]
  cancel: []
  autosize: []
}>()
const drag = ref<{ x: number; width: number; pointer: number } | null>(null)
function start(event: PointerEvent) {
  if (event.button !== 0) return
  drag.value = { x: event.clientX, width: width.value, pointer: event.pointerId }
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}
function move(event: PointerEvent, commit = false) {
  if (!drag.value || event.pointerId !== drag.value.pointer) return
  if (commit && event.clientX === drag.value.x) { cancel(); return }
  emit('resize', clampColumnWidth(drag.value.width + event.clientX - drag.value.x), commit)
  if (commit) drag.value = null
}
function cancel() { if (drag.value) { drag.value = null; emit('cancel') } }
onBeforeUnmount(cancel)
function keydown(event: KeyboardEvent) {
  if (event.key === 'Escape') { cancel(); return }
  if (event.key === 'Enter') { event.preventDefault(); emit('autosize'); return }
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()
  emit('resize', clampColumnWidth(width.value + (event.key === 'ArrowRight' ? 10 : -10)), true)
}
</script>

<template>
  <span class="node-data-column-resizer" :class="{ 'is-resizing': drag }"
    role="separator" tabindex="0" aria-orientation="vertical"
    :aria-label="`Resize ${label}`" :aria-valuenow="Math.round(width)"
    :aria-valuemin="MIN_COLUMN_WIDTH" :aria-valuemax="MAX_COLUMN_WIDTH"
    title="Drag to resize; double-click or press Enter to auto-size"
    @pointerdown.stop.prevent="start" @pointermove.stop="move($event)"
    @pointerup.stop="move($event, true)" @pointercancel="cancel" @lostpointercapture="cancel"
    @click.stop @dblclick.stop.prevent="emit('autosize')" @keydown.stop="keydown"
  />
</template>

<style scoped>
.node-data-column-resizer {
  position: absolute;
  inset-block: 0;
  inset-inline-end: 0;
  width: 10px;
  cursor: col-resize;
  touch-action: none;
  user-select: none;
  z-index: 2;
}
.node-data-column-resizer::after {
  content: '';
  position: absolute;
  inset-block: 6px;
  inset-inline-end: 1px;
  width: 1px;
  background: var(--p-content-border-color);
}
.node-data-column-resizer:hover::after,
.node-data-column-resizer:focus-visible::after,
.node-data-column-resizer.is-resizing::after {
  width: 2px;
  background: var(--p-primary-color);
}
.node-data-column-resizer:focus-visible { outline: 1px solid var(--p-primary-color); outline-offset: -2px; }
</style>
