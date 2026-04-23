<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import Menubar from 'primevue/menubar'
import { useToast } from 'primevue/usetoast'
import type { MenuItem } from 'primevue/menuitem'
import { useUIStore } from '@/stores/ui'
import { useExecutionStore } from '@/stores/execution'
import { useGraphSync } from '@/composables/useGraphSync'
import RunButton from '@/components/execution/RunButton.vue'

const uiStore = useUIStore()
const executionStore = useExecutionStore()
const { flushNow, validationResult, isPending, currentGraph } = useGraphSync()

// useToast throws when no ToastService is provided (e.g. in unit tests
// that mount MenuBar in isolation). The toasts are a nice-to-have here.
let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}

const runButtonRef = useTemplateRef<InstanceType<typeof RunButton> | null>(
  'runButtonRef',
)

const graphSync = { flushNow, validationResult }

function panelToggle(label: string, panelKey: keyof typeof uiStore.panels): MenuItem {
  return {
    label,
    icon: uiStore.panels[panelKey] ? 'pi pi-check' : undefined,
    command: () => uiStore.togglePanel(panelKey),
  }
}

function runDisabledReason(): string | null {
  if (executionStore.isRunning) return 'Execution in progress'
  if (isPending.value) return 'Waiting for validation…'
  return null
}

const menuItems = computed<MenuItem[]>(() => [
  {
    label: 'Workflow',
    items: [
      { label: 'New', icon: 'pi pi-plus', disabled: true },
      { label: 'Open', icon: 'pi pi-folder-open', disabled: true },
      { label: 'Save', icon: 'pi pi-save', disabled: true },
      { label: 'Save As', disabled: true },
      { label: 'Delete', icon: 'pi pi-trash', disabled: true },
    ],
  },
  {
    label: 'Edit',
    items: [
      { label: 'Undo', icon: 'pi pi-undo', disabled: true },
      { label: 'Redo', icon: 'pi pi-refresh', disabled: true },
      { separator: true },
      { label: 'Cut', icon: 'pi pi-clipboard', disabled: true },
      { label: 'Copy', icon: 'pi pi-copy', disabled: true },
      { label: 'Paste', disabled: true },
      { separator: true },
      { label: 'Select All', disabled: true },
    ],
  },
  {
    label: 'Execution',
    items: [
      {
        label: 'Run Workflow',
        icon: 'pi pi-play',
        disabled: runDisabledReason() !== null,
        command: () => runButtonRef.value?.onRun(),
      },
      {
        label: 'Execute Selected',
        icon: 'pi pi-forward',
        disabled:
          runDisabledReason() !== null || uiStore.selectedNodeIds.length === 0,
        command: () => runButtonRef.value?.onExecuteSelected(),
      },
      {
        label: 'Stop',
        icon: 'pi pi-stop',
        disabled: !executionStore.isRunning,
        command: () => runButtonRef.value?.onStop(),
      },
    ],
  },
  {
    label: 'View',
    items: [
      panelToggle('Tools Panel', 'tools'),
      panelToggle('Nodes', 'nodePanel'),
      panelToggle('Data Table', 'dataTable'),
      panelToggle('Logger', 'logger'),
    ],
  },
  {
    label: 'Help',
    items: [{ label: 'About', disabled: true }],
  },
])

function onRunButtonToast(payload: {
  severity: 'warn' | 'error'
  summary: string
  detail?: string
}) {
  if (!toast) return
  // Errors stay open until the user dismisses them (so they have time to
  // read a multi-line validation summary); warnings auto-dismiss.
  toast.add({
    severity: payload.severity,
    summary: payload.summary,
    detail: payload.detail,
    life: payload.severity === 'error' ? undefined : 5000,
  })
}

defineExpose({ menuItems })
</script>

<template>
  <Menubar :model="menuItems" data-testid="app-menubar">
    <template #end>
      <RunButton
        ref="runButtonRef"
        :graph="currentGraph"
        :graph-sync="graphSync"
        :sync-pending="isPending"
        @toast="onRunButtonToast"
      />
    </template>
  </Menubar>
</template>
