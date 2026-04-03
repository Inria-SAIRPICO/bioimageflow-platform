<script setup lang="ts">
import { computed } from 'vue'
import { getBezierPath, Position } from '@vue-flow/core'

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
    :id="id"
    class="vue-flow__edge-path"
    :d="path"
    stroke="#8E8E93"
    stroke-width="2"
    stroke-dasharray="5 3"
    fill="none"
  />
</template>
