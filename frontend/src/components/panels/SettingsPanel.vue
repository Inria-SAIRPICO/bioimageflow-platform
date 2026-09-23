<script setup lang="ts">
import { computed, nextTick, useTemplateRef, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import { useSettingsStore } from '@/stores/settings'
import { useWorkflowStore } from '@/stores/workflow'
import { useSettingsPanel } from '@/composables/useSettingsPanel'
import type { WorkspaceSettings } from '@/stores/settings'
import ExternalEditorSection from '@/components/panels/sections/ExternalEditorSection.vue'
import ExecutionSection from '@/components/panels/sections/ExecutionSection.vue'
import DisplaySection from '@/components/panels/sections/DisplaySection.vue'
import StorageSection from '@/components/panels/sections/StorageSection.vue'
import OmeroSection from '@/components/panels/sections/OmeroSection.vue'
import ImageViewersSection from '@/components/panels/sections/ImageViewersSection.vue'

const settingsStore = useSettingsStore()
const workflowStore = useWorkflowStore()
const panel = useSettingsPanel()
const storageSection = useTemplateRef<InstanceType<typeof StorageSection>>('storageSection')

let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}

// Lazy-load on first open.
watch(panel.isOpen, async (open) => {
  if (!open) return
  if (!settingsStore.isLoaded) await settingsStore.fetchSettings()
  await nextTick()
  await storageSection.value?.refreshWorkspaceInfo()
  await storageSection.value?.refreshDemoStatus()
})

// Surface server errors as a toast as soon as `error` transitions to non-null.
watch(
  () => settingsStore.error,
  (next, prev) => {
    if (next && next !== prev) {
      toast?.add({
        severity: 'error',
        summary: 'Settings update failed',
        detail: next,
        life: 6000,
      })
    }
  },
)

const visible = computed({
  get: () => panel.isOpen.value,
  set: (value: boolean) => {
    if (value) panel.open()
    else panel.close()
  },
})

const fallback: WorkspaceSettings & {
  resolved_tool_store_path?: string
} = {
  deployment_mode: 'desktop',
  external_editor: null,
  fiji_path: null,
  napari_registry_revision: 0,
  napari_environments: [],
  napari_default_environment_id: null,
  napari_filename_rules: [],
  napari_environment_operations: [],
  omero_instances: [],
  tool_store_path: '~/.bioimageflow/tool_packages/',
  update_mode: 'auto',
  new_workflow_execution: 'sequential',
  default_execution_target_id: 'local',
  node_data_page_size: 250,
  keyboard_shortcuts: {},
  dev_mode: true,
  enable_unsafe_webapp_features: false,
  datasets_root: null,
  max_upload_size: 2147483648,
  workspace_path: null,
  workspaces_root: null,
  resolved_tool_store_path: '',
  latest_output_effective_mode: 'pointer',
  latest_output_warning: null,
}
const liveSettings = computed(() => settingsStore.settings ?? fallback)

async function onUpdate(payload: { field: PropertyKey; value: unknown }) {
  if (typeof payload.field !== 'string') return
  await settingsStore.updateSettings(
    { [payload.field]: payload.value } as Partial<WorkspaceSettings>,
  )
  if (payload.field === 'workspace_path' && !settingsStore.error) {
    await workflowStore.fetchWorkflowTree()
    await storageSection.value?.refreshWorkspaceInfo()
    await storageSection.value?.refreshDemoStatus()
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    header="Preferences"
    :style="{ width: 'min(640px, calc(100vw - 2rem))' }"
    data-testid="settings-panel"
  >
    <p
      v-if="settingsStore.isLoading"
      class="settings-loading"
      role="status"
      data-testid="settings-loading"
    >
      Loading settings…
    </p>
    <Tabs v-else v-model:value="panel.activeTab.value" data-testid="settings-tabs">
      <TabList>
        <Tab value="external">External Editor</Tab>
        <Tab v-if="settingsStore.isDesktop" value="viewers">Image Viewers</Tab>
        <Tab value="execution">Execution</Tab>
        <Tab value="display">Display</Tab>
        <Tab value="storage">Storage</Tab>
        <Tab value="omero">OMERO</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="external">
          <ExternalEditorSection :model-value="liveSettings" @update:field="onUpdate" />
        </TabPanel>
        <TabPanel v-if="settingsStore.isDesktop" value="viewers">
          <ImageViewersSection :model-value="liveSettings" @update:field="onUpdate" />
        </TabPanel>
        <TabPanel value="execution">
          <ExecutionSection :model-value="liveSettings" @update:field="onUpdate" />
        </TabPanel>
        <TabPanel value="display">
          <DisplaySection :model-value="liveSettings" @update:field="onUpdate" />
        </TabPanel>
        <TabPanel value="storage">
          <StorageSection
            ref="storageSection"
            :model-value="liveSettings"
            @update:field="onUpdate"
            @refresh-output-view="settingsStore.fetchSettings"
          />
        </TabPanel>
        <TabPanel value="omero">
          <OmeroSection :model-value="liveSettings" @update:field="onUpdate" />
        </TabPanel>
      </TabPanels>
    </Tabs>
    <template #footer>
      <Button
        label="Close"
        severity="secondary"
        data-testid="settings-close"
        @click="panel.close"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.settings-loading {
  margin: 0;
  color: var(--p-text-muted-color, #777);
}
</style>
