<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { getTypeColor } from '@/utils/typeColors'

const props = defineProps<{
  fieldName: string
  fieldType: string
  connected: boolean
  sourceLabel?: string
  positional?: boolean
  positionalIndex?: number
}>()

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
</script>

<template>
  <div class="input-pin" :title="fieldType">
    <Handle
      type="target"
      :position="Position.Left"
      :id="fieldName"
      class="pin-handle"
      :class="{ connected }"
      :style="{ backgroundColor: connected ? color : 'transparent', borderColor: color }"
    />
    <span class="pin-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.input-pin {
  display: flex;
  align-items: center;
  gap: 6px;
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
  left: -7px !important;
  transform: none !important;
}

.pin-label {
  font-size: 12px;
  white-space: nowrap;
  margin-left: 0px;
}
</style>
