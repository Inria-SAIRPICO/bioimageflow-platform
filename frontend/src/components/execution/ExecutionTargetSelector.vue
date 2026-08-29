<script setup lang="ts">
import { computed, ref } from 'vue'
import Select from 'primevue/select'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'
import { useSettingsStore } from '@/stores/settings'

const registry = useExecutionRegistryStore()
const settings = useSettingsStore()

const options = computed(() => registry.targets.filter(target => target.enabled).map(target => ({
  ...target,
  option_label: target.label,
})))
const managedTargetSelected = computed(() => registry.selectedTarget?.mode === 'managed_remote')
const loaded = ref(false)

function ensureTargets(): void {
  if (loaded.value) return
  loaded.value = true
  void Promise.all([registry.loadTargets(), settings.fetchSettings()]).then(() => {
    const preferred = (settings.settings as typeof settings.settings & {
      default_execution_target_id?: string
    } | null)?.default_execution_target_id
    if (
      registry.selectedTargetId === 'local'
      && preferred
      && registry.targets.some(target => target.id === preferred && target.enabled)
    ) {
      registry.selectedTargetId = preferred
    }
  })
}
</script>

<template>
  <span class="execution-target-control">
    <Select
      v-model="registry.selectedTargetId"
      :options="options"
      option-label="option_label"
      option-value="id"
      size="small"
      class="execution-target-selector"
      aria-label="Execution target"
      data-testid="execution-target-selector"
      @before-show="ensureTargets"
    >
      <template #option="slotProps">
        <div class="target-option">
          <i :class="slotProps.option.mode === 'local' ? 'pi pi-desktop' : 'pi pi-cloud'" />
          <span>{{ slotProps.option.label }}</span>
        </div>
      </template>
    </Select>
    <span
      v-if="managedTargetSelected"
      class="managed-submit-warning"
      data-testid="managed-submit-warning"
    >
      <i class="pi pi-exclamation-triangle" />
      A remote run can be allocated before its ID is returned. After an uncertain response, reconnect instead of resubmitting.
    </span>
  </span>
</template>

<style scoped>
.execution-target-control { display: inline-flex; align-items: center; gap: .5rem; }
.execution-target-selector { min-width: 8.5rem; max-width: 14rem; }
.target-option { display: flex; align-items: center; gap: 0.5rem; }
.managed-submit-warning { display: inline-flex; align-items: center; gap: .3rem; max-width: 28rem; color: var(--p-orange-700, #9a3412); font-size: .75rem; line-height: 1.2; }
@media (max-width: 900px) { .managed-submit-warning { max-width: 12rem; } }
</style>
