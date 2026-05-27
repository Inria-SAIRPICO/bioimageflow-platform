import type {
  ColumnRefEdge,
  GraphState,
  InputFieldSchema,
  PositionalEdge,
  ToolMetadata,
} from '@/api/types'
import { generateNodeId, generateNodeName } from './nodeIdGenerator'

export interface PublishedInput {
  name: string
  internal_node_id: string
  internal_field: string
  kind: 'parameter' | 'input'
  schema?: Record<string, unknown> | null
  default?: unknown
}

export interface PublishedOutput {
  name: string
  internal_node_id: string
  internal_output: string
  schema?: Record<string, unknown> | null
}

export type ClipboardEdge = ColumnRefEdge | PositionalEdge

export interface ClipboardNode {
  id: string
  name: string
  tool_name: string
  position: [number, number]
  parameters: Record<string, unknown>
  resources?: Record<string, unknown>
  output_templates?: Record<string, string>
  enabled?: boolean
  collapsed?: boolean
  tool_package?: string
  tool_package_version?: string
  sub_workflow?: ClipboardGraphState | null
  published_inputs?: PublishedInput[]
  published_outputs?: PublishedOutput[]
  sub_workflow_readonly_reason?: string | null
  source_workflow_name?: string | null
  missing?: boolean
}

export interface ClipboardGraphState {
  nodes: ClipboardNode[]
  edges: ClipboardEdge[]
}

export interface ClipboardPayload extends ClipboardGraphState {
  bioimageflow_clipboard: true
  clipboard_version: 1 | 2
  source_workflow_name?: string
  source_workflow_id?: string
  created_at?: string
}

export type ClipboardData = ClipboardPayload

export type ParseClipboardResult =
  | { kind: 'valid'; payload: ClipboardPayload }
  | { kind: 'legacy'; payload: ClipboardPayload }
  | { kind: 'invalid'; reason: string }
  | { kind: 'unsupported_version'; version: unknown }

export type ReadClipboardResult =
  | ParseClipboardResult
  | { kind: 'empty' }

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
const CLIPBOARD_VERSION = 2
const SUB_WORKFLOW_TOOL_NAME = '__sub_workflow__'

let memoryClipboardPayload: ClipboardPayload | null = null

function deepClone<T>(value: T): T {
  if (value === undefined) return value
  return JSON.parse(JSON.stringify(value)) as T
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasOwn(value: object, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(value, key)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isLegacyEdge(value: unknown): value is Omit<ColumnRefEdge, 'type'> {
  return isRecord(value)
    && typeof value.id === 'string'
    && typeof value.source_node === 'string'
    && typeof value.target_node === 'string'
    && typeof value.source_output === 'string'
    && typeof value.target_input === 'string'
    && value.type === undefined
}

function isClipboardEdge(value: unknown): value is ClipboardEdge {
  if (!isRecord(value)) return false
  if (
    value.type === 'column_ref'
    && typeof value.id === 'string'
    && typeof value.source_node === 'string'
    && typeof value.target_node === 'string'
    && typeof value.source_output === 'string'
    && typeof value.target_input === 'string'
  ) {
    return true
  }
  return value.type === 'positional'
    && typeof value.id === 'string'
    && typeof value.source_node === 'string'
    && typeof value.target_node === 'string'
    && typeof value.positional_index === 'number'
}

function isClipboardNode(value: unknown): value is ClipboardNode {
  return isRecord(value)
    && typeof value.id === 'string'
    && typeof value.name === 'string'
    && typeof value.tool_name === 'string'
    && Array.isArray(value.position)
    && value.position.length === 2
    && typeof value.position[0] === 'number'
    && typeof value.position[1] === 'number'
    && isRecord(value.parameters)
}

function normalizeEdge(raw: unknown): ClipboardEdge | null {
  if (isClipboardEdge(raw)) return deepClone(raw)
  if (isLegacyEdge(raw)) {
    return {
      type: 'column_ref',
      id: raw.id,
      source_node: raw.source_node,
      target_node: raw.target_node,
      source_output: raw.source_output,
      target_input: raw.target_input,
    }
  }
  return null
}

function normalizeNode(raw: unknown): ClipboardNode | null {
  if (!isClipboardNode(raw)) return null
  const cloned = deepClone(raw)
  if (cloned.sub_workflow !== undefined && cloned.sub_workflow !== null) {
    const normalizedNested = normalizeGraphLike(cloned.sub_workflow)
    if (normalizedNested === null) return null
    cloned.sub_workflow = normalizedNested
  }
  return cloned
}

function normalizeGraphLike(raw: unknown): ClipboardGraphState | null {
  if (!isRecord(raw) || !Array.isArray(raw.nodes) || !Array.isArray(raw.edges)) {
    return null
  }
  const nodes = raw.nodes.map(normalizeNode)
  const edges = raw.edges.map(normalizeEdge)
  if (nodes.some((node) => node === null) || edges.some((edge) => edge === null)) {
    return null
  }
  return {
    nodes: nodes as ClipboardNode[],
    edges: edges as ClipboardEdge[],
  }
}

export function normalizeClipboardPayload(raw: unknown): ClipboardPayload {
  const graph = normalizeGraphLike(raw)
  if (graph === null || !isRecord(raw)) {
    throw new Error('Clipboard payload must contain nodes and edges arrays')
  }

  const hasMarker = hasOwn(raw, 'bioimageflow_clipboard')
  const hasVersion = hasOwn(raw, 'clipboard_version')
  const isMarked = raw.bioimageflow_clipboard === true
  const version = raw.clipboard_version

  if (isMarked) {
    if (version !== 1 && version !== CLIPBOARD_VERSION) {
      throw new Error(`Unsupported clipboard version: ${String(version)}`)
    }
    return {
      ...graph,
      bioimageflow_clipboard: true,
      clipboard_version: version,
      source_workflow_name: typeof raw.source_workflow_name === 'string'
        ? raw.source_workflow_name
        : undefined,
      source_workflow_id: typeof raw.source_workflow_id === 'string'
        ? raw.source_workflow_id
        : undefined,
      created_at: typeof raw.created_at === 'string' ? raw.created_at : undefined,
    }
  }

  if (hasMarker || hasVersion) {
    throw new Error('Clipboard payload is missing BioImageFlow clipboard marker')
  }

  const rawEdges = raw.edges as unknown[]
  const edgesAreLegacy = rawEdges.every((edge) => isLegacyEdge(edge))
  if (!edgesAreLegacy) {
    throw new Error('Clipboard payload is missing BioImageFlow clipboard marker')
  }

  return {
    ...graph,
    bioimageflow_clipboard: true,
    clipboard_version: 1,
  }
}

export function parseClipboardText(text: string): ParseClipboardResult {
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    return { kind: 'invalid', reason: 'Clipboard does not contain valid JSON' }
  }

  if (!isRecord(raw)) {
    return { kind: 'invalid', reason: 'Clipboard does not contain BioImageFlow nodes' }
  }

  if (raw.bioimageflow_clipboard === true
      && raw.clipboard_version !== 1
      && raw.clipboard_version !== CLIPBOARD_VERSION) {
    return { kind: 'unsupported_version', version: raw.clipboard_version }
  }

  try {
    const payload = normalizeClipboardPayload(raw)
    return payload.clipboard_version === 1
      ? { kind: 'legacy', payload }
      : { kind: 'valid', payload }
  } catch (error) {
    return {
      kind: 'invalid',
      reason: error instanceof Error
        ? error.message
        : 'Clipboard does not contain BioImageFlow nodes',
    }
  }
}

export function serializeGraphSelection(
  graph: GraphState | ClipboardGraphState,
  selectedIds: Set<string>,
  getToolByName: (name: string) => ToolMetadata | undefined,
  options: { sourceWorkflowName?: string; sourceWorkflowId?: string } = {},
): ClipboardPayload {
  const selectedNodes = graph.nodes
    .filter((node) => selectedIds.has(node.id))
    .map((node) => {
      const copied = deepClone(node as ClipboardNode)
      delete copied.missing
      const tool = getToolByName(copied.tool_name)
      if (tool) {
        copied.tool_package = tool.package
        copied.tool_package_version = tool.package_version
      }
      return copied
    })

  const selectedEdges = graph.edges
    .filter((edge) => selectedIds.has(edge.source_node) && selectedIds.has(edge.target_node))
    .map((edge) => normalizeEdge(edge)!)

  return {
    bioimageflow_clipboard: true,
    clipboard_version: CLIPBOARD_VERSION,
    source_workflow_name: options.sourceWorkflowName,
    source_workflow_id: options.sourceWorkflowId,
    created_at: new Date().toISOString(),
    nodes: selectedNodes,
    edges: selectedEdges,
  }
}

export function serializeSelection(
  nodes: ClipboardNode[],
  edges: ClipboardEdge[],
  selectedIds: Set<string>,
): ClipboardPayload {
  return serializeGraphSelection({ nodes, edges }, selectedIds, () => undefined)
}

function fieldHasDefault(field: InputFieldSchema): boolean {
  return hasOwn(field, 'default')
}

function cloneDefault(field: InputFieldSchema): unknown {
  return fieldHasDefault(field) ? deepClone(field.default) : undefined
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
  if (
    normalized === 'str'
    || normalized === 'string'
    || normalized === 'path'
    || normalized === 'imagepath'
    || normalized === 'maskpath'
    || normalized === 'filepath'
    || normalized === 'dirpath'
  ) {
    return typeof value === 'string'
  }
  if (normalized === 'array' || normalized === 'list') return Array.isArray(value)
  if (normalized === 'object' || normalized === 'dict' || normalized === 'record') {
    return isRecord(value)
  }
  return true
}

function valueFitsField(value: unknown, field: InputFieldSchema): boolean {
  if (value === null) return field.nullable
  if (!typeAllowsValue(field.type, value)) return false
  if (isStringArray(field.choices) && !field.choices.includes(String(value))) return false
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
  const parameters: Record<string, unknown> = {}
  const kept: string[] = []
  const reset: string[] = []
  const removed: string[] = []
  const omittedRequired: string[] = []
  const warnings: string[] = []

  for (const [key, value] of Object.entries(pastedParameters)) {
    const field = inputs[key]
    if (!field) {
      removed.push(key)
      continue
    }
    if (valueFitsField(value, field)) {
      parameters[key] = deepClone(value)
      kept.push(key)
      continue
    }
    if (fieldHasDefault(field)) {
      parameters[key] = cloneDefault(field)
      reset.push(key)
      warnings.push(`${key} reset to default`)
      continue
    }
    if (field.required) {
      omittedRequired.push(key)
      warnings.push(`${key} omitted because it is required and has no default`)
      continue
    }
    removed.push(key)
  }

  return {
    parameters,
    kept,
    reset,
    removed,
    omitted_required: omittedRequired,
    warnings,
  }
}

function emptyPasteSummary(): PasteSummary {
  return {
    missingTools: [],
    versionMismatches: [],
    parameterResets: [],
    removedParameters: [],
    omittedRequiredParameters: [],
    warnings: [],
  }
}

function baseNameForPaste(node: ClipboardNode): string {
  return node.name.replace(/\s+\d+$/, '') || node.name
}

function reconcileSubWorkflowGraph(
  graph: ClipboardGraphState,
  getToolByName: (name: string) => ToolMetadata | undefined,
  summary: PasteSummary,
): ClipboardGraphState {
  const keptNodes: ClipboardNode[] = []
  const keptIds = new Set<string>()

  for (const node of graph.nodes) {
    const prepared = prepareNodeForTarget(node, getToolByName, summary, false)
    if (!prepared) continue
    keptNodes.push(prepared)
    keptIds.add(prepared.id)
  }

  return {
    nodes: keptNodes,
    edges: graph.edges
      .filter((edge) => keptIds.has(edge.source_node) && keptIds.has(edge.target_node))
      .map((edge) => deepClone(edge)),
  }
}

function prepareSubWorkflowParameters(node: ClipboardNode): Record<string, unknown> {
  if (!node.published_inputs) return deepClone(node.parameters ?? {})
  const publishedNames = new Set(node.published_inputs.map((input) => input.name))
  return Object.fromEntries(
    Object.entries(node.parameters ?? {})
      .filter(([key]) => publishedNames.has(key))
      .map(([key, value]) => [key, deepClone(value)]),
  )
}

function prepareNodeForTarget(
  node: ClipboardNode,
  getToolByName: (name: string) => ToolMetadata | undefined,
  summary: PasteSummary,
  renameRoot: boolean,
  allIds: string[] = [],
  allNames: string[] = [],
  offset: [number, number] = PASTE_OFFSET,
): ClipboardNode | null {
  const isSubWorkflow = node.tool_name === SUB_WORKFLOW_TOOL_NAME && node.sub_workflow
  const tool = isSubWorkflow ? undefined : getToolByName(node.tool_name)

  if (!isSubWorkflow && !tool) {
    summary.missingTools.push(node.tool_name)
    return null
  }

  const prepared: ClipboardNode = deepClone(node)
  if (renameRoot) {
    const newId = generateNodeId(node.tool_name, allIds)
    allIds.push(newId)
    prepared.id = newId
    const newName = generateNodeName(node.tool_name, allNames, baseNameForPaste(node))
    allNames.push(newName)
    prepared.name = newName
    prepared.position = [
      node.position[0] + offset[0],
      node.position[1] + offset[1],
    ]
  }

  delete prepared.missing

  if (isSubWorkflow) {
    prepared.parameters = prepareSubWorkflowParameters(node)
    prepared.sub_workflow = reconcileSubWorkflowGraph(
      node.sub_workflow!,
      getToolByName,
      summary,
    )
    return prepared
  }

  const activeTool = tool!
  const packageMismatch = Boolean(
    node.tool_package && node.tool_package !== activeTool.package,
  )
  const versionMismatch = Boolean(
    node.tool_package_version
      && node.tool_package_version !== activeTool.package_version,
  )
  if (packageMismatch || versionMismatch) {
    summary.versionMismatches.push({
      nodeName: node.name,
      packageName: node.tool_package ?? activeTool.package,
      sourceVersion: node.tool_package_version,
      targetVersion: activeTool.package_version,
    })
  }

  const reconciled = reconcileParameters(node.parameters ?? {}, activeTool.inputs)
  prepared.parameters = reconciled.parameters
  if (reconciled.reset.length > 0) {
    summary.parameterResets.push({ nodeName: node.name, fields: reconciled.reset })
  }
  if (reconciled.removed.length > 0) {
    summary.removedParameters.push({ nodeName: node.name, fields: reconciled.removed })
  }
  if (reconciled.omitted_required.length > 0) {
    summary.omittedRequiredParameters.push({
      nodeName: node.name,
      fields: reconciled.omitted_required,
    })
  }
  summary.warnings.push(...reconciled.warnings)
  return prepared
}

export function prepareClipboardPaste(
  payload: ClipboardPayload,
  options: PreparePasteOptions,
): PreparedPaste {
  const summary = emptyPasteSummary()
  const idMap = new Map<string, string>()
  const allIds = [...options.existingIds]
  const allNames = [...options.existingNames]
  const allEdgeIds = new Set(options.existingEdgeIds ?? [])
  const offset = options.offset ?? PASTE_OFFSET
  const edgeIdGenerator = options.edgeIdGenerator
    ?? ((_edge: ClipboardEdge, index: number) => `pasted_edge_${index}`)

  const nodes: ClipboardNode[] = []
  for (const node of payload.nodes) {
    const prepared = prepareNodeForTarget(
      node,
      options.getToolByName,
      summary,
      true,
      allIds,
      allNames,
      offset,
    )
    if (!prepared) continue
    nodes.push(prepared)
    idMap.set(node.id, prepared.id)
  }

  let edgeCounter = 0
  const edges: ClipboardEdge[] = []
  for (const edge of payload.edges) {
    const source = idMap.get(edge.source_node)
    const target = idMap.get(edge.target_node)
    if (!source || !target) continue
    edgeCounter += 1
    let edgeId = edgeIdGenerator(edge, edgeCounter)
    while (allEdgeIds.has(edgeId)) {
      edgeCounter += 1
      edgeId = edgeIdGenerator(edge, edgeCounter)
    }
    allEdgeIds.add(edgeId)
    edges.push({
      ...deepClone(edge),
      id: edgeId,
      source_node: source,
      target_node: target,
    } as ClipboardEdge)
  }

  return { nodes, edges, summary }
}

export function deserializeSelection(
  clipboard: ClipboardPayload | ClipboardGraphState,
  existingIds: string[],
  existingNames: string[],
): ClipboardGraphState {
  let payload: ClipboardPayload
  try {
    payload = normalizeClipboardPayload(clipboard)
  } catch {
    const graph = normalizeGraphLike(clipboard)
    if (graph === null) throw new Error('Clipboard payload must contain nodes and edges arrays')
    payload = {
      ...graph,
      bioimageflow_clipboard: true,
      clipboard_version: 1,
    }
  }
  const prepared = prepareClipboardPaste(payload, {
    existingIds,
    existingNames,
    getToolByName: (name) => ({
      name,
      display_name: name,
      package: '',
      package_version: '',
      tool_type: 'ProcessingTool',
      accepts_upstream: true,
      dynamic_outputs: false,
      documentation: '',
      tags: [],
      categories: [],
      inputs: {},
      outputs: {},
      environment: null,
    }),
  })
  return { nodes: prepared.nodes, edges: prepared.edges }
}

export async function writeClipboardPayload(payload: ClipboardPayload): Promise<void> {
  memoryClipboardPayload = deepClone(payload)
  const text = JSON.stringify(payload)
  try {
    await globalThis.navigator?.clipboard?.writeText?.(text)
  } catch {
    // Browser permission denial is expected in tests and some desktop shells.
  }
}

export async function readClipboardPayloadResult(): Promise<ReadClipboardResult> {
  try {
    const text = await globalThis.navigator?.clipboard?.readText?.()
    if (typeof text === 'string' && text.length > 0) {
      const parsed = parseClipboardText(text)
      if (parsed.kind === 'valid' || parsed.kind === 'legacy') {
        memoryClipboardPayload = deepClone(parsed.payload)
      }
      return parsed
    }
  } catch {
    // Fall back to the last in-memory payload.
  }
  return memoryClipboardPayload
    ? { kind: 'valid', payload: deepClone(memoryClipboardPayload) }
    : { kind: 'empty' }
}

export async function readClipboardPayload(): Promise<ClipboardPayload | null> {
  const result = await readClipboardPayloadResult()
  return result.kind === 'valid' || result.kind === 'legacy'
    ? result.payload
    : null
}

export function getMemoryClipboardPayload(): ClipboardPayload | null {
  return memoryClipboardPayload ? deepClone(memoryClipboardPayload) : null
}

export function _resetClipboardForTest(): void {
  memoryClipboardPayload = null
}
