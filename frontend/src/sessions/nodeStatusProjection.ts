import type { NodeStatus } from '@/api/types'

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
  validationStatus: NodeStatus | null
  executionOriginMatches: boolean
  executionIsContextless: boolean
  allowContextlessLegacyExecution: boolean
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
  if (input.executionIsContextless) {
    return input.allowContextlessLegacyExecution
  }
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
