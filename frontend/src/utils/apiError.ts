import type { GraphValidationError } from '@/api/types'

interface ApiValidationIssue {
  loc?: unknown
  msg?: unknown
  type?: unknown
}

/** Structured graph errors returned alongside a workflow build failure. */
export function apiGraphValidationErrors(error: unknown): GraphValidationError[] {
  if (typeof error !== 'object' || error === null || !('response' in error)) return []
  const response = (error as { response?: { data?: { errors?: unknown } } }).response
  const errors = response?.data?.errors
  if (!Array.isArray(errors)) return []
  return errors.filter((issue): issue is GraphValidationError => (
    typeof issue === 'object'
    && issue !== null
    && typeof issue.detail === 'string'
  ))
}

function validationLocation(value: unknown): string {
  if (!Array.isArray(value)) return ''
  let result = ''
  for (const part of value) {
    if (part === 'body') continue
    if (typeof part === 'number') {
      result += `[${part}]`
      continue
    }
    if (typeof part !== 'string' || part.length === 0) continue
    result += result.length > 0 ? `.${part}` : part
  }
  return result
}

function validationIssueMessage(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (typeof value !== 'object' || value === null) return String(value)
  const issue = value as ApiValidationIssue
  const location = validationLocation(issue.loc)
  const message = typeof issue.msg === 'string'
    ? issue.msg.replace(/^Value error,\s*/i, '').trim()
    : ''
  if (location && message) return `${location}: ${message}`
  if (message) return message
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function payloadMessage(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (Array.isArray(value)) {
    return value.map(validationIssueMessage).filter(Boolean).join('\n')
  }
  if (typeof value !== 'object' || value === null) return ''
  try {
    return JSON.stringify(value)
  } catch {
    return ''
  }
}

/** Return the most specific server-provided message available for an API error. */
export function apiErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as {
      response?: { data?: { detail?: unknown; message?: unknown } }
    }).response
    for (const candidate of [response?.data?.detail, response?.data?.message]) {
      const message = payloadMessage(candidate)
      if (message.length > 0) return message
    }
  }
  if (error instanceof Error) return error.message.trim()
  return typeof error === 'string' ? error.trim() : String(error ?? '')
}
