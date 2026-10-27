import type { SerializedConstant } from '@/api/types'

interface ConstantEnvelope { __type__: string; value: unknown }
const kinds = new Set(['none', 'bool', 'int', 'float', 'str', 'path', 'list', 'tuple', 'dict'])
function envelope(value: unknown): value is ConstantEnvelope {
  return !!value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === 2 && '__type__' in value && 'value' in value
    && typeof value.__type__ === 'string' && kinds.has(value.__type__)
}
function canonical(value: unknown): value is ConstantEnvelope {
  if (!envelope(value)) return false
  if (value.__type__ === 'list' || value.__type__ === 'tuple') return Array.isArray(value.value) && value.value.every(canonical)
  if (value.__type__ === 'dict') return Array.isArray(value.value) && value.value.every(entry => (
    entry && typeof entry === 'object' && Object.keys(entry).length === 2 && canonical(entry.key) && canonical(entry.value)
  ))
  return true
}

/** Widget values are JSON values; the backend admits the public library wire. */
export function encodeWorkflowConstant(value: unknown, type?: string, previous?: unknown): SerializedConstant {
  function encode(item: unknown, declared?: string, prior?: unknown): ConstantEnvelope {
    if (canonical(prior) && JSON.stringify(item) === JSON.stringify(decodeWorkflowConstant(prior))) {
      return JSON.parse(JSON.stringify(prior))
    }
    const priorEnvelope = envelope(prior) ? prior : undefined
    if (item === null) return { __type__: 'none', value: null }
    if (Array.isArray(item)) return {
      __type__: declared === 'tuple' || priorEnvelope?.__type__ === 'tuple' ? 'tuple' : 'list',
      value: item.map((child, index) => encode(child, undefined, Array.isArray(priorEnvelope?.value) ? priorEnvelope.value[index] : undefined)),
    }
    if (typeof item === 'number' && Number.isFinite(item)) return {
      __type__: declared === 'float' || priorEnvelope?.__type__ === 'float' || !Number.isInteger(item) ? 'float' : 'int', value: item,
    }
    if (typeof item === 'boolean') return { __type__: 'bool', value: item }
    if (typeof item === 'string') return { __type__: priorEnvelope?.__type__ === 'path' ? 'path' : 'str', value: item }
    if (item && typeof item === 'object' && Object.getPrototypeOf(item) === Object.prototype) return {
      __type__: 'dict', value: Object.entries(item).map(([key, child]) => ({
        key: encode(key), value: encode(child, undefined, priorEnvelope?.__type__ === 'dict' && Array.isArray(priorEnvelope.value)
          ? priorEnvelope.value.find(entry => entry?.key?.__type__ === 'str' && entry.key.value === key)?.value : undefined),
      })),
    }
    throw new TypeError('This value cannot be represented as a workflow constant.')
  }
  const result = encode(value, type, previous)
  if (result.__type__ === 'dict' || result.__type__ === 'path') throw new TypeError('This workflow input type is not supported.')
  return result as SerializedConstant
}

/** Also reads the old raw JSON sequence representation without mutating it. */
export function decodeWorkflowConstant(constant: { __type__?: string; value?: unknown }): unknown {
  const decode = (item: unknown): unknown => {
    return envelope(item) ? decodeWorkflowConstant(item) : item
  }
  if (constant.__type__ === 'list' || constant.__type__ === 'tuple') {
    if (!Array.isArray(constant.value)) return constant.value
    return constant.value.map(decode)
  }
  if (constant.__type__ === 'dict' && Array.isArray(constant.value)) {
    const entries = constant.value as { key: ConstantEnvelope; value: ConstantEnvelope }[]
    if (entries.every(entry => entry?.key?.__type__ === 'str' && typeof entry.key.value === 'string')) {
      return Object.fromEntries(entries.map(entry => [entry.key.value, decode(entry.value)]))
    }
    throw new TypeError('This dictionary has non-string keys and cannot be edited as JSON.')
  }
  return constant.value
}
