import type { GraphState, InputFieldSchema, ToolMetadata, ToolNodeState, WorkflowInput } from '@/api/types'
import { decodeWorkflowConstant } from './workflowConstants'

export interface WorkflowInputPresentation {
  field: InputFieldSchema
  targets: { node: string; field: string }[]
  metadataAvailable: boolean
  canPin: boolean
}

type ToolLookup = (node: ToolNodeState, scopedId: string) => ToolMetadata | null | undefined
const hintKeys = ['description', 'group', 'min', 'max', 'step', 'choices', 'path_picker'] as const

/** A transient presentation projection; interface and leaf declarations stay authoritative. */
export function workflowInputPresentations(
  workflow: GraphState,
  scope: string,
  lookup: ToolLookup,
): Record<string, WorkflowInputPresentation> {
  function resolve(graph: GraphState, input: WorkflowInput, path: string, visited: Set<string>): {
    fields: InputFieldSchema[]; targets: { node: string; field: string }[]; complete: boolean; canPin: boolean
  } {
    const identity = `${path}:${input.id}`
    if (visited.has(identity)) return { fields: [], targets: [], complete: false, canPin: false }
    const nextVisited = new Set([...visited, identity])
    const result = { fields: [] as InputFieldSchema[], targets: [] as { node: string; field: string }[], complete: true, canPin: true }
    if (input.targets.length === 0) result.complete = result.canPin = false
    for (const target of input.targets) {
      const node = graph.nodes.find(candidate => candidate.id === target.node)
      const nodePath = `${path}/${target.node}`
      if (node?.type === 'workflow' && target.port.kind === 'workflow') {
        const portId = target.port.id
        const child = node.workflow.interface.inputs.find(port => port.id === portId && port.kind === 'field')
        if (child) {
          const nested = resolve(node.workflow, child, nodePath, nextVisited)
          result.fields.push(...nested.fields)
          result.targets.push(...nested.targets)
          result.complete &&= nested.complete
          result.canPin &&= nested.canPin
          continue
        }
      } else if (node?.type === 'tool' && target.port.kind === 'field') {
        const name = target.port.name
        result.targets.push({ node: nodePath, field: name })
        const tool = lookup(node, nodePath)
        const field = tool?.inputs[name]
        if (field) {
          result.fields.push(field)
          result.canPin &&= tool?.tool_type !== 'DataFrameTool' && field.connectable !== 'never'
          continue
        }
      }
      result.complete = result.canPin = false
    }
    return result
  }

  return Object.fromEntries(workflow.interface.inputs.filter(input => input.kind === 'field').map(input => {
    const resolved = resolve(workflow, input, scope, new Set())
    const schema = input.schema ?? {}
    const type = typeof schema.type === 'string' ? schema.type : 'any'
    const field: InputFieldSchema = {
      type, required: input.default == null, nullable: schema.nullable === true,
      connectable: resolved.canPin ? 'not_by_default' : 'never',
      display_name: input.name,
    }
    const compatible = resolved.fields.filter(target => target.type === type)
    if (resolved.complete && compatible.length === resolved.fields.length && compatible.length > 0) {
      field.nullable = typeof schema.nullable === 'boolean' ? schema.nullable : compatible.every(target => target.nullable)
      for (const key of hintKeys) {
        const first = compatible[0]![key]
        if (compatible.every(target => JSON.stringify(target[key]) === JSON.stringify(first))) {
          Object.assign(field, { [key]: first })
        }
      }
    }
    // Treat optional portable hints conservatively; malformed hints must not
    // coerce a valid authored value or change the public parameter's type.
    for (const key of hintKeys) {
      const hint = schema[key]
      if (['min', 'max', 'step'].includes(key)) {
        if (typeof hint === 'number' && Number.isFinite(hint) && (key !== 'step' || hint > 0)) Object.assign(field, { [key]: hint })
      } else if (key === 'choices') {
        if (Array.isArray(hint) && hint.every(value => typeof value === 'string')) field.choices = hint
      } else if (key === 'path_picker') {
        if (hint === 'file' || hint === 'folder' || hint === 'both') field.path_picker = hint
      } else if (typeof hint === 'string') Object.assign(field, { [key]: hint })
    }
    if (field.min != null && field.max != null && field.min > field.max) { delete field.min; delete field.max }
    const canPin = resolved.complete && compatible.length === resolved.fields.length && resolved.canPin && schema.connectable !== 'never'
    field.connectable = canPin ? 'not_by_default' : 'never'

    if (input.default != null) {
      try { field.default = decodeWorkflowConstant(input.default) } catch { /* Preserve unsupported values outside the editor. */ }
    }
    const defaultValue = field.default
    if (typeof defaultValue === 'number') {
      if (field.min != null && defaultValue < field.min) delete field.min
      if (field.max != null && defaultValue > field.max) delete field.max
    }
    if (field.choices && defaultValue != null && !field.choices.includes(String(defaultValue))) delete field.choices
    return [input.id, { field, targets: resolved.targets, metadataAvailable: resolved.complete, canPin }]
  }))
}
