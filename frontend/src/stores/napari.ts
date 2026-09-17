import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  NapariDefaultEnvironmentUpdate, NapariEnvironment, NapariEnvironmentCreate,
  NapariEnvironmentList, NapariEnvironmentMutation, NapariEnvironmentOperation,
  NapariEnvironmentUpdate, NapariFilenamePreview, NapariFilenameRuleCreate,
  NapariFilenameRuleMutation, NapariFilenameRulesReplace, NapariManagedEnvironmentCopy,
  NapariManagedEnvironmentCreate, NapariManagedOperationMutation, NapariOpenRequest,
  NapariResolveRequest, NapariResolveResponse,
  NapariViewingReadinessResponse, ViewerFavoriteToggleRequest,
  ViewerPreferencesSnapshot, ViewingRequirementsManifestInput,
} from '@/api/types'
import * as napariApi from '@/api/napari'

export type NapariOpenPayload = NapariOpenRequest
type LaunchPhase = 'installing' | 'opening'
export interface EnvironmentRequestState {
  pending: boolean
  phase: LaunchPhase | null
  requestId: string | null
  status: string | null
  detail: string | null
}

const terminalOperations = new Set(['completed', 'failed', 'cancelled'])

export const useNapariStore = defineStore('napari', () => {
  const requestPending = ref(false) // legacy aggregate compatibility
  const launchPhase = ref<LaunchPhase>('opening')
  const loggerActivationRequest = ref(0)
  const revision = ref(0)
  const environments = ref<NapariEnvironment[]>([])
  const defaultEnvironmentId = ref<string | null>(null)
  const filenameRules = ref<NonNullable<NapariEnvironmentList['filename_rules']>>([])
  const operations = ref<NapariEnvironmentOperation[]>([])
  const preferences = ref<ViewerPreferencesSnapshot | null>(null)
  const environmentRequests = reactive<Record<string, EnvironmentRequestState>>({})
  const resolutions = reactive<Record<string, NapariResolveResponse>>({})
  const viewingReadiness = ref<NapariViewingReadinessResponse | null>(null)
  const viewingManifest = ref<ViewingRequirementsManifestInput | null>(null)
  const viewingWorkflowId = ref<string | null>(null)
  const viewingReadinessPending = ref(false)
  const viewingReadinessError = ref<string | null>(null)
  const operationWatchPromises = new Map<string, Promise<NapariEnvironmentOperation>>()
  let viewingReadinessRequest = 0
  let viewingManifestSourceRequest = 0

  const phase = computed<LaunchPhase | null>(() => requestPending.value ? launchPhase.value : null)

  function environmentState(id: string | null | undefined): EnvironmentRequestState {
    const key = id ?? 'legacy'
    return environmentRequests[key] ??= {
      pending: false, phase: null, requestId: null, status: null, detail: null,
    }
  }

  function syncAggregate(): void {
    requestPending.value = Object.values(environmentRequests).some(state => state.pending)
    const pending = Object.values(environmentRequests).find(state => state.pending && state.phase)
    if (pending?.phase) launchPhase.value = pending.phase
  }

  function applySnapshot(snapshot: NapariEnvironmentList): void {
    revision.value = snapshot.revision
    environments.value = snapshot.environments ?? []
    defaultEnvironmentId.value = snapshot.default_environment_id ?? null
    filenameRules.value = snapshot.filename_rules ?? []
    operations.value = snapshot.operations ?? []
  }

  function applyEnvironmentMutation(mutation: NapariEnvironmentMutation): void {
    revision.value = mutation.revision
    const index = environments.value.findIndex(item => item.id === mutation.environment.id)
    if (index >= 0) environments.value[index] = mutation.environment
    else environments.value.push(mutation.environment)
  }

  function applyRuleMutation(mutation: NapariFilenameRuleMutation): void {
    revision.value = mutation.revision
    filenameRules.value.push(mutation.rule)
  }

  function applyOperationMutation(mutation: NapariManagedOperationMutation): void {
    revision.value = mutation.revision
    if (mutation.environment) {
      const index = environments.value.findIndex(item => item.id === mutation.environment!.id)
      if (index >= 0) environments.value[index] = mutation.environment
      else environments.value.push(mutation.environment)
    }
    const index = operations.value.findIndex(item => item.id === mutation.operation.id)
    if (index >= 0) operations.value[index] = mutation.operation
    else operations.value.push(mutation.operation)
  }

  function applyEnvironmentStatus(payload: Record<string, unknown>): void {
    const environmentId = typeof payload.environment_id === 'string' ? payload.environment_id : 'legacy'
    if (environmentId === 'legacy' && payload.env_name !== 'napari') return
    const status = typeof payload.status === 'string' ? payload.status : null
    const state = environmentState(environmentId)
    state.status = status
    state.detail = typeof payload.detail === 'string' ? payload.detail : null
    const requestId = typeof payload.request_id === 'string' ? payload.request_id : null
    if (requestId) state.requestId = requestId
    if (status === 'creating' || status === 'opening') {
      state.pending = true
      state.phase = status === 'creating' ? 'installing' : 'opening'
      launchPhase.value = state.phase
      loggerActivationRequest.value += 1
    } else if (status === 'running' || status === 'failed' || status === 'stopped' || status === 'restart_required') {
      if (!requestId || !state.requestId || requestId === state.requestId) {
        state.pending = false
        state.phase = null
      }
    }
    syncAggregate()
  }

  async function open(payload: NapariOpenPayload): Promise<void> {
    const state = environmentState(payload.environment_id)
    if (state.pending) return
    const requestId = crypto.randomUUID?.() ?? `${Date.now()}-${Math.random()}`
    state.pending = true
    state.phase = 'opening'
    state.requestId = requestId
    launchPhase.value = 'opening'
    syncAggregate()
    try {
      await napariApi.openInNapari(payload)
    } finally {
      if (state.requestId === requestId) {
        state.pending = false
        state.phase = null
        state.requestId = null
      }
      syncAggregate()
    }
  }

  async function fetchRegistry(): Promise<void> {
    applySnapshot(await napariApi.listNapariEnvironments())
  }

  async function registerEnvironment(request: Omit<NapariEnvironmentCreate, 'expected_revision'>): Promise<void> {
    applyEnvironmentMutation(await napariApi.registerNapariEnvironment({
      ...request, expected_revision: revision.value,
    }))
    await refreshViewingReadiness()
  }

  async function updateEnvironment(id: string, request: Omit<NapariEnvironmentUpdate, 'expected_revision'>): Promise<void> {
    applyEnvironmentMutation(await napariApi.updateNapariEnvironment(id, {
      ...request, expected_revision: revision.value,
    }))
    await refreshViewingReadiness()
  }

  async function forgetEnvironment(id: string): Promise<void> {
    applySnapshot(await napariApi.forgetNapariEnvironment(id, revision.value))
    await refreshViewingReadiness()
  }

  async function probeEnvironment(id: string): Promise<void> {
    try {
      applyEnvironmentMutation(await napariApi.probeNapariEnvironment(id, {
        expected_revision: revision.value,
      }))
      await refreshViewingReadiness()
    } catch (error) {
      // Failed probes persist an actionable probe_failed state before returning
      // their error, so refresh the registry without hiding that error.
      await fetchRegistry().catch(() => undefined)
      throw error
    }
  }

  async function launchEmpty(id: string): Promise<void> {
    await napariApi.launchNapariEnvironment(id)
    await refreshEnvironmentStatus(id)
  }

  async function refreshEnvironmentStatus(id: string): Promise<EnvironmentRequestState> {
    const status = await napariApi.getNapariStatus(id)
    applyEnvironmentStatus(status as unknown as Record<string, unknown>)
    return environmentState(id)
  }

  async function setDefaultEnvironment(environmentId: NapariDefaultEnvironmentUpdate['environment_id']): Promise<void> {
    applySnapshot(await napariApi.setDefaultNapariEnvironment({
      environment_id: environmentId, expected_revision: revision.value,
    }))
    await refreshViewingReadiness()
  }

  async function addFilenameRule(request: Omit<NapariFilenameRuleCreate, 'expected_revision'>): Promise<void> {
    applyRuleMutation(await napariApi.addNapariFilenameRule({
      ...request, expected_revision: revision.value,
    }))
    await refreshViewingReadiness()
  }

  async function replaceFilenameRules(rules: NapariFilenameRulesReplace['rules']): Promise<void> {
    applySnapshot(await napariApi.replaceNapariFilenameRules({
      rules, expected_revision: revision.value,
    }))
    await refreshViewingReadiness()
  }

  function previewFilename(filename: string): Promise<NapariFilenamePreview> {
    return napariApi.previewNapariFilename(filename)
  }

  async function createManagedEnvironment(request: Omit<NapariManagedEnvironmentCreate, 'expected_revision'>): Promise<NapariEnvironmentOperation> {
    const mutation = await napariApi.createManagedNapariEnvironment({
      ...request, expected_revision: revision.value,
    })
    applyOperationMutation(mutation)
    await refreshViewingReadiness()
    return mutation.operation
  }

  async function copyManagedEnvironment(id: string, request: Omit<NapariManagedEnvironmentCopy, 'expected_revision'>): Promise<NapariEnvironmentOperation> {
    const mutation = await napariApi.copyManagedNapariEnvironment(id, {
      ...request, expected_revision: revision.value,
    })
    applyOperationMutation(mutation)
    await refreshViewingReadiness()
    return mutation.operation
  }

  async function retryManagedEnvironment(id: string): Promise<NapariEnvironmentOperation> {
    const mutation = await napariApi.retryManagedNapariEnvironment(id, {
      expected_revision: revision.value,
    })
    applyOperationMutation(mutation)
    await refreshViewingReadiness()
    return mutation.operation
  }

  async function cancelManagedOperation(environmentId: string, operationId: string): Promise<void> {
    applyOperationMutation(await napariApi.cancelManagedNapariOperation(environmentId, operationId))
    await refreshViewingReadiness()
  }

  async function deleteManagedEnvironment(id: string): Promise<NapariEnvironmentOperation> {
    const mutation = await napariApi.deleteManagedNapariEnvironment(id, revision.value)
    applyOperationMutation(mutation)
    await refreshViewingReadiness()
    return mutation.operation
  }

  async function resolve(key: string, request: NapariResolveRequest): Promise<NapariResolveResponse> {
    const response = await napariApi.resolveNapariEnvironment(request)
    resolutions[key] = response
    return response
  }

  async function fetchPreferences(): Promise<void> {
    preferences.value = await napariApi.getViewerPreferences()
  }

  async function evaluateManifest(
    manifest: ViewingRequirementsManifestInput,
    workflowId: string | null,
  ): Promise<NapariViewingReadinessResponse> {
    const request = ++viewingReadinessRequest
    viewingManifest.value = manifest
    viewingWorkflowId.value = workflowId
    viewingReadinessPending.value = true
    try {
      const response = await napariApi.getNapariViewingReadiness(manifest)
      if (request === viewingReadinessRequest) {
        viewingReadiness.value = response
        viewingReadinessError.value = null
      }
      return response
    } catch (error) {
      if (request === viewingReadinessRequest) {
        viewingReadinessError.value = error instanceof Error ? error.message : String(error)
      }
      throw error
    } finally {
      if (request === viewingReadinessRequest) viewingReadinessPending.value = false
    }
  }

  function evaluateViewingReadiness(
    manifest: ViewingRequirementsManifestInput,
    workflowId: string | null = null,
  ): Promise<NapariViewingReadinessResponse> {
    viewingManifestSourceRequest += 1
    return evaluateManifest(manifest, workflowId)
  }

  async function evaluateWorkflowReadiness(workflowId: string): Promise<NapariViewingReadinessResponse> {
    const request = ++viewingManifestSourceRequest
    viewingReadinessPending.value = true
    try {
      const manifest = await napariApi.getWorkflowViewingRequirements(workflowId)
      if (request !== viewingManifestSourceRequest) {
        throw new Error('Viewing requirements request was superseded by a newer workflow')
      }
      return await evaluateManifest(manifest, workflowId)
    } catch (error) {
      if (request === viewingManifestSourceRequest) {
        viewingReadinessError.value = error instanceof Error ? error.message : String(error)
      }
      throw error
    } finally {
      if (request === viewingManifestSourceRequest) viewingReadinessPending.value = false
    }
  }

  async function refreshViewingReadiness(): Promise<NapariViewingReadinessResponse | null> {
    if (!viewingManifest.value) return null
    try {
      return viewingWorkflowId.value
        ? await evaluateWorkflowReadiness(viewingWorkflowId.value)
        : await evaluateViewingReadiness(viewingManifest.value)
    } catch {
      return null
    }
  }

  async function toggleFavorite(request: Omit<ViewerFavoriteToggleRequest, 'expected_revision'>): Promise<void> {
    if (!preferences.value) await fetchPreferences()
    preferences.value = await napariApi.toggleViewerFavorite({
      ...request,
      expected_revision: preferences.value?.revision ?? 0,
    })
  }

  async function pollOperation(environmentId: string, operationId: string): Promise<NapariEnvironmentOperation> {
    const result = await napariApi.getManagedNapariOperation(environmentId, operationId)
    applyOperationMutation(result)
    return result.operation
  }

  function watchOperation(environmentId: string, operationId: string): Promise<NapariEnvironmentOperation> {
    const existing = operationWatchPromises.get(operationId)
    if (existing) return existing
    const watcher = (async () => {
      let operation = await pollOperation(environmentId, operationId)
      while (!terminalOperations.has(operation.state)) {
        await new Promise(resolve => setTimeout(resolve, 1000))
        operation = await pollOperation(environmentId, operationId)
      }
      await fetchRegistry()
      await refreshViewingReadiness()
      return operation
    })().finally(() => operationWatchPromises.delete(operationId))
    operationWatchPromises.set(operationId, watcher)
    return watcher
  }

  return {
    requestPending, phase, loggerActivationRequest, revision, environments,
    defaultEnvironmentId, filenameRules, operations, preferences, environmentRequests,
    resolutions, viewingReadiness, viewingManifest, viewingWorkflowId, viewingReadinessPending,
    viewingReadinessError, environmentState, applyEnvironmentStatus, applySnapshot, open,
    registerEnvironment, updateEnvironment, forgetEnvironment, probeEnvironment, launchEmpty,
    refreshEnvironmentStatus,
    setDefaultEnvironment, addFilenameRule, replaceFilenameRules, previewFilename,
    createManagedEnvironment, copyManagedEnvironment, retryManagedEnvironment,
    cancelManagedOperation, deleteManagedEnvironment,
    fetchRegistry, resolve, fetchPreferences, evaluateViewingReadiness, evaluateWorkflowReadiness,
    refreshViewingReadiness, toggleFavorite,
    pollOperation, watchOperation,
  }
})
