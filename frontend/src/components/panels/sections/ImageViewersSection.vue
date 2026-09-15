<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import ProgressBar from 'primevue/progressbar'
import type { Settings } from '@/stores/settings'
import { selectFolder } from '@/utils/nativeDialogs'
import { useNapariStore } from '@/stores/napari'
import { useSettingsPanel } from '@/composables/useSettingsPanel'

const FIJI_DOWNLOAD_URL = 'https://imagej.net/software/fiji/downloads'
const props = defineProps<{ modelValue: Settings }>()
const emit = defineEmits<{ (e: 'update:field', payload: { field: keyof Settings; value: unknown }): void }>()
const napari = useNapariStore()
const settingsPanel = useSettingsPanel()
const error = ref<string | null>(null)
const external = reactive({ name: '', path: '' })
const create = reactive({ name: '', preset: 'default' as 'default' | 'legacy' | 'advanced', python: '==3.12.*', napari: '0.9.1', qt: 'PyQt6' as 'PyQt5' | 'PyQt6', packages: '' })
const rule = reactive({ mode: 'extension' as 'extension' | 'pattern', value: '', environmentId: '', readerId: '' })
const testFilename = ref('')
const preview = ref<{ matching_rule_ids: string[]; winner_rule_id?: string | null } | null>(null)
const lifecycle = reactive<Record<string, string>>({})
const copyFromId = ref<string | null>(null)
const setupGroupId = ref('')
const selectedRecommendations = ref<string[]>([])
const sourceConfirmed = ref(false)
const editingRuleId = ref<string | null>(null)
const ruleEdit = reactive({ pattern: '', environmentId: '', readerId: '' })
const fijiPath = ref(props.modelValue.fiji_path ?? '')
watch(() => props.modelValue.fiji_path, value => { fijiPath.value = value ?? '' })

const visibleOperations = computed(() => napari.operations.filter(item => item.state !== 'completed'))
const extensionPreview = computed(() => {
  const value = rule.value.trim()
  if (rule.mode !== 'extension' || !value) return value
  return `*.${value.replace(/^\.+/, '')}`
})
const previewMatches = computed(() => (preview.value?.matching_rule_ids ?? []).map(id => (
  napari.filenameRules.find(item => item.id === id)?.pattern ?? id
)))
const selectedSetupGroup = computed(() => settingsPanel.napariCreatePrefills.value.find(group => group.id === setupGroupId.value) ?? null)
const recommendedPackages = computed(() => selectedSetupGroup.value?.managed_create_prefill.recommended_packages ?? [])
const activeOperationStates = new Set(['pending', 'resolving', 'installing', 'validating', 'removing'])
const catchAllWarning = computed(() => {
  const newCatchAll = rule.mode === 'pattern' && rule.value.trim() === '*'
  const existingCatchAll = napari.filenameRules.findIndex(item => item.enabled && item.pattern === '*')
  if (!newCatchAll && (existingCatchAll < 0 || existingCatchAll === napari.filenameRules.length - 1)) return null
  return 'A catch-all * rule wins before every later rule. A global default is usually clearer.'
})

watch(settingsPanel.napariCreatePrefills, groups => {
  if (groups.length === 0) return
  if (!groups.some(group => group.id === setupGroupId.value)) setupGroupId.value = groups[0]!.id
}, { immediate: true })

watch(selectedSetupGroup, group => {
  if (!group) return
  create.packages = (group.managed_create_prefill.requested_packages ?? []).join('\n')
  selectedRecommendations.value = []
  sourceConfirmed.value = false
  if (!create.name.trim()) create.name = `Viewer environment ${settingsPanel.napariCreatePrefills.value.indexOf(group) + 1}`
}, { immediate: true })

function detail(exc: any): string {
  return exc?.response?.data?.detail?.detail ?? exc?.response?.data?.detail ?? exc?.message ?? String(exc)
}

async function run(action: () => Promise<void>) {
  error.value = null
  try { await action() } catch (exc) { error.value = detail(exc) }
}

async function addExisting() {
  await run(async () => {
    await napari.registerEnvironment(external)
    external.name = ''; external.path = ''
  })
}

async function browseEnvironment() {
  const selected = await selectFolder('Choose a Conda or virtual environment')
  if (selected) external.path = selected
}

function packageList(): string[] {
  return [...new Set([
    ...create.packages.split(/[\n,]/).map(value => value.trim()).filter(Boolean),
    ...selectedRecommendations.value,
  ])]
}

async function createManaged() {
  if (selectedSetupGroup.value?.managed_create_prefill.requires_source_confirmation && !sourceConfirmed.value) return
  await run(async () => {
    const recipe = create.preset === 'advanced'
      ? { preset: create.preset, python: create.python, napari: create.napari, qt: create.qt, requested_packages: packageList() }
      : { preset: create.preset, requested_packages: packageList() }
    const operation = copyFromId.value
      ? await napari.copyManagedEnvironment(copyFromId.value, {
          name: create.name,
          ...copyMatrixOverrides(copyFromId.value),
          requested_packages: packageList(),
        })
      : await napari.createManagedEnvironment({ name: create.name, recipe })
    if (setupGroupId.value) settingsPanel.consumeNapariCreatePrefill(setupGroupId.value)
    copyFromId.value = null
    void napari.watchOperation(operation.environment_id, operation.id).catch(exc => { error.value = detail(exc) })
  })
}

function resolvedCreateMatrix() {
  if (create.preset === 'default') return { python: '==3.12.*', napari: '0.9.1', qt: 'PyQt6' as const }
  if (create.preset === 'legacy') return { python: '==3.12.*', napari: '0.6.6', qt: 'PyQt5' as const }
  return { python: create.python, napari: create.napari, qt: create.qt }
}

function copyMatrixOverrides(id: string) {
  const source = napari.environments.find(item => item.id === id)?.managed?.recipe
  const desired = resolvedCreateMatrix()
  return {
    python: desired.python === source?.python ? undefined : desired.python,
    napari: desired.napari === source?.napari ? undefined : desired.napari,
    qt: desired.qt === source?.qt ? undefined : desired.qt,
  }
}

function prepareCopy(id: string) {
  const environment = napari.environments.find(item => item.id === id)
  if (!environment?.managed) return
  const recipe = environment.managed.recipe
  copyFromId.value = id
  create.name = `${environment.name} copy`
  create.preset = recipe.preset ?? 'advanced'
  create.python = recipe.python ?? '==3.12.*'
  create.napari = recipe.napari ?? '0.9.1'
  create.qt = recipe.qt ?? 'PyQt6'
  create.packages = (recipe.requested_packages ?? []).join('\n')
}

async function rename(id: string, currentName: string) {
  const name = prompt('Environment name', currentName)?.trim()
  if (!name || name === currentName) return
  await run(async () => napari.updateEnvironment(id, { name }))
}

async function locate(id: string) {
  const path = await selectFolder('Locate the environment')
  if (!path) return
  await run(async () => napari.updateEnvironment(id, { path }))
}

async function refresh(id: string) {
  await run(async () => napari.probeEnvironment(id))
}

async function launch(id: string) {
  await run(async () => {
    await napari.launchEmpty(id)
    lifecycle[id] = napari.environmentState(id).status ?? 'running'
  })
}

async function forget(id: string) {
  if (!confirm('Forget this external environment and clear its defaults, rules, and favorites?')) return
  await run(async () => napari.forgetEnvironment(id))
}

async function removeManaged(id: string) {
  if (!confirm('Delete this BioImageFlow-managed installation? Its running viewer will be closed.')) return
  await run(async () => {
    const operation = await napari.deleteManagedEnvironment(id)
    void napari.watchOperation(operation.environment_id, operation.id).catch(exc => { error.value = detail(exc) })
  })
}

async function retry(id: string) {
  await run(async () => {
    const operation = await napari.retryManagedEnvironment(id)
    void napari.watchOperation(operation.environment_id, operation.id).catch(exc => { error.value = detail(exc) })
  })
}

async function setDefault(event: Event) {
  const value = (event.target as HTMLSelectElement).value || null
  await run(async () => napari.setDefaultEnvironment(value))
}

async function addRule() {
  if (!rule.value || !rule.environmentId) return
  await run(async () => {
    await napari.addFilenameRule({ value: rule.value, mode: rule.mode, environment_id: rule.environmentId, reader_id: rule.readerId || null, enabled: true })
    rule.value = ''; rule.readerId = ''
    preview.value = null
  })
}

async function moveRule(index: number, delta: number) {
  const rules = [...napari.filenameRules]
  const target = index + delta
  if (target < 0 || target >= rules.length) return
  ;[rules[index], rules[target]] = [rules[target]!, rules[index]!]
  await run(async () => { await napari.replaceFilenameRules(rules); preview.value = null })
}

async function deleteRule(index: number) {
  const rules = napari.filenameRules.filter((_, item) => item !== index)
  await run(async () => { await napari.replaceFilenameRules(rules); preview.value = null })
}

async function toggleRule(index: number) {
  const rules = napari.filenameRules.map((item, itemIndex) => itemIndex === index
    ? { ...item, enabled: !item.enabled }
    : item)
  await run(async () => { await napari.replaceFilenameRules(rules); preview.value = null })
}

async function testRules() {
  await run(async () => { preview.value = await napari.previewFilename(testFilename.value) })
}

async function cancel(environmentId: string, operationId: string) {
  await run(async () => napari.cancelManagedOperation(environmentId, operationId))
}

async function loadRegistry() {
  await napari.fetchRegistry()
  for (const operation of napari.operations.filter(item => activeOperationStates.has(item.state))) {
    void napari.watchOperation(operation.environment_id, operation.id).catch(exc => { error.value = detail(exc) })
  }
  await Promise.all(napari.environments.map(async (environment) => {
    try {
      lifecycle[environment.id] = (await napari.refreshEnvironmentStatus(environment.id)).status ?? environment.state
    } catch {
      lifecycle[environment.id] = environment.state
    }
  }))
}

function isPlatformManaged(environment: typeof napari.environments[number]): boolean {
  return environment.managed?.recipe.source === 'managed'
}

function ownershipLabel(environment: typeof napari.environments[number]): string {
  if (isPlatformManaged(environment)) return 'Managed by BioImageFlow'
  return environment.ownership === 'external' ? 'External' : 'Adopted installation'
}

function canLaunch(environment: typeof napari.environments[number]): boolean {
  return !['setup_needed', 'creating', 'failed', 'cancelled', 'removing', 'missing', 'replaced', 'probe_failed'].includes(environment.state)
}

function beginRuleEdit(item: typeof napari.filenameRules[number]) {
  editingRuleId.value = item.id
  ruleEdit.pattern = item.pattern
  ruleEdit.environmentId = item.environment_id
  ruleEdit.readerId = item.reader_id ?? ''
}

function cancelRuleEdit() {
  editingRuleId.value = null
}

async function saveRuleEdit(index: number) {
  const rules = napari.filenameRules.map((item, itemIndex) => itemIndex === index
    ? {
        ...item,
        pattern: ruleEdit.pattern,
        environment_id: ruleEdit.environmentId,
        reader_id: ruleEdit.readerId || null,
      }
    : item)
  await run(async () => {
    await napari.replaceFilenameRules(rules)
    editingRuleId.value = null
    preview.value = null
  })
}

function stateLabel(state: string): string {
  return state.replace(/_/g, ' ').replace(/^./, (value: string) => value.toUpperCase())
}

function commitFiji() {
  emit('update:field', { field: 'fiji_path', value: fijiPath.value.trim() || null })
}

async function browseFiji() {
  const path = await selectFolder('Choose the Fiji.app folder')
  if (path) {
    fijiPath.value = path
    commitFiji()
  }
}

function clearFiji() {
  fijiPath.value = ''
  commitFiji()
}

onMounted(() => {
  void loadRegistry().catch(exc => { error.value = detail(exc) })
})
</script>

<template>
  <div class="settings-section" data-testid="image-viewers-section">
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <section>
      <div class="heading">
        <h3>napari environments</h3>
      </div>
      <label>
        Default
        <select :value="napari.defaultEnvironmentId ?? ''" @change="setDefault">
          <option value="">Automatic</option>
          <option v-for="environment in napari.environments" :key="environment.id" :value="environment.id">
            {{ environment.name }}
          </option>
        </select>
      </label>
      <p v-if="napari.environments.length === 0" class="help-text">No napari environments are registered.</p>
      <article
        v-for="environment in napari.environments"
        :key="environment.id"
        class="environment"
        :data-testid="`napari-environment-card-${environment.id}`"
      >
        <div class="heading">
          <strong>{{ environment.name }}</strong>
          <span>napari {{ environment.inventory?.napari_version ?? 'unknown' }} · {{ stateLabel(lifecycle[environment.id] ?? environment.state) }}</span>
        </div>
        <details>
          <summary>Details</summary>
          <dl>
            <dt>Path</dt><dd><code>{{ environment.root }}</code></dd>
            <dt>Ownership</dt><dd>{{ ownershipLabel(environment) }}</dd>
            <dt>Kind</dt><dd>{{ environment.kind }}</dd>
            <dt>Recipe</dt><dd>{{ environment.managed?.recipe.preset ?? 'User managed' }}</dd>
            <dt>Python</dt><dd>{{ environment.inventory?.python_version ?? 'Not detected' }}</dd>
            <dt>Qt</dt><dd>{{ environment.inventory?.qt_distribution ? `${environment.inventory.qt_distribution} ${environment.inventory.qt_version ?? ''}` : 'Not detected' }}</dd>
            <dt>Lifecycle</dt><dd>{{ stateLabel(lifecycle[environment.id] ?? 'stopped') }}</dd>
            <dt>Last check</dt><dd>{{ environment.inventory?.probed_at ?? 'Never' }}</dd>
            <template v-if="environment.last_error">
              <dt>Last error</dt><dd class="error">{{ environment.last_error }}</dd>
            </template>
          </dl>
          <p v-if="lifecycle[environment.id] === 'restart_required'">Running viewer restart required to use the current installed packages.</p>
          <h4>Installed packages</h4>
          <p v-if="!environment.inventory?.distributions.length" class="help-text">No inventory is available.</p>
          <ul v-else class="packages">
            <li v-for="pkg in environment.inventory.distributions" :key="pkg.name">{{ pkg.name }} {{ pkg.version }}</li>
          </ul>
          <div class="actions">
            <Button label="Refresh" size="small" @click="refresh(environment.id)" />
            <Button label="Launch empty viewer" size="small" :disabled="!canLaunch(environment)" @click="launch(environment.id)" />
            <Button label="Rename" size="small" @click="rename(environment.id, environment.name)" />
            <Button v-if="!isPlatformManaged(environment) && (environment.state === 'missing' || environment.state === 'replaced')" label="Locate environment" size="small" @click="locate(environment.id)" />
            <Button v-if="!isPlatformManaged(environment)" label="Forget" severity="secondary" size="small" @click="forget(environment.id)" />
            <Button v-if="isPlatformManaged(environment)" label="Create modified copy" size="small" :disabled="environment.state !== 'ready' && environment.state !== 'drifted'" @click="prepareCopy(environment.id)" />
            <Button v-if="isPlatformManaged(environment) && ['failed', 'cancelled', 'setup_needed'].includes(environment.state)" label="Retry" size="small" @click="retry(environment.id)" />
            <Button v-if="isPlatformManaged(environment)" label="Delete managed installation" severity="danger" size="small" @click="removeManaged(environment.id)" />
          </div>
        </details>
      </article>
      <div v-for="operation in visibleOperations" :key="operation.id" class="operation">
        <span>{{ operation.message }}<small v-if="operation.error" class="error"> — {{ operation.error.detail }}</small></span>
        <ProgressBar :value="operation.progress" />
        <Button v-if="activeOperationStates.has(operation.state)" label="Cancel" text size="small" @click="cancel(operation.environment_id, operation.id)" />
      </div>
    </section>

    <section class="form">
      <h4>Add existing environment</h4>
      <InputText v-model="external.name" aria-label="Existing environment name" placeholder="Name" />
      <div class="path-row">
        <InputText v-model="external.path" aria-label="Environment path" placeholder="Environment folder or Python executable" />
        <Button label="Browse…" @click="browseEnvironment" />
      </div>
      <p class="help-text">Registration checks the environment but never installs or updates packages.</p>
      <Button label="Add existing" :disabled="!external.name.trim() || !external.path.trim()" @click="addExisting" />
    </section>
    <section class="form">
      <h4>{{ copyFromId ? 'Create modified copy' : 'Create environment' }}</h4>
      <label v-if="settingsPanel.napariCreatePrefills.value.length">
        Viewing requirement set
        <select v-model="setupGroupId">
          <option v-for="(group, index) in settingsPanel.napariCreatePrefills.value" :key="group.id" :value="group.id">
            Set {{ index + 1 }} — {{ group.members?.length ?? 0 }} output{{ group.members?.length === 1 ? '' : 's' }}
          </option>
        </select>
      </label>
      <p v-if="selectedSetupGroup" class="help-text">Prefilled from portable workflow requirements. Package availability on PyPI is not yet verified.</p>
      <InputText v-model="create.name" aria-label="Managed environment name" placeholder="Name" />
      <select v-model="create.preset" aria-label="Managed environment recipe">
        <option value="default">Default — napari 0.9.1 / PyQt6</option>
        <option value="legacy">Legacy smoke — napari 0.6.6 / PyQt5</option>
        <option value="advanced">Advanced</option>
      </select>
      <template v-if="create.preset === 'advanced'">
        <InputText v-model="create.python" aria-label="Python constraint" />
        <InputText v-model="create.napari" aria-label="napari version" />
        <select v-model="create.qt" aria-label="Qt distribution"><option>PyQt6</option><option>PyQt5</option></select>
      </template>
      <textarea v-model="create.packages" aria-label="Required Python distributions" placeholder="Required Python distributions, one per line" />
      <fieldset v-if="recommendedPackages.length">
        <legend>Optional recommended distributions</legend>
        <label v-for="requirement in recommendedPackages" :key="requirement">
          <input v-model="selectedRecommendations" type="checkbox" :value="requirement"> {{ requirement }}
        </label>
      </fieldset>
      <label v-if="selectedSetupGroup?.managed_create_prefill.requires_source_confirmation" class="source-confirmation">
        <input v-model="sourceConfirmed" type="checkbox">
        I confirmed these workflow-declared requirements are available from PyPI. Unknown or private packages must be installed manually in an external environment.
      </label>
      <p class="help-text">Managed recipes use Python 3.12 and install napari, Qt, and these reviewed requirements from PyPI.</p>
      <Button :label="copyFromId ? 'Create modified copy' : 'Create environment'" :disabled="!create.name.trim() || (Boolean(selectedSetupGroup?.managed_create_prefill.requires_source_confirmation) && !sourceConfirmed)" @click="createManaged()" />
    </section>

    <section>
      <h4>File opening rules <small>(first match wins)</small></h4>
      <p v-if="napari.filenameRules.length === 0" class="help-text">No filename rules. Compatible outputs use the global default and backend selection.</p>
      <div v-for="(item, index) in napari.filenameRules" :key="item.id" class="rule">
        <label><input type="checkbox" :checked="item.enabled" @change="toggleRule(index)"> Enabled</label>
        <template v-if="editingRuleId === item.id">
          <InputText v-model="ruleEdit.pattern" class="rule-value" aria-label="Edit filename pattern" />
          <select v-model="ruleEdit.environmentId" class="rule-environment" aria-label="Edit preferred environment">
            <option v-for="environment in napari.environments" :key="environment.id" :value="environment.id">{{ environment.name }}</option>
          </select>
          <InputText v-model="ruleEdit.readerId" class="rule-reader" aria-label="Edit optional reader ID" placeholder="Automatic" />
          <Button icon="pi pi-check" title="Save rule" text :disabled="!ruleEdit.pattern.trim() || !ruleEdit.environmentId" @click="saveRuleEdit(index)" />
          <Button icon="pi pi-times" title="Cancel rule editing" text @click="cancelRuleEdit" />
        </template>
        <template v-else>
          <code class="rule-value">{{ item.pattern }}</code>
          <span class="rule-environment">{{ napari.environments.find(env => env.id === item.environment_id)?.name }}</span>
          <span class="rule-reader">{{ item.reader_id ?? 'Automatic' }}</span>
          <Button icon="pi pi-pencil" title="Edit rule" text @click="beginRuleEdit(item)" />
          <Button icon="pi pi-arrow-up" title="Move rule up" text :disabled="index === 0" @click="moveRule(index, -1)" />
          <Button icon="pi pi-arrow-down" title="Move rule down" text :disabled="index === napari.filenameRules.length - 1" @click="moveRule(index, 1)" />
          <Button icon="pi pi-trash" title="Delete rule" text @click="deleteRule(index)" />
        </template>
      </div>
      <div class="form">
        <select v-model="rule.mode" aria-label="Filename rule mode"><option value="extension">Extension</option><option value="pattern">Filename pattern</option></select>
        <InputText v-model="rule.value" aria-label="Extension or filename pattern" :placeholder="rule.mode === 'extension' ? '.tif' : '*_labels.tif'" />
        <span v-if="extensionPreview">Saves as <code>{{ extensionPreview }}</code></span>
        <select v-model="rule.environmentId" aria-label="Preferred environment">
          <option value="">Environment</option>
          <option v-for="environment in napari.environments" :key="environment.id" :value="environment.id">{{ environment.name }}</option>
        </select>
        <InputText v-model="rule.readerId" aria-label="Optional reader ID" placeholder="Reader ID (optional)" />
        <Button label="Add rule" :disabled="!rule.value.trim() || !rule.environmentId" @click="addRule" />
      </div>
      <p v-if="catchAllWarning" class="warning">{{ catchAllWarning }}</p>
      <div class="path-row">
        <InputText v-model="testFilename" aria-label="Test filename" placeholder="Test filename" />
        <Button label="Test" :disabled="!testFilename.trim()" @click="testRules" />
      </div>
      <p v-if="preview">Matching rules: {{ previewMatches.join(', ') || 'none' }}. Winner: {{ napari.filenameRules.find(item => item.id === preview?.winner_rule_id)?.pattern ?? 'none' }}</p>
    </section>

    <section>
      <h3>Fiji</h3>
      <p class="help-text">Fiji is installed separately. <a :href="FIJI_DOWNLOAD_URL" target="_blank" rel="noopener noreferrer">Download Fiji</a></p>
      <div class="path-row">
        <InputText v-model="fijiPath" placeholder="/Applications/Fiji.app" data-testid="fiji-path-input" @blur="commitFiji" @keydown.enter="commitFiji" />
        <Button label="Browse…" data-testid="fiji-path-browse" @click="browseFiji" />
        <Button label="Clear" data-testid="fiji-path-clear" @click="clearFiji" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-section,
.form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.settings-section > section { border-top: 1px solid var(--bif-border-muted); padding-top: 0.75rem; }
.heading,
.actions,
.rule,
.path-row { display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem; }
.heading { justify-content: space-between; }
.environment { padding: 0.6rem; border: 1px solid var(--bif-border-muted); border-radius: 0.4rem; margin: 0.5rem 0; }
.environment dl { display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 0.75rem; }
.environment dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
.packages { max-height: 10rem; overflow: auto; }
.rule { display: grid; grid-template-columns: auto minmax(6rem, 1fr) minmax(6rem, 1fr) minmax(5rem, 1fr) repeat(4, auto); margin: 0.25rem 0; }
.rule-value { min-width: 0; overflow-wrap: anywhere; }
.path-row > :first-child { flex: 1; min-width: 10rem; }
.operation { display: grid; grid-template-columns: 1fr minmax(8rem, 1fr) auto; align-items: center; gap: 0.5rem; }
.help-text { color: var(--p-text-muted-color); }
.error { color: var(--p-red-600); }
.warning { color: var(--p-orange-600); }
.source-confirmation { display: flex; align-items: flex-start; gap: 0.5rem; }
h3,
h4,
p { margin: 0.25rem 0; }
textarea { min-height: 4rem; }
@media (max-width: 520px) {
  .rule { grid-template-columns: 1fr repeat(4, auto); }
  .rule-value,
  .rule-environment,
  .rule-reader { grid-column: 1 / -1; width: 100%; }
  .operation { grid-template-columns: 1fr; }
  .operation > button { justify-self: start; }
}
</style>
