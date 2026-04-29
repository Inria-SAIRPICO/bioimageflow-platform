<script setup lang="ts">
import { computed, toRef } from 'vue'
import { getBezierPath, Position } from '@vue-flow/core'
import { useEdgeError } from '@/composables/useEdgeError'
import type { GraphValidationError } from '@/api/types'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  id: string
  sourceX: number
  sourceY: number
  targetX: number
  targetY: number
  sourcePosition: Position
  targetPosition: Position
  data?: { errors?: GraphValidationError[] }
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

const { hasError, errorTitle } = useEdgeError(toRef(props, 'data'))
const strokeColor = computed(() =>
  hasError.value ? 'var(--p-red-500)' : '#7A7A80',
)
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
    :class="['vue-flow__edge-path', { 'edge-error': hasError }]"
    :d="path"
    :stroke="strokeColor"
    stroke-width="2.5"
    fill="none"
  >
    <title v-if="hasError">{{ errorTitle }}</title>
  </path>
</template>
