<script setup lang="ts">
import { computed } from 'vue'
import type { NapariViewingReadinessResponse, NapariViewingRequirementGroup } from '@/api/types'

const props = defineProps<{
  workflowName: string
  report: NapariViewingReadinessResponse | null
  error: string | null
  pending: boolean
}>()
defineEmits<{ dismiss: []; create: [group: NapariViewingRequirementGroup]; manage: [] }>()
const uncovered = computed(() => (props.report?.outputs ?? []).filter(output => output.status !== 'covered' && output.group_id))
const groups = computed(() => (props.report?.groups ?? []).filter(group => uncovered.value.some(output => output.group_id === group.id)))
const unknown = computed(() => (props.report?.outputs ?? []).filter(output => output.status === 'unknown' && !output.group_id))
</script>

<template>
  <section class="viewing-guidance" aria-label="Viewing guidance" data-testid="viewing-guidance">
    <div class="guidance-summary">
      <div>
        <strong>Viewing requirements — {{ workflowName }}</strong>
        <p v-if="pending">Checking viewing requirements…</p>
        <p v-else-if="error">Viewing requirements not checked: {{ error }}. Reopen this saved workflow to check again.</p>
        <p v-else-if="report">{{ report.summary.message }}</p>
        <p>Workflow execution is unaffected.</p>
      </div>
      <button type="button" aria-label="Dismiss viewing guidance" @click="$emit('dismiss')">Continue configuring later</button>
    </div>
    <details v-if="report && (groups.length || unknown.length)">
      <summary>Viewer setup details</summary>
      <div class="guidance-details">
        <p v-if="!report.manifest_complete">The viewing snapshot is incomplete. Unknown metadata needs manual review.</p>
        <article v-for="(group, index) in groups" :key="group.id">
          <strong>Requirement set {{ index + 1 }}</strong>
          <p>Outputs: {{ (group.members ?? []).join(', ') }}</p>
          <p>Required Python distributions: {{ (group.managed_create_prefill.requested_packages ?? []).join(', ') || 'None declared' }}</p>
          <p v-if="group.napari_version">napari: {{ group.napari_version }}</p>
          <ul>
            <li v-for="output in uncovered.filter(output => output.group_id === group.id)" :key="output.output_identity">
              {{ output.output_identity }}: {{ output.effective_reason }}
              <ul v-for="candidate in output.candidates ?? []" :key="candidate.environment_id">
                <li>{{ candidate.name }}: {{ candidate.reason }}</li>
                <li v-for="(issue, issueIndex) in candidate.issues ?? []" :key="issueIndex">{{ issue.distribution }} {{ issue.required_version }}: {{ issue.detail }}<span v-if="issue.installed_version"> (installed {{ issue.installed_version }})</span></li>
              </ul>
            </li>
          </ul>
          <button type="button" @click="$emit('create', group)">Create environment for this set</button>
        </article>
        <article v-for="output in unknown" :key="output.output_identity">
          <strong>{{ output.output_identity }} — Unknown viewing requirements</strong>
          <p>{{ output.manifest_reason || output.effective_reason }}</p>
        </article>
        <p>Refresh or repair registered environments, or attach an existing installation. Unknown or private packages may need manual setup in an external environment; verify their source before installation.</p>
        <button type="button" @click="$emit('manage')">Manage/attach environments</button>
      </div>
    </details>
  </section>
</template>

<style scoped>
.viewing-guidance { border-bottom: 1px solid var(--p-content-border-color); padding: 0.65rem 1rem; font-size: 0.85rem; }
.guidance-summary { display: flex; justify-content: space-between; gap: 1rem; align-items: start; }
p { margin: 0.3rem 0; }
button { cursor: pointer; padding: 0.3rem 0.6rem; }
summary { cursor: pointer; margin-top: 0.4rem; }
.guidance-details { max-height: 18rem; overflow: auto; }
article { margin: 0.6rem 0; padding: 0.4rem; border: 1px solid var(--p-content-border-color); }
</style>
