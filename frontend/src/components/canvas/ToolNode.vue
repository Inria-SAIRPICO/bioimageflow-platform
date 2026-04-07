<script setup lang="ts">
import { computed } from 'vue'
import type { ToolMetadata } from '@/api/types'
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

const connectableInputs = computed(() => {
  return Object.entries(props.data.tool.inputs).filter(
    ([, field]) => field.connectable,
  )
})

const isDataFrameTool = computed(() => {
  return props.data.tool.tool_type === 'DataFrameTool'
})

const positionalInputCount = computed(() => {
  // For DataFrameTools: number of connected positional inputs + 1 spare
  if (!isDataFrameTool.value) return 0
  const connected = Object.keys(props.data.connectedInputs).filter((k) =>
    k.startsWith('__positional_'),
  ).length
  return connected + 1
})

const outputs = computed(() => {
  return Object.entries(props.data.tool.outputs)
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
      <span v-if="hasGpu" class="gpu-badge">GPU</span>
    </div>

    <div v-show="!data.collapsed" class="node-body">
      <div class="inputs">
        <InputPin
          v-for="[name, field] in connectableInputs"
          :key="name"
          :field-name="name"
          :field-type="field.type"
          :connected="name in data.connectedInputs"
          :source-label="data.connectedInputs[name]"
        />
        <InputPin
          v-if="isDataFrameTool"
          v-for="i in positionalInputCount"
          :key="`__positional_${i - 1}`"
          :field-name="`__positional_${i - 1}`"
          field-type="DataFrame"
          :connected="`__positional_${i - 1}` in data.connectedInputs"
          :positional="true"
          :positional-index="i - 1"
        />
      </div>

      <div class="outputs">
        <OutputPin
          v-for="[name, field] in outputs"
          :key="name"
          :field-name="name"
          :field-type="field.type"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.tool-node {
  background: #ffffff;
  border: 2px solid #dee2e6;
  border-radius: 8px;
  min-width: 160px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  color: #334155;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-bottom: 1px solid #e2e8f0;
  cursor: pointer;
  user-select: none;
  background: #f8fafc;
  border-radius: 6px 6px 0 0;
}

.node-name {
  font-weight: 600;
  font-size: 13px;
}

.gpu-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  background: #ff9500;
  color: #000;
  font-weight: 700;
}

.node-body {
  padding: 6px 10px;
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
  border-color: #4A90D9;
}
.status-executed {
  border-color: #34C759;
}
.status-out-of-date {
  border-color: #FF9500;
}
.status-running {
  border-color: #4A90D9;
  animation: pulse 1.5s ease-in-out infinite;
}
.status-failed {
  border-color: #FF3B30;
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
