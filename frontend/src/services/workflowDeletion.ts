import type {
  CanvasId,
  CanvasSessionRegistrationToken,
} from '@/sessions/canvasSessionRegistry'

export interface WorkflowDeletionRequest {
  workflowName: string
  canvasId: CanvasId | null
  localIdentityGeneration: number
  serverIdentityGeneration: number | null
  sessionRegistrationToken: CanvasSessionRegistrationToken | null
}

export class WorkflowDeletionTargetChangedError extends Error {
  constructor(workflowName: string) {
    super(`Workflow '${workflowName}' was replaced after this delete confirmation opened. Review the current workflow and delete it again.`)
    this.name = 'WorkflowDeletionTargetChangedError'
  }
}

export class WorkflowDeletionCommittedCleanupError extends Error {
  readonly cause: unknown

  constructor(workflowName: string, cause: unknown) {
    const detail = cause instanceof Error ? cause.message : String(cause)
    super(`Workflow '${workflowName}' was deleted, but local recovery cleanup did not finish: ${detail}`)
    this.name = 'WorkflowDeletionCommittedCleanupError'
    this.cause = cause
  }
}

export interface WorkflowDeletionEventDetail extends WorkflowDeletionRequest {
  resolve: () => void
  reject: (error: unknown) => void
}

export function requestWorkflowDeletion(
  request: WorkflowDeletionRequest,
): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    window.dispatchEvent(new CustomEvent<WorkflowDeletionEventDetail>(
      'bioimageflow:request-delete-workflow',
      { detail: { ...request, resolve, reject } },
    ))
  })
}
