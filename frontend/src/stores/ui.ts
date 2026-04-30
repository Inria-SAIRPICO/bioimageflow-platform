import { ref, reactive, computed } from 'vue'
import { defineStore } from 'pinia'

export const useUIStore = defineStore('ui', () => {
  const selectedNodeIds = ref<string[]>([])
  const graphNodes = ref<any[]>([])
  const activeWorkflowName = ref<string | null>(null)
  const hasUnsavedChanges = ref(false)
  const isExecutionLocked = ref(false)

  const panels = reactive({
    tools: true,
    nodePanel: true,
    dataTable: true,
    logger: true,
  })

  const hasSelection = computed(() => selectedNodeIds.value.length > 0)
  const isSingleSelection = computed(() => selectedNodeIds.value.length === 1)
  const isMultiSelection = computed(() => selectedNodeIds.value.length > 1)

  const tabTitle = computed(() => {
    let title = 'BioImageFlow'
    if (activeWorkflowName.value) {
      title += ` \u2014 ${activeWorkflowName.value}`
    }
    if (hasUnsavedChanges.value) {
      title += ' *'
    }
    return title
  })

  function setSelectedNodes(ids: string[]) {
    selectedNodeIds.value = ids
  }

  function clearSelection() {
    selectedNodeIds.value = []
  }

  function setGraphNodes(nodes: any[]) {
    graphNodes.value = nodes
  }

  function setActiveWorkflow(name: string | null) {
    activeWorkflowName.value = name
  }

  function markDirty() {
    hasUnsavedChanges.value = true
  }

  function markClean() {
    hasUnsavedChanges.value = false
  }

  function setExecutionLocked(locked: boolean) {
    isExecutionLocked.value = locked
  }

  function togglePanel(panel: keyof typeof panels) {
    panels[panel] = !panels[panel]
  }

  function setPanelVisible(panel: keyof typeof panels, visible: boolean) {
    panels[panel] = visible
  }

  return {
    selectedNodeIds,
    graphNodes,
    activeWorkflowName,
    hasUnsavedChanges,
    isExecutionLocked,
    panels,
    hasSelection,
    isSingleSelection,
    isMultiSelection,
    tabTitle,
    setSelectedNodes,
    clearSelection,
    setGraphNodes,
    setActiveWorkflow,
    markDirty,
    markClean,
    setExecutionLocked,
    togglePanel,
    setPanelVisible,
  }
})
