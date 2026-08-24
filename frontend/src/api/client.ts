import axios from 'axios'
import type { GraphState, NodeOutputSchemaResponse } from '@/api/types'
import { apiErrorMessage } from '@/utils/apiError'

// Don't set a global Content-Type default — axios auto-detects body type
// (application/json for objects, multipart/form-data with boundary for
// FormData, etc.). A hardcoded default breaks FormData uploads.
export const api = axios.create()

api.interceptors.response.use(
  response => response,
  (error: unknown) => {
    if (error instanceof Error) {
      const message = apiErrorMessage(error)
      if (message.length > 0) error.message = message
    }
    return Promise.reject(error)
  },
)

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
