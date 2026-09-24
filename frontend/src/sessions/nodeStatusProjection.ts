import type { GraphValidationError, NodeStatus } from '@/api/types'
import type { ExecutionPhase } from '@/stores/execution'

export type NodeStatusProjectionSource =
  | 'semantic'
  | 'execution'
  | 'validation'
  | 'default'

export interface ProjectedNodeStatus extends NodeStatus {
  presentationStatus: NodeStatus['status']
  source: NodeStatusProjectionSource
}

export interface NodeStatusProjectionInput {
  nodeId: string
  enabled: boolean
  semanticOverride: NodeStatus | null
  semanticPresentationStatus: NodeStatus['status'] | null
  executionStatus: NodeStatus | null
  executionPhase: ExecutionPhase
  validationStatus: NodeStatus | null
  validationErrors: readonly GraphValidationError[]
  executionOriginMatches: boolean
  executionDraftRevision: number | null
  acceptedDraftRevision: number | null
}

/** Resolve one node badge from local, execution, validation, and graph inputs. */
export function projectNodeStatus(
  input: NodeStatusProjectionInput,
): ProjectedNodeStatus {
  if (input.semanticOverride !== null) {
    return projected(
      input.semanticOverride,
      'semantic',
      input.semanticPresentationStatus ?? input.semanticOverride.status,
    )
  }

  if (
    input.executionPhase === 'idle'
    && input.validationStatus?.status === 'failed'
    && input.validationErrors.some(error => (
      error.type === 'cache_corrupt'
      && (error.node === input.nodeId || error.node?.startsWith(`${input.nodeId}/`))
    ))
  ) {
    return projected(input.validationStatus, 'validation')
  }

  if (executionMatchesCanvasDraft(input) && input.executionStatus !== null) {
    return projected(input.executionStatus, 'execution')
  }

  if (input.validationStatus !== null) {
    return projected(input.validationStatus, 'validation')
  }

  return projected({
    node_id: input.nodeId,
    status: input.enabled ? 'unexecuted' : 'disabled',
    cached: false,
  }, 'default')
}

function executionMatchesCanvasDraft(input: NodeStatusProjectionInput): boolean {
  if (!input.executionOriginMatches) return false
  return input.executionDraftRevision !== null
    && input.acceptedDraftRevision !== null
    && input.executionDraftRevision === input.acceptedDraftRevision
}

function projected(
  value: NodeStatus,
  source: NodeStatusProjectionSource,
  presentationStatus: NodeStatus['status'] = value.status,
): ProjectedNodeStatus {
  return {
    ...value,
    presentationStatus,
    source,
  }
}
