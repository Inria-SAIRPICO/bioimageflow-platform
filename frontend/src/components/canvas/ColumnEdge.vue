<script setup lang="ts">
import { computed, toRef } from 'vue'
import { getBezierPath, Position } from '@vue-flow/core'
import { getTypeColor } from '@/utils/typeColors'
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
  targetNode?: {
    data?: {
      nodeType?: 'tool' | 'workflow'
      tool?: { row_consumption?: 'mapped' | 'collective' | null } | null
    }
  }
  data?: { type?: string; errors?: GraphValidationError[] }
}>()

function edgePath(offset: number, converge: boolean): string {
  const horizontal = props.targetPosition === Position.Left
    || props.targetPosition === Position.Right
  const sourceX = props.sourceX + (horizontal ? 0 : offset)
  const sourceY = props.sourceY + (horizontal ? offset : 0)
  const targetOffset = converge ? 0 : offset
  const targetX = props.targetX + (horizontal ? 0 : targetOffset)
  const targetY = props.targetY + (horizontal ? targetOffset : 0)
  const [d] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition: props.sourcePosition,
    targetX,
    targetY,
    targetPosition: props.targetPosition,
  })
  return d
}

const rowConsumption = computed(() => {
  if (props.targetNode?.data?.nodeType !== 'tool') return null
  return props.targetNode.data.tool?.row_consumption ?? null
})

const paths = computed(() => {
  if (rowConsumption.value === null) {
    return [{ id: props.id, path: edgePath(0, false) }]
  }
  const converge = rowConsumption.value === 'collective'
  return [-4, 0, 4].map((offset, index) => ({
    id: index === 1 ? props.id : `${props.id}-strand-${index}`,
    path: edgePath(offset, converge),
  }))
})

const interactionPath = computed(() => edgePath(0, false))
const consumptionTitle = computed(() => {
  if (rowConsumption.value === 'mapped') return 'Rows are processed independently.'
  if (rowConsumption.value === 'collective') return 'Rows are processed together.'
  return ''
})

const { hasError, errorTitle } = useEdgeError(toRef(props, 'data'))

const strokeColor = computed(() =>
  hasError.value ? 'var(--p-red-500)' : getTypeColor(props.data?.type ?? ''),
)
</script>

<template>
  <path
    :d="interactionPath"
    stroke="transparent"
    stroke-width="12"
    fill="none"
    class="vue-flow__edge-interaction"
  />
  <path
    v-for="strand in paths"
    :id="strand.id"
    :key="strand.id"
    :class="['vue-flow__edge-path', { 'edge-error': hasError }]"
    :d="strand.path"
    :stroke="strokeColor"
    stroke-width="2"
    fill="none"
  >
    <title v-if="hasError || consumptionTitle">{{ hasError ? errorTitle : consumptionTitle }}</title>
  </path>
</template>
