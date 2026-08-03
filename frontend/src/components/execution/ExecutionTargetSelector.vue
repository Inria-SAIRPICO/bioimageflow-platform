<script setup lang="ts">
import { computed, ref } from 'vue'
import Select from 'primevue/select'
import { useExecutionRegistryStore } from '@/stores/executionRegistry'
import { useSettingsStore } from '@/stores/settings'

const registry = useExecutionRegistryStore()
const settings = useSettingsStore()

const options = computed(() => registry.targets.map(target => ({
  ...target,
  option_label: target.enabled
    ? target.label
    : `${target.label} — unavailable`,
  disabled: !target.enabled,
})))
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
  <Select
    v-model="registry.selectedTargetId"
    :options="options"
    option-label="option_label"
    option-value="id"
    option-disabled="disabled"
    size="small"
    class="execution-target-selector"
    aria-label="Execution target"
    data-testid="execution-target-selector"
    @before-show="ensureTargets"
  >
    <template #option="slotProps">
      <div class="target-option" :title="slotProps.option.disabled_reason ?? undefined">
        <i :class="slotProps.option.mode === 'local' ? 'pi pi-desktop' : 'pi pi-cloud'" />
        <span>{{ slotProps.option.label }}</span>
        <small v-if="!slotProps.option.enabled">
          {{ slotProps.option.disabled_reason }}
        </small>
      </div>
    </template>
  </Select>
</template>

<style scoped>
.execution-target-selector { min-width: 8.5rem; max-width: 14rem; }
.target-option { display: flex; align-items: center; gap: 0.5rem; }
.target-option small { color: var(--p-text-muted-color); }
</style>
