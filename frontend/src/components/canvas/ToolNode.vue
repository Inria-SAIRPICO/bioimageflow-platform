<script setup lang="ts">
import { computed, inject } from 'vue'
import type { ToolMetadata, NodeOutputSchemaResponse } from '@/api/types'
import InputPin from './InputPin.vue'
import OutputPin from './OutputPin.vue'

export interface NodeData {
  name: string
  toolName: string
  tool: ToolMetadata
  status: string
  parameters: Record<string, unknown>
  collapsed: boolean
  enabled: boolean
  connectedInputs: Record<string, string>
  pinnedInputs: Record<string, boolean>
  output_templates: Record<string, string>
  provisional?: boolean
}

const props = defineProps<{
  id: string
  data: NodeData
}>()

const emit = defineEmits<{
  'context-menu': [event: MouseEvent]
  'toggle-collapse': [id: string]
}>()

/**
 * Injected by CanvasView — the reactive resolved-outputs map keyed by node id.
 * Falls back to an empty object if not provided (e.g. in unit tests).
 */
const resolvedOutputsByNodeId = inject<Record<string, NodeOutputSchemaResponse>>(
  'bioimageflow:resolvedOutputs',
  {},
)

const connectableInputs = computed(() => {
  return Object.entries(props.data.tool.inputs).filter(
    ([name, field]) => field.connectable !== 'never' && (props.data.pinnedInputs[name] !== false),
  )
})

const showsPositionalPins = computed(() => {
  return props.data.tool.tool_type === 'DataFrameTool'
      && props.data.tool.accepts_upstream === true
})

const positionalInputCount = computed(() => {
  // For DataFrameTools that accept upstream: number of connected positional inputs + 1 spare
  if (!showsPositionalPins.value) return 0
  const connected = Object.keys(props.data.connectedInputs).filter((k) =>
    k.startsWith('__positional_'),
  ).length
  return connected + 1
})

/**
 * Output pin entries. For tools with `dynamic_outputs === true`, the
 * resolved schema from the store replaces the static tool.outputs.
 *
 * Shape: `[name, { type }, placeholder?]`
 */
const outputs = computed<Array<[string, { type: string }, boolean]>>(() => {
  const tool = props.data.tool

  if (tool.dynamic_outputs !== true) {
    // Static outputs — render tool.outputs directly (no fallback).
    const toolOutputs = tool.outputs as Record<string, { type: string }>
    return Object.entries(toolOutputs).map(([name, field]) => [name, field, false])
  }

  // Dynamic outputs — check the resolved-outputs store.
  const entry = resolvedOutputsByNodeId[props.id]

  if (!entry || entry.resolved !== true) {
    // Unresolved or not yet fetched — render a single placeholder pin.
    return [['...', { type: 'DataFrame' }, true]]
  }

  const columns = entry.columns as Record<string, { type?: string }>

  // Passthrough marker: `{_passthrough: true, ...extra}`
  const isPassthrough = '_passthrough' in columns && (columns as any)._passthrough === true

  if (isPassthrough) {
    const concreteEntries: Array<[string, { type: string }, boolean]> = []
    for (const [key, spec] of Object.entries(columns)) {
      if (key === '_passthrough') continue
      concreteEntries.push([key, { type: (spec as any)?.type ?? 'any' }, false])
    }
    // Add a single placeholder for inherited columns.
    concreteEntries.push(['(+ inherited columns)', { type: 'DataFrame' }, true])
    return concreteEntries
  }

  // Normal resolved: one pin per column.
  return Object.entries(columns).map(([name, spec]) => [
    name,
    { type: (spec as any)?.type ?? 'any' },
    false,
  ])
})

const statusClass = computed(() => {
  return `status-${props.data.status.replace(/_/g, '-')}`
})

const hasGpu = computed(() => {
  const env = props.data.tool.environment
  if (!env) return false
  const resources = env.resources as Record<string, number> | undefined
  return resources != null && (resources.gpu ?? 0) > 0
})

function toggleCollapse() {
  emit('toggle-collapse', props.id)
}

function onContextMenu(event: MouseEvent) {
  event.preventDefault()
  emit('context-menu', event)
}
</script>

<template>
  <div
    class="tool-node"
    :class="[
      statusClass,
      {
        disabled: !data.enabled,
        provisional: data.provisional,
        collapsed: data.collapsed,
      },
    ]"
    @contextmenu="onContextMenu"
  >
    <div class="node-header" @dblclick="toggleCollapse">
      <span class="node-name">{{ data.name }}</span>
      <span class="category-badge" v-if="data.tool?.categories?.length">{{ data.tool.categories[0] }}</span>
      <span v-if="hasGpu" class="gpu-badge">GPU</span>
    </div>

    <div v-show="!data.collapsed" class="node-body">
      <div class="inputs">
        <InputPin
          v-for="[name, field] in connectableInputs"
          :key="name"
          :node-id="id"
          :field-name="name"
          :field-type="field.type"
          :connected="name in data.connectedInputs"
          :source-label="data.connectedInputs[name]"
        />
        <InputPin
          v-if="showsPositionalPins"
          v-for="i in positionalInputCount"
          :key="`__positional_${i - 1}`"
          :node-id="id"
          :field-name="`__positional_${i - 1}`"
          field-type="DataFrame"
          :connected="`__positional_${i - 1}` in data.connectedInputs"
          :positional="true"
          :positional-index="i - 1"
        />
      </div>

      <div class="outputs">
        <OutputPin
          v-for="[name, field, isPlaceholder] in outputs"
          :key="name"
          :field-name="name"
          :field-type="field.type"
          :placeholder="isPlaceholder"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.tool-node {
  background: var(--p-surface-0);
  border: 2px solid var(--p-content-border-color);
  border-radius: 8px;
  min-width: 160px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  color: var(--p-text-color);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-bottom: 1px solid var(--p-surface-200);
  cursor: pointer;
  user-select: none;
  background: var(--p-surface-50);
  border-radius: 6px 6px 0 0;
  margin: 0.5px;
}

.node-name {
  font-weight: 600;
  font-size: 13px;
}

.category-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--p-primary-50);
  color: var(--p-primary-color);
  margin-left: 4px;
}

.gpu-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--p-orange-500);
  color: var(--p-surface-0);
  font-weight: 700;
}

.node-body {
  padding: 6px 6px;
}

.inputs,
.outputs {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.outputs {
  margin-top: 4px;
}

/* Status */
.status-unexecuted {
  border-color: var(--p-blue-500);
}
.status-executed {
  border-color: var(--p-green-500);
}
.status-out-of-date {
  border-color: var(--p-orange-500);
}
.status-running {
  border-color: var(--p-blue-500);
  animation: pulse 1.5s ease-in-out infinite;
}
.status-failed {
  border-color: var(--p-red-500);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* Disabled & provisional */
.disabled {
  opacity: 0.4;
}
.provisional {
  filter: saturate(0.4);
}

.collapsed .node-header {
  border-bottom: none;
  border-radius: 6px;
}
</style>

<style>
.vue-flow__node-tool.selected .tool-node {
  border-color: var(--p-primary-color);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--p-primary-color) 25%, transparent);
}
</style>
