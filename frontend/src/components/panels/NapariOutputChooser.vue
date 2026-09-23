<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import { useToast } from 'primevue/usetoast'
import {
  getViewerPreferences,
  listNapariEnvironments,
  resolveNapariEnvironment,
  toggleViewerFavorite,
} from '@/api/napari'
import type {
  NapariEnvironment,
  NapariEnvironmentCandidate,
  NapariResolveResponse,
  ResultArtifactIdentity,
  ViewerFavorite,
  ViewerPreferencesSnapshot,
} from '@/api/types'
import { useSettingsPanel } from '@/composables/useSettingsPanel'
import { useNapariStore } from '@/stores/napari'

const props = defineProps<{
  workflowId: string | null
  identityGeneration: number | null
  nodePath: string[]
  outputKey: string
  outputName: string
  resultIdentity: ResultArtifactIdentity | null
  row: number
  path: string
}>()

const popover = ref<InstanceType<typeof Popover> | null>(null)
const resolution = ref<NapariResolveResponse | null>(null)
const environments = ref<NapariEnvironment[]>([])
const preferences = ref<ViewerPreferencesSnapshot | null>(null)
const resolving = ref(false)
const loadingMenu = ref(false)
const favoritePending = ref(false)
const napari = useNapariStore()
const settingsPanel = useSettingsPanel()
let toast: ReturnType<typeof useToast> | null = null
try {
  toast = useToast()
} catch {
  toast = null
}
let resolveRequest = 0

const identityToken = computed(() => JSON.stringify([
  props.workflowId,
  props.identityGeneration,
  props.nodePath,
  props.outputKey,
  props.resultIdentity,
  props.row,
]))
const outputSlug = computed(() => props.outputKey.replace(/[^a-zA-Z0-9_-]/g, '_') || '_')
const canResolve = computed(() => Boolean(
  props.workflowId
  && props.identityGeneration !== null
  && props.nodePath.length > 0
  && props.outputKey
  && props.resultIdentity,
))
const effectiveCandidate = computed(() => candidateFor(
  resolution.value?.effective_environment_id ?? null,
))
const favoriteCandidate = computed(() => (
  resolution.value?.candidates.find(candidate => candidate.preference === 'favorite') ?? null
))
const favoriteUnavailable = computed(() => (
  favoriteCandidate.value !== null
  && favoriteCandidate.value.environment_id !== resolution.value?.effective_environment_id
))
const primaryLabel = computed(() => effectiveCandidate.value
  ? `Open in ${effectiveCandidate.value.name}`
  : canResolve.value ? 'Choose a napari environment' : 'Result identity unavailable')
const primaryTitle = computed(() => {
  if (!canResolve.value) return 'Refresh output data before opening this result in napari'
  if (!resolution.value) return 'Checking which napari environment can open this result'
  if (!effectiveCandidate.value) return resolution.value.effective_reason
  const savedWarning = favoriteUnavailable.value
    ? ` Saved preference unavailable: ${favoriteCandidate.value?.reason}.`
    : ''
  return `${primaryLabel.value}.${savedWarning}`
})

function errorDetail(error: unknown, fallback: string): string {
  const candidate = error as {
    message?: string
    response?: { data?: { detail?: string | { detail?: string } } }
  }
  const detail = candidate.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail.detail === 'string') return detail.detail
  return candidate.message ?? fallback
}

function showError(error: unknown, fallback: string): void {
  toast?.add({
    severity: 'error',
    summary: 'Napari action failed',
    detail: errorDetail(error, fallback),
    life: 5000,
  })
}

function candidateFor(environmentId: string | null): NapariEnvironmentCandidate | null {
  if (environmentId === null) return null
  return resolution.value?.candidates.find(
    candidate => candidate.environment_id === environmentId,
  ) ?? null
}

function environmentFor(environmentId: string): NapariEnvironment | null {
  return environments.value.find(environment => environment.id === environmentId) ?? null
}

function napariVersion(environmentId: string): string {
  return environmentFor(environmentId)?.inventory?.napari_version ?? 'version not detected'
}

function keysMatch(favorite: ViewerFavorite): boolean {
  const key = resolution.value?.preference_key
  if (!key || favorite.key.kind !== key.kind) return false
  return favorite.key.workspace_id === key.workspace_id
    && favorite.key.workflow_id === key.workflow_id
    && favorite.key.identity_generation === key.identity_generation
    && favorite.key.output_key === key.output_key
    && favorite.key.node_path.length === key.node_path.length
    && favorite.key.node_path.every((part, index) => part === key.node_path[index])
}

function favoriteEnvironmentId(): string | null {
  return preferences.value?.favorites?.find(keysMatch)?.environment_id
    ?? favoriteCandidate.value?.environment_id
    ?? null
}

function isFavorite(environmentId: string): boolean {
  return favoriteEnvironmentId() === environmentId
}

async function resolveSelection(): Promise<NapariResolveResponse | null> {
  if (!canResolve.value || !props.workflowId || props.identityGeneration === null || !props.resultIdentity) {
    resolution.value = null
    return null
  }
  const requestId = ++resolveRequest
  const token = identityToken.value
  resolving.value = true
  try {
    const response = await resolveNapariEnvironment({
      workflow_id: props.workflowId,
      identity_generation: props.identityGeneration,
      node_path: [...props.nodePath],
      output_key: props.outputKey,
      result_identity: { ...props.resultIdentity },
      row: props.row,
    })
    if (requestId === resolveRequest && token === identityToken.value) {
      resolution.value = response
      return response
    }
    return null
  } catch (error) {
    if (requestId === resolveRequest) resolution.value = null
    showError(error, 'Could not resolve a napari environment')
    return null
  } finally {
    if (requestId === resolveRequest) resolving.value = false
  }
}

watch(identityToken, () => {
  preferences.value = null
  void resolveSelection()
}, { immediate: true })

async function loadMenu(): Promise<void> {
  loadingMenu.value = true
  try {
    const [registry, snapshot] = await Promise.all([
      listNapariEnvironments(),
      getViewerPreferences(),
      resolution.value ? Promise.resolve(resolution.value) : resolveSelection(),
    ])
    environments.value = registry.environments ?? []
    preferences.value = snapshot
  } catch (error) {
    showError(error, 'Could not load napari environments')
  } finally {
    loadingMenu.value = false
  }
}

function toggleMenu(event: Event): void {
  popover.value?.toggle(event)
  void loadMenu()
}

async function openCandidate(
  candidate: NapariEnvironmentCandidate,
  event?: MouseEvent,
  replace = false,
): Promise<void> {
  if (!props.resultIdentity || candidate.status === 'unavailable') return
  try {
    await napari.open({
      paths: [props.path],
      clear_layers: replace || Boolean(event?.ctrlKey || event?.metaKey),
      environment_id: candidate.environment_id,
      reader_id: candidate.reader_id ?? null,
      node_id: props.resultIdentity.node_key,
      row: props.row,
      col: props.outputKey,
      workflow_name: props.workflowId,
      result_identity: { ...props.resultIdentity },
    })
  } catch (error) {
    showError(error, 'Could not open the selected result in napari')
  }
}

async function primaryOpen(event: MouseEvent): Promise<void> {
  const response = resolution.value ?? await resolveSelection()
  const candidate = response?.effective_environment_id
    ? candidateFor(response.effective_environment_id)
    : null
  if (!candidate) {
    toggleMenu(event)
    return
  }
  await openCandidate(candidate, event)
}

async function updateFavorite(environmentId: string): Promise<void> {
  if (!resolution.value || favoritePending.value) return
  const candidate = candidateFor(environmentId)
  if (!isFavorite(environmentId) && candidate?.status !== 'compatible') return
  favoritePending.value = true
  try {
    if (!preferences.value) preferences.value = await getViewerPreferences()
    preferences.value = await toggleViewerFavorite({
      key: resolution.value.preference_key,
      environment_id: environmentId,
      expected_revision: preferences.value.revision,
    })
    await resolveSelection()
  } catch (error) {
    const status = (error as { response?: { status?: number } }).response?.status
    if (status === 409) {
      preferences.value = await getViewerPreferences().catch(() => preferences.value)
      await resolveSelection()
    }
    showError(error, status === 409
      ? 'The favorite changed in another window. The current preference has been reloaded.'
      : 'Could not update the favorite environment')
  } finally {
    favoritePending.value = false
  }
}

function manageEnvironments(): void {
  settingsPanel.open('viewers')
  popover.value?.hide()
}

function createEnvironment(): void {
  window.dispatchEvent(new CustomEvent('bioimageflow:napari-environment-setup', {
    detail: {
      viewer: resolution.value?.viewer ?? null,
      workflowId: resolution.value?.workflow_id ?? props.workflowId,
      nodePath: resolution.value?.node_path ?? props.nodePath,
      outputKey: resolution.value?.output_key ?? props.outputKey,
    },
  }))
  manageEnvironments()
}
</script>

<template>
  <div class="napari-output-chooser">
    <Button
      icon="pi pi-image"
      text
      size="small"
      :title="primaryTitle"
      :aria-label="primaryLabel"
      :disabled="!canResolve || resolving || napari.environmentState(resolution?.effective_environment_id).pending"
      :data-testid="`open-napari-${row}-${outputSlug}`"
      @click.stop="primaryOpen"
    />
    <Button
      icon="pi pi-chevron-down"
      text
      size="small"
      title="Choose napari environment"
      aria-label="Choose napari environment"
      :disabled="!canResolve"
      :data-testid="`choose-napari-${row}-${outputSlug}`"
      @click.stop="toggleMenu"
    />
    <Popover ref="popover">
      <section class="napari-picker" data-testid="napari-environment-picker" aria-label="Napari environments">
        <header>
          <strong>{{ outputName }}</strong>
          <div class="napari-picker__identity">{{ nodePath.join(' › ') }} › {{ outputKey }}</div>
        </header>
        <p v-if="resolution" class="napari-picker__effective">
          <template v-if="effectiveCandidate">Will open in {{ effectiveCandidate.name }}</template>
          <template v-else>{{ resolution.effective_reason }}</template>
        </p>
        <p v-if="favoriteUnavailable" class="napari-picker__warning" role="status">
          Saved preference unavailable: {{ favoriteCandidate?.reason }}.
          Using {{ effectiveCandidate?.name ?? 'no fallback environment' }}.
        </p>
        <p v-if="loadingMenu || resolving" role="status">Checking environments…</p>
        <div v-else-if="resolution?.candidates.length" class="napari-picker__list">
          <article
            v-for="candidate in resolution.candidates"
            :key="candidate.environment_id"
            class="napari-picker__row"
            :data-testid="`napari-environment-${candidate.environment_id}`"
          >
            <div class="napari-picker__environment">
              <strong>{{ candidate.name }}</strong>
              <span>{{ napariVersion(candidate.environment_id) }}</span>
            </div>
            <div class="napari-picker__status">
              <span :class="`napari-picker__indicator napari-picker__indicator--${candidate.status}`" aria-hidden="true" />
              <span>{{ candidate.label }}</span>
              <small v-if="candidate.status !== 'compatible' && !candidate.issues?.length">{{ candidate.reason }}</small>
              <small v-for="issue in candidate.issues" :key="`${issue.code}:${issue.distribution ?? ''}`">{{ issue.detail }}</small>
            </div>
            <Button
              :label="candidate.status === 'compatible' ? 'Open once' : 'Try opening anyway'"
              text
              size="small"
              :disabled="candidate.status === 'unavailable' || napari.environmentState(candidate.environment_id).pending"
              :aria-label="`${candidate.status === 'compatible' ? 'Open once in' : 'Try opening anyway in'} ${candidate.name}`"
              @click="openCandidate(candidate, $event)"
            />
            <Button
              :icon="isFavorite(candidate.environment_id) ? 'pi pi-star-fill' : 'pi pi-star'"
              text
              size="small"
              :aria-label="isFavorite(candidate.environment_id) ? 'Unset favorite for this output' : `Set ${candidate.name} as favorite for this output`"
              :title="isFavorite(candidate.environment_id) ? 'Unset favorite for this output' : 'Set favorite for this output'"
              :aria-pressed="isFavorite(candidate.environment_id)"
              :disabled="favoritePending || (!isFavorite(candidate.environment_id) && candidate.status !== 'compatible')"
              @click="updateFavorite(candidate.environment_id)"
            />
          </article>
        </div>
        <p v-else-if="resolution" class="napari-picker__warning">No registered napari environments are available.</p>
        <footer class="napari-picker__actions">
          <Button
            v-if="effectiveCandidate"
            label="Clear layers, then open"
            text
            size="small"
            :title="`Clear all layers in ${effectiveCandidate.name}, then open ${outputName}`"
            @click="openCandidate(effectiveCandidate, $event, true)"
          />
          <Button label="Manage environments" link size="small" @click="manageEnvironments" />
          <Button
            v-if="resolution?.viewer?.napari"
            label="Create environment for these requirements"
            text
            size="small"
            @click="createEnvironment"
          />
        </footer>
      </section>
    </Popover>
  </div>
</template>

<style scoped>
.napari-output-chooser {
  display: inline-flex;
}

.napari-picker {
  display: grid;
  gap: 0.75rem;
  min-width: min(38rem, 82vw);
  max-width: min(48rem, 90vw);
}

.napari-picker__identity,
.napari-picker__environment span,
.napari-picker__status small {
  color: var(--p-text-muted-color);
  font-size: 0.78rem;
}

.napari-picker__effective,
.napari-picker__warning {
  margin: 0;
}

.napari-picker__warning {
  color: var(--p-orange-600);
}

.napari-picker__list {
  display: grid;
  gap: 0.25rem;
}

.napari-picker__row {
  display: grid;
  grid-template-columns: minmax(8rem, 1fr) minmax(12rem, 2fr) auto auto;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem;
  border-radius: var(--p-border-radius-md);
}

.napari-picker__row:hover {
  background: var(--bif-surface-hover);
}

.napari-picker__environment,
.napari-picker__status {
  display: grid;
}

.napari-picker__status {
  grid-template-columns: auto 1fr;
  column-gap: 0.4rem;
}

.napari-picker__status small {
  grid-column: 2;
}

.napari-picker__indicator {
  width: 0.65rem;
  height: 0.65rem;
  margin-top: 0.3rem;
  border-radius: 50%;
  background: var(--p-text-muted-color);
}

.napari-picker__indicator--compatible {
  background: var(--p-green-500);
}

.napari-picker__indicator--incompatible {
  background: var(--p-orange-500);
}

.napari-picker__indicator--unavailable {
  background: var(--p-red-500);
}

.napari-picker__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

@media (max-width: 700px) {
  .napari-picker__row {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .napari-picker__status {
    grid-column: 1 / -1;
    grid-row: 2;
  }
}
</style>
