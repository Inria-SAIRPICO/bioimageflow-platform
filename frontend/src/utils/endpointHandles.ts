export type EndpointHandle =
  | { kind: 'dataframe-output' }
  | { kind: 'tool-input'; name: string }
  | { kind: 'tool-output'; name: string }
  | { kind: 'dataframe-position'; index: number }
  | { kind: 'dataframe-input'; name: string }
  | { kind: 'workflow-input'; id: string }
  | { kind: 'workflow-output'; id: string }

const PREFIX = 'bif:v1:'

function encodeText(value: string): string {
  if (value.length === 0) throw new Error('Endpoint identity cannot be empty')
  return encodeURIComponent(value)
}

export function encodeEndpointHandle(endpoint: EndpointHandle): string {
  switch (endpoint.kind) {
    case 'dataframe-output':
      return `${PREFIX}dataframe-output`
    case 'dataframe-position':
      if (!Number.isSafeInteger(endpoint.index) || endpoint.index < 0) {
        throw new Error('DataFrame input position must be a non-negative integer')
      }
      return `${PREFIX}dataframe-position:${endpoint.index}`
    case 'tool-input':
    case 'tool-output':
    case 'dataframe-input':
      return `${PREFIX}${endpoint.kind}:${encodeText(endpoint.name)}`
    case 'workflow-input':
    case 'workflow-output':
      return `${PREFIX}${endpoint.kind}:${encodeText(endpoint.id)}`
  }
}

export function decodeEndpointHandle(handle: string): EndpointHandle {
  if (!handle.startsWith(PREFIX)) throw new Error(`Invalid endpoint handle: ${handle}`)
  const encoded = handle.slice(PREFIX.length)
  if (encoded === 'dataframe-output') return { kind: 'dataframe-output' }
  const separator = encoded.indexOf(':')
  if (separator < 0) throw new Error(`Invalid endpoint handle: ${handle}`)
  const kind = encoded.slice(0, separator)
  const payload = encoded.slice(separator + 1)
  if (kind === 'dataframe-position') {
    if (!/^\d+$/.test(payload)) throw new Error(`Invalid endpoint handle: ${handle}`)
    const index = Number(payload)
    if (!Number.isSafeInteger(index)) throw new Error(`Invalid endpoint handle: ${handle}`)
    return { kind, index }
  }
  let identity: string
  try {
    identity = decodeURIComponent(payload)
  } catch {
    throw new Error(`Invalid endpoint handle: ${handle}`)
  }
  if (identity.length === 0) throw new Error(`Invalid endpoint handle: ${handle}`)
  if (kind === 'tool-input' || kind === 'tool-output' || kind === 'dataframe-input') {
    return { kind, name: identity }
  }
  if (kind === 'workflow-input' || kind === 'workflow-output') {
    return { kind, id: identity }
  }
  throw new Error(`Invalid endpoint handle: ${handle}`)
}

export function isDataFrameEndpoint(handle: string | null | undefined): boolean {
  if (!handle) return false
  const endpoint = decodeEndpointHandle(handle)
  return endpoint.kind === 'dataframe-output'
    || endpoint.kind === 'dataframe-position'
    || endpoint.kind === 'dataframe-input'
}
