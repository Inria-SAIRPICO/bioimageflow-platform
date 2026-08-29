<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import { downloadSlurmProfileExample, type ExecutionProfile } from '@/api/executionProfiles'
import { useExecutionProfilesStore } from '@/stores/executionProfiles'
import { selectFile } from '@/utils/nativeDialogs'

defineProps<{ editable: boolean }>()

const profiles = useExecutionProfilesStore()
const editorOpen = ref(false)
const describeOpen = ref(false)
const editing = ref<ExecutionProfile | null>(null)
const describedProfile = ref<ExecutionProfile | null>(null)
const formError = ref<string | null>(null)
const actionError = ref<string | null>(null)

const form = reactive({
  name: '',
  configPath: '',
  enabled: true,
})

const description = computed(() => (
  describedProfile.value ? profiles.descriptions[describedProfile.value.id] ?? null : null
))
const requiredManagedCapabilities = new Set([
  'remote_cluster_bootstrap',
  'remote_cluster_validation',
  'remote_cluster_planning',
  'idempotent_planned_submission',
  'durable_remote_diagnostics',
])
const optionalManagedCapabilities = new Set([
  'remote_node_path_overrides',
  'managed_uv_environment',
  'managed_pixi_environment',
  'managed_pylock_environment',
  'offline_wheelhouse_environment',
  'existing_python_attestation',
  'managed_setup_scripts',
  'cluster_cleanup_planning',
  'submitted_run_retry',
  'submitted_recompute',
  'submitted_result_export',
])
const capabilityEntries = computed(() => Object.entries(
  description.value?.capabilities.capabilities ?? {},
))
const managedCapabilities = computed(() => capabilityEntries.value.filter(([key]) => (
  requiredManagedCapabilities.has(key) || optionalManagedCapabilities.has(key)
)))
const otherCapabilities = computed(() => capabilityEntries.value.filter(([key]) => (
  !requiredManagedCapabilities.has(key) && !optionalManagedCapabilities.has(key)
)))
const missingRequiredCapabilities = computed(() => managedCapabilities.value.filter(
  ([key, value]) => requiredManagedCapabilities.has(key) && !value.supported,
))

interface ClusterFact {
  label: string
  value: string
}

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function factValue(value: unknown): string | null {
  if (typeof value === 'string' && value.length > 0) return value
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return null
}

const clusterFacts = computed<ClusterFact[]>(() => {
  const cluster = description.value?.cluster
  if (!cluster) return []
  const environment = record(cluster.environment)
  const parsl = record(cluster.parsl)
  const orchestrator = record(cluster.orchestrator)
  const setup = record(cluster.setup)
  const walltime = factValue(orchestrator?.walltime_seconds)
  const values: Array<[string, string | null]> = [
    ['Results root', factValue(cluster.results_root)],
    ['Environment kind', factValue(environment?.kind)],
    ['Parsl source', factValue(parsl?.source_kind)],
    ['Parsl factory', factValue(parsl?.factory)],
    ['Scheduler', factValue(orchestrator?.scheduler)],
    ['Project / account', factValue(orchestrator?.project)],
    ['Queue / partition', factValue(orchestrator?.queue)],
    ['Orchestrator walltime', walltime === null ? null : `${walltime} seconds`],
    ['Orchestrator CPU', factValue(orchestrator?.cpu)],
    ['Setup script', setup === null ? 'Not configured' : 'Configured'],
    ['Setup source', factValue(setup?.source_kind)],
    ['Setup digest', factValue(setup?.digest)],
    ['Setup cluster path', factValue(setup?.cluster_path)],
  ]
  return values.flatMap(([label, value]) => value === null ? [] : [{ label, value }])
})

function connectionSummary(connection: Record<string, unknown> | null | undefined): string {
  if (!connection) return 'Not checked'
  const reachable = connection.reachable ?? connection.ok
  const message = connection.message
  if (reachable === true) return typeof message === 'string' && message ? message : 'Reachable'
  if (typeof message === 'string' && message) return message
  if (reachable === false) return 'Unavailable'
  return 'Connection report available'
}

function resetForm(): void {
  Object.assign(form, { name: '', configPath: '', enabled: true })
}

function openNew(): void {
  editing.value = null
  resetForm()
  formError.value = null
  editorOpen.value = true
}

function openEdit(profile: ExecutionProfile): void {
  editing.value = profile
  Object.assign(form, {
    name: profile.name,
    configPath: profile.config_path,
    enabled: profile.enabled,
  })
  formError.value = null
  editorOpen.value = true
}

async function chooseConfig(): Promise<void> {
  const selected = await selectFile('Select RemoteCluster configuration', ['*.py'])
  if (selected !== null) form.configPath = selected
}

async function save(): Promise<void> {
  formError.value = null
  try {
    const draft = {
      name: form.name.trim(),
      enabled: form.enabled,
      config_path: form.configPath.trim(),
    }
    if (!draft.name) throw new Error('Name is required')
    if (!draft.config_path) throw new Error('Configuration script is required')
    if (editing.value) await profiles.update(editing.value, draft)
    else await profiles.create(draft)
    editorOpen.value = false
  } catch (cause) {
    formError.value = cause instanceof Error ? cause.message : String(cause)
  }
}

async function describe(profile: ExecutionProfile, checkConnection = false): Promise<void> {
  actionError.value = null
  describedProfile.value = profile
  describeOpen.value = true
  try {
    await profiles.describe(profile, checkConnection)
  } catch (cause) {
    actionError.value = cause instanceof Error ? cause.message : String(cause)
  }
}

async function downloadExample(): Promise<void> {
  actionError.value = null
  try {
    const blob = await downloadSlurmProfileExample()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'bioimageflow-slurm-profile.zip'
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (cause) {
    actionError.value = cause instanceof Error ? cause.message : String(cause)
  }
}

onMounted(() => void profiles.refresh())
</script>

<template>
  <section class="profiles" data-testid="execution-profiles-section">
    <header>
      <div>
        <h3>Managed remote clusters</h3>
        <p>Each profile loads one trusted Python script that defines <code>cluster = RemoteCluster(...)</code>.</p>
      </div>
      <div class="actions">
        <Button label="Slurm example" icon="pi pi-download" severity="secondary" size="small" @click="downloadExample" />
        <Button v-if="editable" label="Add profile" icon="pi pi-plus" size="small" @click="openNew" />
      </div>
    </header>
    <p class="security-note">Authentication stays in SSH and the process environment. Secrets are never saved in platform profile state.</p>
    <p v-if="profiles.loading" role="status">Loading execution profiles…</p>
    <p v-if="profiles.error" class="error" role="alert">{{ profiles.error }}</p>
    <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>
    <article v-for="profile in profiles.profiles" :key="profile.id" class="profile-card">
      <div class="profile-summary">
        <div>
          <strong>{{ profile.name }}</strong>
          <Tag :value="profile.enabled ? 'enabled' : 'disabled'" :severity="profile.enabled ? 'success' : 'secondary'" />
        </div>
        <span>{{ profile.cluster_host }} · {{ profile.cluster_root }}</span>
        <code :title="profile.config_digest">{{ profile.config_digest }}</code>
        <small>{{ profile.config_path }} · revision {{ profile.revision }}</small>
      </div>
      <div class="actions">
        <Button label="Describe" severity="secondary" size="small" :loading="profiles.describing === profile.id" @click="describe(profile)" />
        <Button v-if="profile.editable" label="Edit" severity="secondary" size="small" @click="openEdit(profile)" />
        <Button v-if="profile.editable" label="Remove" severity="danger" text size="small" @click="profiles.remove(profile)" />
      </div>
    </article>
    <p v-if="!profiles.loading && profiles.profiles.length === 0" class="empty">
      No managed remote cluster is configured. Local Direct and Wetlands execution remain available.
    </p>

    <Dialog v-model:visible="editorOpen" modal :header="editing ? 'Edit remote cluster' : 'Add remote cluster'" :style="{ width: 'min(42rem, calc(100vw - 2rem))' }">
      <div class="form-grid">
        <label>Name<InputText v-model="form.name" /></label>
        <label>
          Configuration script
          <span class="path-row">
            <InputText v-model="form.configPath" placeholder="/absolute/path/to/cluster.py" />
            <Button label="Browse…" severity="secondary" @click="chooseConfig" />
          </span>
        </label>
        <small>The platform imports this trusted script only on the backend. Saving snapshots its digest and the non-secret host and root identities.</small>
        <label class="checkbox"><Checkbox v-model="form.enabled" binary />Enabled</label>
      </div>
      <p v-if="formError" class="error" role="alert">{{ formError }}</p>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="editorOpen = false" />
        <Button label="Save" @click="save" />
      </template>
    </Dialog>

    <Dialog v-model:visible="describeOpen" modal header="Cluster description" :style="{ width: 'min(52rem, calc(100vw - 2rem))' }" data-testid="cluster-description">
      <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>
      <div v-else-if="profiles.describing" class="loading"><i class="pi pi-spin pi-spinner" /> Describing cluster…</div>
      <template v-else-if="description">
        <dl class="description-grid">
          <dt>Host</dt><dd>{{ description.cluster_host }}</dd>
          <dt>Writable root</dt><dd>{{ description.cluster_root }}</dd>
          <dt>Configuration digest</dt><dd><code>{{ description.config_digest }}</code></dd>
          <dt>Configured</dt><dd>{{ description.configured ? 'Yes' : 'No' }}</dd>
          <dt>Connection</dt><dd>{{ connectionSummary(description.connection) }}</dd>
        </dl>
        <section v-if="clusterFacts.length" data-testid="cluster-site-facts">
          <h4>Sanitized site configuration</h4>
          <dl class="description-grid">
            <template v-for="item in clusterFacts" :key="item.label">
              <dt>{{ item.label }}</dt><dd><code>{{ item.value }}</code></dd>
            </template>
          </dl>
        </section>
        <div class="describe-actions">
          <Button label="Check connection" icon="pi pi-wifi" severity="secondary" :loading="profiles.describing === describedProfile?.id" @click="describedProfile && describe(describedProfile, true)" />
        </div>
        <section>
          <h4>Managed execution capabilities</h4>
          <ul class="capability-list">
            <li v-for="[key, value] in managedCapabilities" :key="key">
              <Tag
                :value="requiredManagedCapabilities.has(key) ? (value.supported ? 'required · ready' : 'required · unavailable') : (value.supported ? 'optional · available' : 'optional · unavailable')"
                :severity="value.supported ? 'success' : requiredManagedCapabilities.has(key) ? 'danger' : 'secondary'"
              />
              <code>{{ key }}</code>
              <span v-if="value.reason">{{ value.reason }}</span>
            </li>
          </ul>
          <p v-if="missingRequiredCapabilities.length === 0">All required managed-submission capabilities are available.</p>
          <details v-if="otherCapabilities.length" class="other-capabilities">
            <summary>Other BioImageFlow capability discovery</summary>
            <p>These library capabilities are not requirements for this managed target.</p>
            <ul class="capability-list">
              <li v-for="[key, value] in otherCapabilities" :key="key">
                <Tag :value="value.supported ? 'supported' : 'unavailable'" severity="secondary" />
                <code>{{ key }}</code>
                <span v-if="value.reason">{{ value.reason }}</span>
              </li>
            </ul>
          </details>
        </section>
        <section v-if="description.diagnostics?.length">
          <h4>Diagnostics</h4>
          <article v-for="(diagnostic, index) in description.diagnostics ?? []" :key="index" class="diagnostic">
            <strong>{{ diagnostic.phase }} · {{ diagnostic.category }}</strong>
            <p>{{ diagnostic.message }}</p>
            <p v-if="diagnostic.next_action"><strong>Next action:</strong> {{ diagnostic.next_action }}</p>
          </article>
        </section>
      </template>
    </Dialog>
  </section>
</template>

<style scoped>
.profiles { display: grid; gap: .75rem; }
header, .profile-card, .actions, .profile-summary > div, .describe-actions { display: flex; align-items: center; gap: .5rem; }
header, .profile-card { justify-content: space-between; }
h3, h4, p { margin: 0; }
header p, .profile-summary span, .profile-summary small, .empty, .security-note { color: var(--p-text-muted-color, #666); }
.security-note { padding: .65rem; border-radius: 6px; background: var(--p-surface-100); }
.profile-card { padding: .75rem; border: 1px solid var(--p-content-border-color, #ddd); border-radius: 6px; }
.profile-summary { min-width: 0; display: grid; gap: .25rem; }
.profile-summary code, .profile-summary small { overflow-wrap: anywhere; }
.form-grid { display: grid; gap: .8rem; }
.form-grid label { display: grid; gap: .35rem; font-weight: 600; }
.checkbox { display: flex !important; align-items: center; justify-content: start; }
.path-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: .5rem; }
.error { color: var(--p-red-600, #c00); white-space: pre-wrap; }
.loading { display: flex; align-items: center; justify-content: center; gap: .5rem; min-height: 8rem; }
.description-grid { display: grid; grid-template-columns: 9rem minmax(0, 1fr); gap: .45rem; }
.description-grid dt { color: var(--p-text-muted-color); }
.description-grid dd { margin: 0; overflow-wrap: anywhere; }
.capability-list { display: grid; gap: .35rem; padding: 0; list-style: none; }
.capability-list li { display: grid; grid-template-columns: auto minmax(12rem, auto) 1fr; align-items: center; gap: .5rem; }
.other-capabilities { margin-top: .75rem; }
.other-capabilities summary { cursor: pointer; font-weight: 600; }
.diagnostic { margin-top: .5rem; padding: .65rem; border-radius: 6px; background: var(--p-surface-100); }
@media (max-width: 680px) { header, .profile-card { align-items: stretch; flex-direction: column; } .actions { flex-wrap: wrap; } .path-row { grid-template-columns: 1fr; } }
</style>
