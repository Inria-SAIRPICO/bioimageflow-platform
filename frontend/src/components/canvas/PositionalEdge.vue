<script setup lang="ts">
import { computed } from 'vue'
import { getBezierPath, Position } from '@vue-flow/core'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  id: string
  sourceX: number
  sourceY: number
  targetX: number
  targetY: number
  sourcePosition: Position
  targetPosition: Position
}>()

const path = computed(() => {
  const [d] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
  })
  return d
})
</script>

<template>
  <path
    :d="path"
    stroke="transparent"
    stroke-width="14"
    fill="none"
    class="vue-flow__edge-interaction"
  />
  <path
    :id="id"
    class="vue-flow__edge-path"
    :d="path"
    stroke="#7A7A80"
    stroke-width="2.5"
    fill="none"
  />
</template>
