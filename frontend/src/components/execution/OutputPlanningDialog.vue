<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import type { OutputPlanningReport } from '@/api/types'

const props = defineProps<{
  report: OutputPlanningReport
  reports?: OutputPlanningReport[]
  busy?: boolean
  error?: string | null
  validationReports?: OutputPlanningReport[]
  correctionUnavailableReason?: string | null
}>()
const emit = defineEmits<{
  cancel: []
  submit: [templates: Record<string, string>]
  selectReport: [nodeId: string]
}>()
const templates = ref<Record<string, string>>({})
watch(() => props.report, report => {
  templates.value = Object.fromEntries(report.fields.map(field => [
    field.field,
    report.suggested_templates?.[field.field] ?? field.template,
  ]))
}, { immediate: true })
const canSubmit = computed(() => props.report.correction_available
  && !props.correctionUnavailableReason
  && props.report.fields.every(field => (templates.value[field.field] ?? '').trim().length > 0))
const explanation = computed(() => props.validationReports?.[0] ?? props.report)
const mismatch = computed(() => explanation.value.code === 'output_group_destination_mismatch')

function cancel(): void {
  if (!props.busy) emit('cancel')
}
</script>

<template>
  <Dialog
    visible modal
    :header="mismatch ? 'Output filenames disagree within a group' : 'Output filenames collide'"
    :closable="!busy" :close-on-escape="!busy" :dismissable-mask="!busy"
    :style="{ width: 'min(45rem, 95vw)' }"
    data-testid="output-planning-dialog"
    @update:visible="visible => { if (!visible) cancel() }"
  >
    <label v-if="(reports?.length ?? 0) > 1" class="planning-template">
      Node to correct
      <select :value="report.node_id" :disabled="busy" data-testid="output-planning-node"
        @change="emit('selectReport', ($event.target as HTMLSelectElement).value)">
        <option v-for="item in reports" :key="item.node_id" :value="item.node_id">{{ item.node_id }}</option>
      </select>
      <small>Other reported conflicts may need a further correction after this node is updated.</small>
    </label>
    <p><strong>{{ report.node_id }}</strong></p>
    <p data-testid="output-planning-detail">{{ explanation.detail }}</p>
    <p v-if="mismatch">
      Rows contributing to one file must use the same destination. Remove values that vary within that group.
    </p>
    <p v-else>Separate files need different destinations. Include a value that distinguishes their rows or groups.</p>

    <div v-if="error" role="alert" class="planning-error" data-testid="output-planning-error">{{ error }}</div>
    <div
      v-for="(conflict, conflictIndex) in explanation.conflicts"
      :key="`${conflictIndex}-${conflict.path}`"
      class="planning-conflict"
    >
      <code class="planning-path">{{ conflict.path }}</code>
      <details :open="conflictIndex === 0">
        <summary>How this filename is produced ({{ conflict.total_members }} contributing entries)</summary>
        <section v-for="(member, memberIndex) in conflict.members" :key="memberIndex" class="planning-member">
          <small>
            {{ member.field }} · {{ member.row_index == null ? 'Batch' : `Row ${member.row_index}` }} · Group {{ member.group_index }}
          </small>
          <dl v-if="Object.keys(member.group_key ?? {}).length" class="planning-keys">
            <template v-for="(value, name) in member.group_key" :key="name"><dt>{{ name }}</dt><dd>{{ value }}</dd></template>
          </dl>
          <table class="planning-expansion" data-testid="output-template-expansion">
            <thead><tr><th>Template part</th><th>Resolved value</th></tr></thead>
            <tbody><tr v-for="(part, index) in member.parts" :key="index">
              <td><code>{{ part.text }}</code></td>
              <td><code>{{ part.value }}</code><small v-if="part.kind === 'literal'"> (literal text)</small></td>
            </tr></tbody>
          </table>
        </section>
        <small v-if="conflict.total_members > conflict.members.length">Representative entries shown; {{ conflict.total_members }} entries are affected.</small>
      </details>
    </div>
    <small v-if="explanation.total_conflicts > explanation.conflicts.length">
      Showing {{ explanation.conflicts.length }} of {{ explanation.total_conflicts }} conflicts.
    </small>

    <div v-for="field in report.fields" :key="field.field" class="planning-template">
      <label :for="`collision-template-${field.field}`">Output template · {{ field.field }}</label>
      <small>{{ field.description }}</small>
      <code>Current: {{ field.template }}</code>
      <InputText :id="`collision-template-${field.field}`" v-model="templates[field.field]" :disabled="busy || !report.correction_available"
        :data-testid="`collision-template-${field.field}`" />
    </div>
    <p v-if="correctionUnavailableReason || report.correction_unavailable_reason" role="status" class="planning-unavailable">
      {{ correctionUnavailableReason || report.correction_unavailable_reason }}
      You can edit the workflow normally and run it again.
    </p>
    <p class="planning-consequences">
      Updating the template changes your workflow. Continuing restarts execution and reuses available cached results.
      Changed filenames may affect downstream tools that interpret them.
      Results already completed will be kept.
    </p>
    <template #footer>
      <Button label="Cancel execution" severity="secondary" :disabled="busy" data-testid="cancel-output-correction" @click="cancel" />
      <Button label="Update template and continue" :loading="busy" :disabled="busy || !canSubmit"
        data-testid="apply-output-correction" @click="emit('submit', { ...templates })" />
    </template>
  </Dialog>
</template>

<style scoped>
.planning-error { padding: .65rem; color: var(--p-red-700); background: var(--p-red-50); border-radius: 4px; }
.planning-conflict { margin: 1rem 0; padding: .65rem; border: 1px solid var(--p-content-border-color); border-radius: 4px; }
.planning-path { display: block; overflow-wrap: anywhere; margin-bottom: .5rem; }
.planning-member { margin: .65rem 0; }
.planning-expansion { width: 100%; border-collapse: collapse; margin-top: .35rem; table-layout: fixed; }
.planning-expansion th, .planning-expansion td { text-align: left; padding: .3rem; border-bottom: 1px solid var(--p-content-border-color); overflow-wrap: anywhere; vertical-align: top; }
.planning-keys { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: .25rem .75rem; font-size: .85rem; }
.planning-keys dd { margin: 0; overflow-wrap: anywhere; }
.planning-template { display: grid; gap: .35rem; margin: 1rem 0; }
.planning-template label { font-weight: 600; }
.planning-template code { overflow-wrap: anywhere; font-size: .85rem; }
.planning-template small, .planning-consequences, .planning-unavailable { color: var(--p-text-muted-color); }
.planning-consequences { font-size: .9rem; }
</style>
