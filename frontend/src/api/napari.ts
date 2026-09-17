import { api } from '@/api/client'
import type {
  NapariDefaultEnvironmentUpdate, NapariEnvironmentCreate, NapariEnvironmentList,
  NapariEnvironmentMutation, NapariEnvironmentStatus, NapariEnvironmentUpdate,
  NapariFilenamePreview, NapariFilenameRuleCreate, NapariFilenameRuleMutation,
  NapariFilenameRulesReplace, NapariManagedEnvironmentCopy, NapariManagedEnvironmentCreate,
  NapariManagedOperationMutation, NapariManagedRetryRequest, NapariOpenRequest,
  NapariProbeRequest, NapariResolveRequest, NapariResolveResponse, NapariStatus,
  NapariViewingReadinessResponse, ViewingRequirementsManifestInput,
  ViewingRequirementsManifestOutput,
  ViewerFavoriteToggleRequest, ViewerPreferencesSnapshot,
} from '@/api/types'

export async function openInNapari(requestOrPaths: NapariOpenRequest | string[], clearLayers = false): Promise<void> {
  const request: NapariOpenRequest = Array.isArray(requestOrPaths)
    ? { paths: requestOrPaths, clear_layers: clearLayers }
    : requestOrPaths
  await api.post('/api/v1/napari/open', request)
}

export async function getNapariStatus(environmentId?: string): Promise<NapariStatus | NapariEnvironmentStatus> {
  return environmentId
    ? (await api.get('/api/v1/napari/status', { params: { environment_id: environmentId } })).data
    : (await api.get('/api/v1/napari/status')).data
}

export async function shutdownNapari(environmentId?: string): Promise<void> {
  if (environmentId) await api.post('/api/v1/napari/shutdown', undefined, { params: { environment_id: environmentId } })
  else await api.post('/api/v1/napari/shutdown')
}

export async function launchNapariEnvironment(environmentId: string): Promise<void> {
  await api.post('/api/v1/napari/launch', { environment_id: environmentId })
}

export async function listNapariEnvironments(): Promise<NapariEnvironmentList> {
  return (await api.get('/api/v1/napari/environments')).data
}

export async function registerNapariEnvironment(request: NapariEnvironmentCreate): Promise<NapariEnvironmentMutation> {
  return (await api.post('/api/v1/napari/environments', request)).data
}

export async function updateNapariEnvironment(id: string, request: NapariEnvironmentUpdate): Promise<NapariEnvironmentMutation> {
  return (await api.patch(`/api/v1/napari/environments/${id}`, request)).data
}

export async function forgetNapariEnvironment(id: string, expectedRevision: number): Promise<NapariEnvironmentList> {
  return (await api.delete(`/api/v1/napari/environments/${id}`, { params: { expected_revision: expectedRevision } })).data
}

export async function probeNapariEnvironment(id: string, request: NapariProbeRequest): Promise<NapariEnvironmentMutation> {
  return (await api.post(`/api/v1/napari/environments/${id}/probe`, request)).data
}

export async function setDefaultNapariEnvironment(request: NapariDefaultEnvironmentUpdate): Promise<NapariEnvironmentList> {
  return (await api.put('/api/v1/napari/environment-settings/default', request)).data
}

export async function addNapariFilenameRule(request: NapariFilenameRuleCreate): Promise<NapariFilenameRuleMutation> {
  return (await api.post('/api/v1/napari/environment-settings/filename-rules', request)).data
}

export async function replaceNapariFilenameRules(request: NapariFilenameRulesReplace): Promise<NapariEnvironmentList> {
  return (await api.put('/api/v1/napari/environment-settings/filename-rules', request)).data
}

export async function previewNapariFilename(filename: string): Promise<NapariFilenamePreview> {
  return (await api.post('/api/v1/napari/environment-settings/filename-rules/preview', { filename })).data
}

export async function createManagedNapariEnvironment(request: NapariManagedEnvironmentCreate): Promise<NapariManagedOperationMutation> {
  return (await api.post('/api/v1/napari/environments/managed', request)).data
}

export async function copyManagedNapariEnvironment(id: string, request: NapariManagedEnvironmentCopy): Promise<NapariManagedOperationMutation> {
  return (await api.post(`/api/v1/napari/environments/${id}/copy`, request)).data
}

export async function retryManagedNapariEnvironment(id: string, request: NapariManagedRetryRequest): Promise<NapariManagedOperationMutation> {
  return (await api.post(`/api/v1/napari/environments/${id}/retry`, request)).data
}

export async function getManagedNapariOperation(environmentId: string, operationId: string): Promise<NapariManagedOperationMutation> {
  return (await api.get(`/api/v1/napari/environments/${environmentId}/operations/${operationId}`)).data
}

export async function cancelManagedNapariOperation(environmentId: string, operationId: string): Promise<NapariManagedOperationMutation> {
  return (await api.post(`/api/v1/napari/environments/${environmentId}/operations/${operationId}/cancel`)).data
}

export async function deleteManagedNapariEnvironment(id: string, expectedRevision: number): Promise<NapariManagedOperationMutation> {
  return (await api.delete(`/api/v1/napari/environments/managed/${id}`, { params: { expected_revision: expectedRevision } })).data
}

export async function resolveNapariEnvironment(request: NapariResolveRequest): Promise<NapariResolveResponse> {
  return (await api.post('/api/v1/napari/resolve', request)).data
}

export async function getNapariViewingReadiness(manifest: ViewingRequirementsManifestInput): Promise<NapariViewingReadinessResponse> {
  return (await api.post('/api/v1/napari/viewing-readiness', manifest)).data
}

export async function getWorkflowViewingRequirements(workflowId: string): Promise<ViewingRequirementsManifestOutput> {
  const encoded = workflowId.split('/').map(encodeURIComponent).join('/')
  return (await api.get(`/api/v1/workflows/${encoded}/viewing-readiness`)).data
}

export async function getViewerPreferences(): Promise<ViewerPreferencesSnapshot> {
  return (await api.get('/api/v1/napari/viewer-preferences')).data
}

export async function toggleViewerFavorite(request: ViewerFavoriteToggleRequest): Promise<ViewerPreferencesSnapshot> {
  return (await api.post('/api/v1/napari/viewer-preferences/favorite/toggle', request)).data
}
