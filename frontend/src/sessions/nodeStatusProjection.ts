import type { NodeStatus } from '@/api/types'

export type NodeStatusProjectionSource =
  | 'provisional'
  | 'execution'
  | 'validation'
  | 'default'

export interface ProjectedNodeStatus extends NodeStatus {
  provisional: boolean
  source: NodeStatusProjectionSource
}

export interface NodeStatusProjectionInput {
  nodeId: string
  enabled: boolean
  provisionalOverride: NodeStatus | null
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
  if (input.provisionalOverride !== null) {
    return projected(input.provisionalOverride, 'provisional', true)
  }

  if (executionMatchesCanvasDraft(input) && input.executionStatus !== null) {
    return projected(input.executionStatus, 'execution', false)
  }

  if (input.validationStatus !== null) {
    return projected(input.validationStatus, 'validation', false)
  }

  return projected({
    node_id: input.nodeId,
    status: input.enabled ? 'unexecuted' : 'disabled',
    cached: false,
  }, 'default', false)
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
  provisional: boolean,
): ProjectedNodeStatus {
  return {
    ...value,
    provisional,
    source,
  }
}
