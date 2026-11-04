import type { OutputFileDeclaration, ToolMetadata } from '@/api/types'

const PATH_OUTPUT_TYPES = new Set(['Path', 'ImageFile', 'MaskPath'])

export type OutputFileMetadata = Partial<OutputFileDeclaration> & {
  type?: string
  default?: unknown
}

export function outputFileMetadata(tool: ToolMetadata | null | undefined, key: string, raw: unknown): OutputFileMetadata {
  return { ...(typeof raw === 'object' && raw !== null ? raw : {}), ...tool?.output_file_declarations?.[key] }
}

export function isWritableOutputTemplate(field: unknown): field is OutputFileMetadata {
  return (
    typeof field === 'object'
    && field !== null
    && PATH_OUTPUT_TYPES.has(String((field as { type?: unknown }).type ?? ''))
    && ['exact', 'base'].includes(String((field as OutputFileMetadata).output_role ?? ''))
  )
}

export function outputFileDescription(field: OutputFileMetadata): string | null {
  if (field.output_role === 'base') return 'Base name; this tool generates the individual filenames.'
  if (field.output_role !== 'exact') return null
  if (field.description) return field.description
  if (field.file_group?.kind === 'once') return 'One file for the whole batch.'
  if (field.file_group?.kind === 'by') return `One file per distinct ${(field.file_group.keys ?? []).join(' and ')}.`
  if (field.file_group?.kind === 'per_row') return 'One file per input row.'
  return null
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
    const field = outputFileMetadata(tool, key, rawField)
    if (!PATH_OUTPUT_TYPES.has(String(field.type ?? ''))) continue
    const current = existing[key]
    if (typeof current === 'string') {
      reconciled[key] = current
      continue
    }
    if (!isWritableOutputTemplate(field)) continue
    reconciled[key] = typeof field.default === 'string' ? field.default : ''
  }
  return reconciled
}
