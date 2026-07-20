import type {
  GraphState,
  InputFieldSchema,
  ToolMetadata,
  ToolNodeState,
  WorkflowNodeState,
} from '@/api/types'
import { generateNodeId, generateNodeName } from './nodeIdGenerator'

export type ClipboardEdge = GraphState['edges'][number]
export type ClipboardNode = ToolNodeState | WorkflowNodeState

export interface ClipboardPayload {
  bioimageflow_clipboard: true
  clipboard_version: 1
  nodes: ClipboardNode[]
  edges: ClipboardEdge[]
  source_workflow_id?: string
  created_at: string
}

export type ClipboardData = ClipboardPayload

export type ParseClipboardResult =
  | { kind: 'valid'; payload: ClipboardPayload }
  | { kind: 'invalid'; reason: string }
  | { kind: 'unsupported_version'; version: unknown }

export type ReadClipboardResult = ParseClipboardResult | { kind: 'empty' }

export interface ReconcileSummary {
  kept: string[]
  reset: string[]
  removed: string[]
  omitted_required: string[]
  warnings: string[]
}

export interface ReconcileResult extends ReconcileSummary {
  parameters: Record<string, unknown>
}

export interface PasteSummary {
  missingTools: string[]
  versionMismatches: Array<{
    nodeName: string
    packageName?: string
    sourceVersion?: string
    targetVersion?: string
  }>
  parameterResets: Array<{ nodeName: string; fields: string[] }>
  removedParameters: Array<{ nodeName: string; fields: string[] }>
  omittedRequiredParameters: Array<{ nodeName: string; fields: string[] }>
  warnings: string[]
}

export interface PreparedPaste {
  nodes: ClipboardNode[]
  edges: ClipboardEdge[]
  summary: PasteSummary
}

export interface PreparePasteOptions {
  existingIds: string[]
  existingNames: string[]
  existingEdgeIds?: string[]
  getToolByName: (name: string) => ToolMetadata | undefined
  offset?: [number, number]
  edgeIdGenerator?: (edge: ClipboardEdge, index: number) => string
}

const PASTE_OFFSET: [number, number] = [50, 50]
let memoryClipboardPayload: ClipboardPayload | null = null

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isNode(value: unknown): value is ClipboardNode {
  return isRecord(value)
    && (value.type === 'tool' || value.type === 'workflow')
    && typeof value.id === 'string'
    && typeof value.name === 'string'
    && Array.isArray(value.position)
}

function isEdge(value: unknown): value is ClipboardEdge {
  if (!isRecord(value) || typeof value.id !== 'string') return false
  if (value.type === 'column') {
    return typeof value.source_node === 'string'
      && typeof value.target_node === 'string'
      && typeof value.source_output === 'string'
      && typeof value.target_input === 'string'
  }
  return value.type === 'dataframe'
    && typeof value.source_node === 'string'
    && typeof value.target_node === 'string'
}

export function normalizeClipboardPayload(raw: unknown): ClipboardPayload {
  if (!isRecord(raw) || raw.bioimageflow_clipboard !== true) {
    throw new Error('Clipboard payload has no BioImageFlow marker')
  }
  if (raw.clipboard_version !== 1) {
    throw new Error(`Unsupported clipboard version: ${String(raw.clipboard_version)}`)
  }
  if (!Array.isArray(raw.nodes) || !raw.nodes.every(isNode)) {
    throw new Error('Clipboard payload has invalid nodes')
  }
  if (!Array.isArray(raw.edges) || !raw.edges.every(isEdge)) {
    throw new Error('Clipboard payload has invalid edges')
  }
  if (typeof raw.created_at !== 'string') {
    throw new Error('Clipboard payload has no creation timestamp')
  }
  return clone(raw as unknown as ClipboardPayload)
}

export function parseClipboardText(text: string): ParseClipboardResult {
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    return { kind: 'invalid', reason: 'Clipboard does not contain valid JSON' }
  }
  if (isRecord(raw)
    && raw.bioimageflow_clipboard === true
    && raw.clipboard_version !== 1) {
    return { kind: 'unsupported_version', version: raw.clipboard_version }
  }
  try {
    return { kind: 'valid', payload: normalizeClipboardPayload(raw) }
  } catch (error) {
    return {
      kind: 'invalid',
      reason: error instanceof Error ? error.message : 'Clipboard payload is invalid',
    }
  }
}

export function serializeGraphSelection(
  graph: Pick<GraphState, 'nodes' | 'edges'>,
  selectedIds: Set<string>,
  _getToolByName: (name: string) => ToolMetadata | undefined,
  options: { sourceWorkflowId?: string } = {},
): ClipboardPayload {
  return {
    bioimageflow_clipboard: true,
    clipboard_version: 1,
    source_workflow_id: options.sourceWorkflowId,
    created_at: new Date().toISOString(),
    nodes: clone(graph.nodes.filter(node => selectedIds.has(node.id))),
    edges: clone(graph.edges.filter(edge => (
      selectedIds.has(edge.source_node) && selectedIds.has(edge.target_node)
    ))),
  }
}

export function serializeSelection(
  nodes: ClipboardNode[],
  edges: ClipboardEdge[],
  selectedIds: Set<string>,
): ClipboardPayload {
  return serializeGraphSelection({ nodes, edges }, selectedIds, () => undefined)
}

function hasDefault(field: InputFieldSchema): boolean {
  return Object.prototype.hasOwnProperty.call(field, 'default')
}

function typeAllowsValue(type: string, value: unknown): boolean {
  const normalized = type.toLowerCase()
  if (normalized === 'any' || normalized === 'unknown') return true
  if (normalized === 'bool' || normalized === 'boolean') return typeof value === 'boolean'
  if (normalized === 'int' || normalized === 'integer') {
    return typeof value === 'number' && Number.isInteger(value)
  }
  if (normalized === 'float' || normalized === 'number') {
    return typeof value === 'number' && Number.isFinite(value)
  }
  if (['str', 'string', 'path', 'imagepath', 'maskpath', 'filepath', 'dirpath']
    .includes(normalized)) return typeof value === 'string'
  if (normalized === 'array' || normalized === 'list') return Array.isArray(value)
  if (['object', 'dict', 'record'].includes(normalized)) return isRecord(value)
  return true
}

function valueFitsField(value: unknown, field: InputFieldSchema): boolean {
  if (value === null) return field.nullable
  if (!typeAllowsValue(field.type, value)) return false
  if (Array.isArray(field.choices) && !field.choices.includes(String(value))) return false
  if (typeof value === 'number') {
    if (typeof field.min === 'number' && value < field.min) return false
    if (typeof field.max === 'number' && value > field.max) return false
  }
  return true
}

export function reconcileParameters(
  pastedParameters: Record<string, unknown>,
  inputs: ToolMetadata['inputs'],
): ReconcileResult {
  const result: ReconcileResult = {
    parameters: {},
    kept: [],
    reset: [],
    removed: [],
    omitted_required: [],
    warnings: [],
  }
  for (const [key, value] of Object.entries(pastedParameters)) {
    const field = inputs[key]
    if (!field) {
      result.removed.push(key)
    } else if (valueFitsField(value, field)) {
      result.parameters[key] = clone(value)
      result.kept.push(key)
    } else if (hasDefault(field)) {
      result.parameters[key] = clone(field.default)
      result.reset.push(key)
      result.warnings.push(`${key} reset to default`)
    } else if (field.required) {
      result.omitted_required.push(key)
      result.warnings.push(`${key} omitted because it is required and has no default`)
    } else {
      result.removed.push(key)
    }
  }
  return result
}

function emptySummary(): PasteSummary {
  return {
    missingTools: [],
    versionMismatches: [],
    parameterResets: [],
    removedParameters: [],
    omittedRequiredParameters: [],
    warnings: [],
  }
}

function reconcileToolNode(
  node: ToolNodeState,
  getToolByName: PreparePasteOptions['getToolByName'],
  summary: PasteSummary,
): ToolNodeState {
  const tool = getToolByName(node.tool_name)
  if (!tool) {
    summary.missingTools.push(node.tool_name)
    return clone(node)
  }
  if ((node.tool_package && node.tool_package !== tool.package)
    || (node.tool_package_version && node.tool_package_version !== tool.package_version)) {
    summary.versionMismatches.push({
      nodeName: node.name,
      packageName: node.tool_package ?? tool.package,
      sourceVersion: node.tool_package_version ?? undefined,
      targetVersion: tool.package_version,
    })
  }
  const reconciled = reconcileParameters(node.parameters, tool.inputs)
  if (reconciled.reset.length) {
    summary.parameterResets.push({ nodeName: node.name, fields: reconciled.reset })
  }
  if (reconciled.removed.length) {
    summary.removedParameters.push({ nodeName: node.name, fields: reconciled.removed })
  }
  if (reconciled.omitted_required.length) {
    summary.omittedRequiredParameters.push({
      nodeName: node.name,
      fields: reconciled.omitted_required,
    })
  }
  summary.warnings.push(...reconciled.warnings)
  return { ...clone(node), parameters: reconciled.parameters }
}

export function prepareClipboardPaste(
  payload: ClipboardPayload,
  options: PreparePasteOptions,
): PreparedPaste {
  const summary = emptySummary()
  const allIds = [...options.existingIds]
  const allNames = [...options.existingNames]
  const idMap = new Map<string, string>()
  const offset = options.offset ?? PASTE_OFFSET
  const nodes = payload.nodes.map((original) => {
    const node = original.type === 'tool'
      ? reconcileToolNode(original, options.getToolByName, summary)
      : clone(original)
    const idSeed = node.type === 'tool' ? node.tool_name : 'workflow'
    const id = generateNodeId(idSeed, allIds)
    allIds.push(id)
    const name = generateNodeName(idSeed, allNames, node.name.replace(/\s+\d+$/, ''))
    allNames.push(name)
    idMap.set(original.id, id)
    return {
      ...node,
      id,
      name,
      position: [node.position[0] + offset[0], node.position[1] + offset[1]],
    } as ClipboardNode
  })

  const edgeIds = new Set(options.existingEdgeIds ?? [])
  let counter = 0
  const edges = payload.edges.map((original) => {
    let id: string
    do {
      counter += 1
      id = options.edgeIdGenerator?.(original, counter) ?? `pasted_edge_${counter}`
    } while (edgeIds.has(id))
    edgeIds.add(id)
    return {
      ...clone(original),
      id,
      source_node: idMap.get(original.source_node)!,
      target_node: idMap.get(original.target_node)!,
    }
  })
  return { nodes, edges, summary }
}

export function deserializeSelection(
  clipboard: ClipboardPayload,
  existingIds: string[],
  existingNames: string[],
): Pick<GraphState, 'nodes' | 'edges'> {
  const prepared = prepareClipboardPaste(normalizeClipboardPayload(clipboard), {
    existingIds,
    existingNames,
    getToolByName: () => undefined,
  })
  return { nodes: prepared.nodes, edges: prepared.edges }
}

export async function writeClipboardPayload(payload: ClipboardPayload): Promise<void> {
  memoryClipboardPayload = clone(payload)
  try {
    await globalThis.navigator?.clipboard?.writeText?.(JSON.stringify(payload))
  } catch {
    // Browser permission denial falls back to the in-memory clipboard.
  }
}

export async function readClipboardPayloadResult(): Promise<ReadClipboardResult> {
  try {
    const text = await globalThis.navigator?.clipboard?.readText?.()
    if (text) {
      const result = parseClipboardText(text)
      if (result.kind === 'valid') memoryClipboardPayload = clone(result.payload)
      return result
    }
  } catch {
    // Browser permission denial falls back to the in-memory clipboard.
  }
  return memoryClipboardPayload
    ? { kind: 'valid', payload: clone(memoryClipboardPayload) }
    : { kind: 'empty' }
}

export async function readClipboardPayload(): Promise<ClipboardPayload | null> {
  const result = await readClipboardPayloadResult()
  return result.kind === 'valid' ? result.payload : null
}

export function getMemoryClipboardPayload(): ClipboardPayload | null {
  return memoryClipboardPayload ? clone(memoryClipboardPayload) : null
}

export function _resetClipboardForTest(): void {
  memoryClipboardPayload = null
}
