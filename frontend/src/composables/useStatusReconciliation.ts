import { computed, ref, type Ref, watch } from 'vue'
import type { NodeState, NodeStatus, ValidationResult } from '@/api/types'

export interface NodeStateMessage {
  node_id: string
  status: string
}

export interface ReconciledStatus {
  status: string
  provisional: boolean
}

export function useStatusReconciliation(
  nodes: Ref<NodeState[]>,
  validationResult: Ref<ValidationResult | null>,
  wsMessages: Ref<NodeStateMessage[]>,
) {
  // Provisional statuses set by the client during debounce
  const provisionalStatuses = ref<Record<string, string>>({})

  // WS overrides, keyed by node_id
  const wsOverrides = ref<Record<string, string>>({})

  // When validation arrives, clear provisional statuses for nodes it covers
  watch(validationResult, (val) => {
    if (!val?.node_statuses) return
    const next = { ...provisionalStatuses.value }
    for (const nodeId of Object.keys(val.node_statuses)) {
      delete next[nodeId]
    }
    provisionalStatuses.value = next
  })

  // Track WS messages
  watch(wsMessages, (messages) => {
    if (!messages || messages.length === 0) return
    const overrides = { ...wsOverrides.value }
    for (const msg of messages) {
      overrides[msg.node_id] = msg.status
    }
    wsOverrides.value = overrides
  }, { deep: true, immediate: true })

  const reconciledStatuses = computed<Record<string, ReconciledStatus>>(() => {
    const result: Record<string, ReconciledStatus> = {}

    for (const node of nodes.value) {
      const nodeId = node.id

      // Priority: WS > validation > provisional > default
      if (wsOverrides.value[nodeId] !== undefined) {
        result[nodeId] = {
          status: wsOverrides.value[nodeId],
          provisional: false,
        }
      } else if (
        provisionalStatuses.value[nodeId] === undefined &&
        validationResult.value?.node_statuses?.[nodeId]
      ) {
        result[nodeId] = {
          status: validationResult.value.node_statuses[nodeId].status,
          provisional: false,
        }
      } else if (provisionalStatuses.value[nodeId] !== undefined) {
        result[nodeId] = {
          status: provisionalStatuses.value[nodeId],
          provisional: true,
        }
      } else {
        result[nodeId] = {
          status: 'unexecuted',
          provisional: false,
        }
      }
    }

    return result
  })

  const isReconciling = computed(() =>
    Object.keys(provisionalStatuses.value).length > 0,
  )

  function markProvisional(nodeId: string, status: string): void {
    provisionalStatuses.value = {
      ...provisionalStatuses.value,
      [nodeId]: status,
    }
  }

  return { reconciledStatuses, isReconciling, markProvisional }
}
