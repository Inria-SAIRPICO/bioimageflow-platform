<script setup lang="ts">
import { computed, inject } from 'vue'
import { Handle, Position, useVueFlow } from '@vue-flow/core'
import { getTypeColor } from '@/utils/typeColors'

const props = withDefaults(defineProps<{
  nodeId: string
  fieldName: string
  fieldType: string
  connected: boolean
  sourceLabel?: string
  positional?: boolean
  positionalIndex?: number
  variant?: 'header' | 'body'
}>(), {
  variant: 'body',
})

const { getEdges } = useVueFlow()
const disconnectEdge = inject<((edgeId: string) => void) | undefined>(
  'bioimageflow:disconnectEdge',
  undefined,
)

const color = computed(() => getTypeColor(props.fieldType))

const label = computed(() => {
  if (props.positional && props.positionalIndex != null) {
    return String(props.positionalIndex + 1)
  }
  if (props.connected && props.sourceLabel) {
    return props.sourceLabel
  }
  return props.fieldName
})

/**
 * Grabbing a connected input pin detaches the edge and re-starts the
 * connection drag from the upstream source, so the edge follows the cursor.
 * Dropping on another input pin reconnects; dropping on empty canvas deletes.
 * Unconnected pins fall through to Vue Flow's default (start a new connection
 * from the target side).
 */
function onPointerDown(event: PointerEvent) {
  const target = event.target as HTMLElement | null
  if (!target?.closest('.vue-flow__handle')) return
  if (!props.connected) return

  const existing = getEdges.value.find(
    (e: any) => e.target === props.nodeId && e.targetHandle === props.fieldName,
  )
  if (!existing) return

  const sourceEl = document.querySelector<HTMLElement>(
    `.vue-flow__node[data-id="${existing.source}"] ` +
      `.vue-flow__handle[data-handleid="${existing.sourceHandle}"]`,
  )
  if (!sourceEl) return

  event.stopPropagation()

  disconnectEdge?.(existing.id)

  sourceEl.dispatchEvent(
    new PointerEvent('pointerdown', {
      bubbles: true,
      cancelable: true,
      clientX: event.clientX,
      clientY: event.clientY,
      pointerId: event.pointerId,
      button: event.button,
      buttons: event.buttons,
      pointerType: event.pointerType,
      isPrimary: event.isPrimary,
    }),
  )
}
</script>

<template>
  <div class="input-pin" :class="{ 'input-pin--any': fieldType === 'any', 'input-pin--header': variant === 'header' }" :title="fieldType === 'any' ? '? (runtime-typed)' : fieldType" @pointerdown.capture="onPointerDown">
    <Handle
      type="target"
      :position="Position.Left"
      :id="fieldName"
      class="pin-handle"
      :class="{ connected, 'pin-handle--header': variant === 'header' }"
      :style="variant === 'header' ? { backgroundColor: connected ? '#7A7A80' : 'transparent', borderColor: '#7A7A80' } : { backgroundColor: connected ? color : 'transparent', borderColor: color }"
    />
    <span class="pin-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.input-pin {
  display: flex;
  align-items: center;
  gap: 3px;
  position: relative;
  padding: 2px 0;
}

.pin-handle {
  width: 14px !important;
  height: 14px !important;
  border-radius: 50% !important;
  border: 2px solid !important;
  background: transparent !important;
  position: relative !important;
  transform: none !important;
}

.pin-handle--header {
  border-radius: 2px !important;
}

.input-pin--header .pin-label {
  font-size: 11px;
  font-weight: 600;
}

.pin-label {
  font-size: 12px;
  white-space: nowrap;
  margin-left: 0px;
}
</style>
