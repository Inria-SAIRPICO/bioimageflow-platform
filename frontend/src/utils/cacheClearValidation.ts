import type { NodeStatus, ValidationResult } from '@/api/types'

/** Apply a successful cache-clear response to the accepted canvas validation snapshot. */
export function validationAfterCacheClear(
  validation: ValidationResult,
  requestedNodeIds: string[],
  statuses: Record<string, NodeStatus>,
): ValidationResult {
  const repairedRoots = new Set(
    requestedNodeIds.filter((nodeId) => {
      const status = statuses[nodeId]
      return status !== undefined && status.status !== 'failed'
    }),
  )
  const errors = validation.errors.filter(error => (
    error.type !== 'cache_corrupt'
    || typeof error.node !== 'string'
    || !repairedRoots.has(error.node.split('/', 1)[0]!)
  ))
  return {
    ...validation,
    valid: errors.length === 0,
    errors,
    node_statuses: {
      ...validation.node_statuses,
      ...statuses,
    },
  }
}
