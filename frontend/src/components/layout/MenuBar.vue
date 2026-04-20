<script setup lang="ts">
import { computed } from 'vue'
import Menubar from 'primevue/menubar'
import type { MenuItem } from 'primevue/menuitem'
import { useUIStore } from '@/stores/ui'

const uiStore = useUIStore()

function panelToggle(label: string, panelKey: keyof typeof uiStore.panels): MenuItem {
  return {
    label,
    icon: uiStore.panels[panelKey] ? 'pi pi-check' : undefined,
    command: () => uiStore.togglePanel(panelKey),
  }
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
      { label: 'Run', icon: 'pi pi-play', disabled: true },
      { label: 'Stop', icon: 'pi pi-stop', disabled: true },
      { label: 'Clear Results', icon: 'pi pi-eraser', disabled: true },
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
    items: [
      { label: 'About', disabled: true },
    ],
  },
])

defineExpose({ menuItems })
</script>

<template>
  <Menubar :model="menuItems" data-testid="app-menubar" />
</template>
