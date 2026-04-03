import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, nextTick } from 'vue'
import type { NodeState, ValidationResult, NodeStatus } from '@/api/types'
import type { NodeStateMessage } from '../useStatusReconciliation'
import { useStatusReconciliation } from '../useStatusReconciliation'

function makeNodeStatus(
  nodeId: string,
  status: NodeStatus['status'] = 'unexecuted',
): NodeStatus {
  return { node_id: nodeId, status, cached: false }
}

function makeValidation(statuses: Record<string, NodeStatus>): ValidationResult {
  return { valid: true, node_statuses: statuses, errors: [] }
}

describe('useStatusReconciliation', () => {
  it('returns authoritative statuses when no edits are pending', () => {
    const nodes = ref<NodeState[]>([
      { id: 'a', name: 'A', tool_name: 't', position: [0, 0], parameters: {} },
    ])
    const validation = ref<ValidationResult | null>(
      makeValidation({ a: makeNodeStatus('a', 'executed') }),
    )
    const ws = ref<NodeStateMessage[]>([])

    const { reconciledStatuses } = useStatusReconciliation(nodes, validation, ws)

    expect(reconciledStatuses.value.a).toEqual(
      expect.objectContaining({ status: 'executed', provisional: false }),
    )
  })

  it('shows provisional status during debounce', () => {
    const nodes = ref<NodeState[]>([
      { id: 'a', name: 'A', tool_name: 't', position: [0, 0], parameters: {} },
    ])
    const validation = ref<ValidationResult | null>(null)
    const ws = ref<NodeStateMessage[]>([])

    const { reconciledStatuses, markProvisional } = useStatusReconciliation(nodes, validation, ws)

    markProvisional('a', 'out_of_date')

    expect(reconciledStatuses.value.a).toEqual(
      expect.objectContaining({ status: 'out_of_date', provisional: true }),
    )
  })

  it('authoritative overwrites provisional when validation arrives', async () => {
    const nodes = ref<NodeState[]>([
      { id: 'a', name: 'A', tool_name: 't', position: [0, 0], parameters: {} },
    ])
    const validation = ref<ValidationResult | null>(null)
    const ws = ref<NodeStateMessage[]>([])

    const { reconciledStatuses, markProvisional } = useStatusReconciliation(nodes, validation, ws)

    markProvisional('a', 'out_of_date')
    expect(reconciledStatuses.value.a.provisional).toBe(true)

    validation.value = makeValidation({ a: makeNodeStatus('a', 'executed') })
    await nextTick()

    expect(reconciledStatuses.value.a).toEqual(
      expect.objectContaining({ status: 'executed', provisional: false }),
    )
  })

  it('WS updates take effect immediately', async () => {
    const nodes = ref<NodeState[]>([
      { id: 'a', name: 'A', tool_name: 't', position: [0, 0], parameters: {} },
    ])
    const validation = ref<ValidationResult | null>(
      makeValidation({ a: makeNodeStatus('a', 'unexecuted') }),
    )
    const ws = ref<NodeStateMessage[]>([])

    const { reconciledStatuses } = useStatusReconciliation(nodes, validation, ws)

    ws.value = [{ node_id: 'a', status: 'running' }]
    await nextTick()

    expect(reconciledStatuses.value.a).toEqual(
      expect.objectContaining({ status: 'running', provisional: false }),
    )
  })

  it('WS has priority over stale validation', async () => {
    const nodes = ref<NodeState[]>([
      { id: 'a', name: 'A', tool_name: 't', position: [0, 0], parameters: {} },
    ])
    const validation = ref<ValidationResult | null>(
      makeValidation({ a: makeNodeStatus('a', 'unexecuted') }),
    )
    const ws = ref<NodeStateMessage[]>([{ node_id: 'a', status: 'running' }])

    const { reconciledStatuses } = useStatusReconciliation(nodes, validation, ws)

    // WS should win over validation
    expect(reconciledStatuses.value.a).toEqual(
      expect.objectContaining({ status: 'running', provisional: false }),
    )
  })

  it('isReconciling is true when provisional exists', () => {
    const nodes = ref<NodeState[]>([
      { id: 'a', name: 'A', tool_name: 't', position: [0, 0], parameters: {} },
    ])
    const validation = ref<ValidationResult | null>(null)
    const ws = ref<NodeStateMessage[]>([])

    const { isReconciling, markProvisional } = useStatusReconciliation(nodes, validation, ws)

    expect(isReconciling.value).toBe(false)

    markProvisional('a', 'out_of_date')

    expect(isReconciling.value).toBe(true)
  })

  it('handles multiple rapid edits', async () => {
    const nodes = ref<NodeState[]>([
      { id: 'a', name: 'A', tool_name: 't', position: [0, 0], parameters: {} },
      { id: 'b', name: 'B', tool_name: 't', position: [0, 0], parameters: {} },
    ])
    const validation = ref<ValidationResult | null>(null)
    const ws = ref<NodeStateMessage[]>([])

    const { reconciledStatuses, markProvisional, isReconciling } = useStatusReconciliation(nodes, validation, ws)

    markProvisional('a', 'out_of_date')
    markProvisional('b', 'out_of_date')

    expect(reconciledStatuses.value.a.provisional).toBe(true)
    expect(reconciledStatuses.value.b.provisional).toBe(true)
    expect(isReconciling.value).toBe(true)

    // Validation arrives for both
    validation.value = makeValidation({
      a: makeNodeStatus('a', 'executed'),
      b: makeNodeStatus('b', 'executed'),
    })
    await nextTick()

    expect(reconciledStatuses.value.a.provisional).toBe(false)
    expect(reconciledStatuses.value.b.provisional).toBe(false)
    expect(isReconciling.value).toBe(false)
  })
})
