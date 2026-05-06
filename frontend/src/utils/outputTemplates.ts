import type { ToolMetadata } from '@/api/types'

const PATH_OUTPUT_TYPES = new Set(['Path', 'ImageFile', 'MaskPath'])

function isPathOutput(field: unknown): field is { type?: string; default?: unknown } {
  return (
    typeof field === 'object'
    && field !== null
    && PATH_OUTPUT_TYPES.has(String((field as { type?: unknown }).type ?? ''))
  )
}

export function reconcileOutputTemplates(
  tool: ToolMetadata | null | undefined,
  existing: Record<string, string> = {},
): Record<string, string> {
  if (!tool || tool.tool_type === 'DataFrameTool') {
    return {}
  }

  const reconciled: Record<string, string> = {}
  for (const [key, rawField] of Object.entries(tool.outputs ?? {})) {
    if (!isPathOutput(rawField)) continue
    const current = existing[key]
    if (typeof current === 'string') {
      reconciled[key] = current
      continue
    }
    reconciled[key] = typeof rawField.default === 'string' ? rawField.default : ''
  }
  return reconciled
}
