import axios from 'axios'
import type { GraphState, NodeOutputSchemaResponse } from '@/api/types'

// Don't set a global Content-Type default — axios auto-detects body type
// (application/json for objects, multipart/form-data with boundary for
// FormData, etc.). A hardcoded default breaks FormData uploads.
export const api = axios.create()

/**
 * Fetch the resolved output column schema for a single node.
 * The full graph is submitted because resolution may depend on upstream wiring.
 */
export async function fetchNodeOutputSchema(
  nodeId: string,
  graph: GraphState,
): Promise<NodeOutputSchemaResponse> {
  const { data } = await api.post<NodeOutputSchemaResponse>(
    `/api/v1/graph/nodes/${nodeId}/output_schema`,
    graph,
  )
  return data
}
