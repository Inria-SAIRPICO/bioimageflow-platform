interface DisplayNamedField {
  display_name?: unknown
}

interface ConnectionSourceNode {
  id?: string
  name?: string
  data?: {
    name?: string
    tool?: {
      outputs?: Record<string, unknown>
    } | null
    workflow?: {
      interface: { outputs: Array<{ id: string; name: string }> }
    }
  }
}

export function fieldDisplayName(
  fieldName: string,
  field?: unknown,
): string {
  let endpointName = fieldName
  try {
    const endpoint = decodeEndpointHandle(fieldName)
    if (endpoint.kind === 'dataframe-output') return 'DataFrame'
    if (endpoint.kind === 'dataframe-position') return String(endpoint.index + 1)
    endpointName = 'id' in endpoint ? endpoint.id : endpoint.name
  } catch {
    // Non-handle labels are also used outside the canvas.
  }
  const displayName = field && typeof field === 'object'
    ? (field as DisplayNamedField).display_name
    : undefined
  return typeof displayName === 'string' && displayName.trim().length > 0
    ? displayName
    : endpointName
}

export function connectionSourceLabel(
  sourceNode: ConnectionSourceNode | null | undefined,
  sourceHandle: string | null | undefined,
  resolvedOutput?: unknown,
): string {
  const handle = sourceHandle || 'output'
  const data = sourceNode?.data
  const nodeName = data?.name ?? sourceNode?.name ?? sourceNode?.id ?? ''
  let outputName = handle
  try {
    const endpoint = decodeEndpointHandle(handle)
    outputName = 'id' in endpoint ? endpoint.id : 'name' in endpoint ? endpoint.name : handle
  } catch {
    // Callers outside Vue Flow may pass a plain output name.
  }
  const workflowOutput = data?.workflow?.interface.outputs.find(
    output => output.id === outputName,
  )
  const output = resolvedOutput ?? data?.tool?.outputs?.[outputName]
  const field = output && typeof output === 'object'
    ? output as DisplayNamedField
    : null
  return `${workflowOutput?.name ?? fieldDisplayName(handle, field)} of ${nodeName}`
}
import { decodeEndpointHandle } from '@/utils/endpointHandles'
