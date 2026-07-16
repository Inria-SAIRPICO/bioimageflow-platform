import {
  computed,
  ref,
  watch,
  type ComputedRef,
  type InjectionKey,
  type Ref,
} from 'vue'

import type { NodeStatus, ProgressInfo, ValidationResult } from '@/api/types'
import {
  canvasIdFromPanelId,
  canvasSessionRegistry,
  type CanvasId,
  type CanvasSessionDescriptor,
  type DisposableCanvasResource,
} from '@/sessions/canvasSessionRegistry'
import {
  projectNodeStatus,
  type ProjectedNodeStatus,
} from '@/sessions/nodeStatusProjection'
import { useExecutionStore } from '@/stores/execution'
import { useCanvasPersistence } from './useCanvasPersistence'
import { useGraphSync } from './useGraphSync'

const CANVAS_STATUS_RESOURCE = 'canvas-status-projection'
const LEGACY_CANVAS_ID = canvasIdFromPanelId('__legacy_status_projection__')

export interface CanvasStatusNode {
  readonly id: string
  readonly enabled: boolean
}

export interface CanvasStatusProjectionOptions {
  readonly descriptor: CanvasSessionDescriptor
  readonly nodes: Readonly<Ref<readonly CanvasStatusNode[]>>
  readonly validationResult: Readonly<Ref<ValidationResult | null>>
  readonly acceptedDraftRevision: Readonly<Ref<number | null>>
}

export interface CanvasStatusProjectionReader {
  readonly canvasId: CanvasId | null
  readonly statuses: ComputedRef<Record<string, ProjectedNodeStatus>>
  statusForNode(nodeId: string): ProjectedNodeStatus | null
  progressForNode(nodeId: string): ProgressInfo | null
}

export interface CanvasStatusProjectionApi extends CanvasStatusProjectionReader {
  markProvisional(nodeId: string, value: NodeStatus): void
  markAllProvisional(): void
  dispose(): void
}

interface CanvasStatusProjectionResource
  extends CanvasStatusProjectionReader, DisposableCanvasResource {
  markProvisional(nodeId: string, value: NodeStatus): void
  markAllProvisional(): void
}

export const CANVAS_STATUS_PROJECTION_KEY:
InjectionKey<CanvasStatusProjectionReader> = Symbol('bioimageflow:canvas-status')

let activeFacade: CanvasStatusProjectionApi | null = null

export function useCanvasStatusProjection(
  options: CanvasStatusProjectionOptions,
): CanvasStatusProjectionApi
export function useCanvasStatusProjection(): CanvasStatusProjectionApi
export function useCanvasStatusProjection(
  options?: CanvasStatusProjectionOptions,
): CanvasStatusProjectionApi {
  if (options === undefined) {
    if (activeFacade === null) activeFacade = createActiveFacade()
    return activeFacade
  }

  canvasSessionRegistry.register(options.descriptor)
  const resource = canvasSessionRegistry.getOrCreateResource(
    options.descriptor.canvasId,
    CANVAS_STATUS_RESOURCE,
    () => createCanvasStatusProjectionResource(options),
  )
  return fixedFacade(options.descriptor.canvasId, resource)
}

/** Test-only reset for the compatibility facade. */
export function _resetCanvasStatusProjectionForTest(): void {
  activeFacade = null
}

export function getCanvasStatusProjection(
  canvasId: CanvasId,
): CanvasStatusProjectionReader | null {
  return canvasSessionRegistry.getResource<CanvasStatusProjectionResource>(
    canvasId,
    CANVAS_STATUS_RESOURCE,
  )
}

function createCanvasStatusProjectionResource(
  options: CanvasStatusProjectionOptions,
): CanvasStatusProjectionResource {
  const execution = useExecutionStore()
  const provisionalOverrides = ref<Record<string, NodeStatus>>({})
  const disposed = ref(false)

  const stopValidationWatch = watch(
    options.validationResult,
    (result) => {
      if (!result?.node_statuses) return
      const next = { ...provisionalOverrides.value }
      let changed = false
      for (const nodeId of Object.keys(result.node_statuses)) {
        if (!(nodeId in next)) continue
        delete next[nodeId]
        changed = true
      }
      if (changed) provisionalOverrides.value = next
    },
    { deep: true, flush: 'sync' },
  )

  function statusForNode(
    nodeId: string,
    node?: CanvasStatusNode,
  ): ProjectedNodeStatus | null {
    if (disposed.value) return null
    const ownedScoped = node === undefined && isOwnedScopedNodeId(nodeId)
    if (node === undefined && !ownedScoped) return null
    const contextless = execution.executionId === null
    const originMatches = options.descriptor.kind === 'root'
      && execution.appliesToCanvas(options.descriptor.canvasId)
    const projected = projectNodeStatus({
      nodeId,
      enabled: node?.enabled ?? true,
      provisionalOverride: provisionalOverrides.value[nodeId] ?? null,
      executionStatus: execution.nodeStatuses[nodeId] ?? null,
      validationStatus:
        options.validationResult.value?.node_statuses?.[nodeId] ?? null,
      executionOriginMatches: originMatches,
      executionIsContextless: contextless,
      allowContextlessLegacyExecution: contextless && originMatches,
      executionDraftRevision: execution.executionDraftRevision,
      acceptedDraftRevision: options.acceptedDraftRevision.value,
    })
    return node === undefined && projected.source === 'default' ? null : projected
  }

  function isOwnedScopedNodeId(nodeId: string): boolean {
    return options.nodes.value.some(node => nodeId.startsWith(`${node.id}/`))
  }

  function scopedStatusIds(): Set<string> {
    const ids = new Set<string>()
    for (const candidates of [
      Object.keys(options.validationResult.value?.node_statuses ?? {}),
      Object.keys(execution.nodeStatuses),
      Object.keys(provisionalOverrides.value),
    ]) {
      for (const nodeId of candidates) {
        if (isOwnedScopedNodeId(nodeId)) ids.add(nodeId)
      }
    }
    return ids
  }

  const statuses = computed<Record<string, ProjectedNodeStatus>>(() => {
    if (disposed.value) return {}
    const result: Record<string, ProjectedNodeStatus> = {}
    for (const node of options.nodes.value) {
      const status = statusForNode(node.id, node)
      if (status !== null) result[node.id] = status
    }
    for (const nodeId of scopedStatusIds()) {
      const status = statusForNode(nodeId)
      if (status !== null) result[nodeId] = status
    }
    return result
  })

  function assertActive(): void {
    if (disposed.value) throw new Error('Canvas status projection has been disposed')
  }

  function markProvisional(nodeId: string, value: NodeStatus): void {
    assertActive()
    provisionalOverrides.value = {
      ...provisionalOverrides.value,
      [nodeId]: { ...value },
    }
  }

  function markAllProvisional(): void {
    assertActive()
    const next = { ...provisionalOverrides.value }
    for (const [nodeId, current] of Object.entries(statuses.value)) {
      next[nodeId] = statusValue(current)
    }
    provisionalOverrides.value = next
  }

  return {
    canvasId: options.descriptor.canvasId,
    statuses,
    statusForNode: nodeId => (
      statuses.value[nodeId]
      ?? statusForNode(nodeId)
    ),
    progressForNode: (nodeId) => {
      const status = statuses.value[nodeId] ?? statusForNode(nodeId)
      if (status?.source !== 'execution') return null
      const current = execution.progress
      return current?.node_id === nodeId ? current : null
    },
    markProvisional,
    markAllProvisional,
    dispose: () => {
      if (disposed.value) return
      disposed.value = true
      provisionalOverrides.value = {}
      stopValidationWatch()
    },
  }
}

function fixedFacade(
  canvasId: CanvasId,
  resource: CanvasStatusProjectionResource,
): CanvasStatusProjectionApi {
  return {
    canvasId,
    statuses: resource.statuses,
    statusForNode: nodeId => resource.statusForNode(nodeId),
    progressForNode: nodeId => resource.progressForNode(nodeId),
    markProvisional: (nodeId, value) => resource.markProvisional(nodeId, value),
    markAllProvisional: () => resource.markAllProvisional(),
    dispose: () => canvasSessionRegistry.unregister(canvasId),
  }
}

function createActiveFacade(): CanvasStatusProjectionApi {
  const execution = useExecutionStore()
  const graphSync = useGraphSync()
  const persistence = useCanvasPersistence()
  function legacyStatusForNode(
    nodeId: string,
    enabled?: boolean,
  ): ProjectedNodeStatus | null {
    if (canvasSessionRegistry.sessionCount.value !== 0) return null
    const originMatches = execution.appliesToCanvas(LEGACY_CANVAS_ID)
    const projected = projectNodeStatus({
      nodeId,
      enabled: enabled ?? true,
      provisionalOverride: null,
      executionStatus: execution.nodeStatuses[nodeId] ?? null,
      validationStatus: graphSync.validationResult.value?.node_statuses?.[nodeId] ?? null,
      executionOriginMatches: originMatches,
      executionIsContextless: execution.executionId === null,
      allowContextlessLegacyExecution:
        execution.executionId === null && originMatches,
      executionDraftRevision: execution.executionDraftRevision,
      acceptedDraftRevision: persistence.acceptedDraftRevision.value,
    })
    return enabled === undefined && projected.source !== 'execution' ? null : projected
  }

  const statuses = computed<Record<string, ProjectedNodeStatus>>(() => {
    const resource = activeResource()
    if (resource !== null) return resource.statuses.value
    if (canvasSessionRegistry.sessionCount.value !== 0) return {}

    const result: Record<string, ProjectedNodeStatus> = {}
    for (const node of graphSync.currentGraph.value.nodes) {
      const status = legacyStatusForNode(node.id, node.enabled !== false)
      if (status !== null) result[node.id] = status
    }
    return result
  })

  return {
    get canvasId() {
      return canvasSessionRegistry.activeCanvasId.value
    },
    statuses,
    statusForNode: nodeId => (
      statuses.value[nodeId]
      ?? activeResource()?.statusForNode(nodeId)
      ?? legacyStatusForNode(nodeId)
    ),
    progressForNode: (nodeId) => {
      const resource = activeResource()
      if (resource !== null) return resource.progressForNode(nodeId)
      if (legacyStatusForNode(nodeId)?.source !== 'execution') return null
      return execution.progress?.node_id === nodeId ? execution.progress : null
    },
    markProvisional: (nodeId, value) => {
      activeResource()?.markProvisional(nodeId, value)
    },
    markAllProvisional: () => {
      activeResource()?.markAllProvisional()
    },
    dispose: () => {
      const canvasId = canvasSessionRegistry.activeCanvasId.value
      if (canvasId !== null) canvasSessionRegistry.unregister(canvasId)
    },
  }
}

function activeResource(): CanvasStatusProjectionResource | null {
  const canvasId = canvasSessionRegistry.activeCanvasId.value
  if (canvasId === null) return null
  return canvasSessionRegistry.getResource<CanvasStatusProjectionResource>(
    canvasId,
    CANVAS_STATUS_RESOURCE,
  )
}

function statusValue(value: ProjectedNodeStatus): NodeStatus {
  const { provisional: _provisional, source: _source, ...status } = value
  return status
}
