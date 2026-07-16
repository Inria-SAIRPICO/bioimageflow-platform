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
    published_outputs?: Array<{ name: string }>
  }
}

export function fieldDisplayName(
  fieldName: string,
  field?: unknown,
): string {
  if (fieldName === '__dataframe_out') return 'DataFrame'
  const displayName = field && typeof field === 'object'
    ? (field as DisplayNamedField).display_name
    : undefined
  return typeof displayName === 'string' && displayName.trim().length > 0
    ? displayName
    : fieldName
}

export function connectionSourceLabel(
  sourceNode: ConnectionSourceNode | null | undefined,
  sourceHandle: string | null | undefined,
  resolvedOutput?: unknown,
): string {
  const handle = sourceHandle || 'output'
  const data = sourceNode?.data
  const nodeName = data?.name ?? sourceNode?.name ?? sourceNode?.id ?? ''
  const output = resolvedOutput ?? data?.tool?.outputs?.[handle]
  const field = output && typeof output === 'object'
    ? output as DisplayNamedField
    : null
  return `${fieldDisplayName(handle, field)} of ${nodeName}`
}
