import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ToolMetadata } from '@/api/types'
import type { ClipboardEdge, ClipboardNode, ClipboardPayload } from '../clipboard'
import {
  _resetClipboardForTest,
  deserializeSelection,
  normalizeClipboardPayload,
  parseClipboardText,
  prepareClipboardPaste,
  readClipboardPayload,
  readClipboardPayloadResult,
  reconcileParameters,
  serializeGraphSelection,
  serializeSelection,
  writeClipboardPayload,
} from '../clipboard'

const makeNode = (id: string, x = 0, y = 0): ClipboardNode => ({
  id,
  name: `Node ${id}`,
  tool_name: `tool_${id}`,
  position: [x, y],
  parameters: { a: 1 },
  resources: { file: '/tmp/a.tif' },
  output_templates: { result: '{name}.tif' },
  enabled: false,
  collapsed: true,
})

const makeColumnEdge = (id: string, source: string, target: string): ClipboardEdge => ({
  type: 'column_ref',
  id,
  source_node: source,
  target_node: target,
  source_output: 'output',
  target_input: 'input',
})

const makeTool = (overrides: Partial<ToolMetadata> = {}): ToolMetadata => ({
  name: 'tool_a',
  display_name: 'Tool A',
  package: 'bioimageflow-core',
  package_version: '1.2.0',
  tool_type: 'ProcessingTool',
  accepts_upstream: true,
  dynamic_outputs: false,
  documentation: '',
  tags: [],
  categories: [],
  inputs: {
    a: { type: 'int', required: false, nullable: false, connectable: 'never', default: 1 },
  },
  outputs: {},
  environment: null,
  ...overrides,
})

describe('parseClipboardText', () => {
  it('rejects malformed JSON and wrong root shapes', () => {
    expect(parseClipboardText('{').kind).toBe('invalid')
    expect(parseClipboardText('[]').kind).toBe('invalid')
  })

  it('parses v2 payloads with positional edges and sub-workflow fields', () => {
    const payload: ClipboardPayload = {
      bioimageflow_clipboard: true,
      clipboard_version: 2,
      nodes: [{
        ...makeNode('a'),
        sub_workflow: { nodes: [makeNode('inner')], edges: [] },
        published_inputs: [{
          name: 'threshold',
          internal_node_id: 'inner',
          internal_field: 'a',
          kind: 'parameter',
          schema: null,
          default: 1,
        }],
        published_outputs: [{
          name: 'result',
          internal_node_id: 'inner',
          internal_output: 'out',
          schema: null,
        }],
        sub_workflow_readonly_reason: 'library node',
      }],
      edges: [{
        type: 'positional',
        id: 'e1',
        source_node: 'a',
        target_node: 'b',
        positional_index: 2,
      }],
    }

    const parsed = parseClipboardText(JSON.stringify(payload))

    expect(parsed.kind).toBe('valid')
    if (parsed.kind !== 'valid') return
    expect(parsed.payload.edges[0]).toMatchObject({ type: 'positional', positional_index: 2 })
    expect(parsed.payload.nodes[0].published_inputs?.[0].name).toBe('threshold')
  })

  it('reports unsupported versions', () => {
    const parsed = parseClipboardText(JSON.stringify({
      bioimageflow_clipboard: true,
      clipboard_version: 99,
      nodes: [],
      edges: [],
    }))

    expect(parsed.kind).toBe('unsupported_version')
  })

  it('rejects payloads with an explicit wrong marker instead of treating them as legacy', () => {
    const parsed = parseClipboardText(JSON.stringify({
      bioimageflow_clipboard: false,
      nodes: [makeNode('a')],
      edges: [{
        id: 'e1',
        source_node: 'a',
        target_node: 'a',
        source_output: 'x',
        target_input: 'y',
      }],
    }))

    expect(parsed.kind).toBe('invalid')
  })

  it('upgrades legacy same-workflow payloads without mutating the caller data', () => {
    const legacy = {
      nodes: [makeNode('a')],
      edges: [{ id: 'e1', source_node: 'a', target_node: 'b', source_output: 'x', target_input: 'y' }],
    }

    const normalized = normalizeClipboardPayload(legacy)

    expect(normalized.clipboard_version).toBe(1)
    expect(normalized.edges[0]).toMatchObject({ type: 'column_ref' })
    expect((legacy.edges[0] as any).type).toBeUndefined()
  })
})

describe('serializeGraphSelection', () => {
  it('serializes selected graph nodes with package metadata and internal edges only', () => {
    const graph = {
      nodes: [makeNode('a'), makeNode('b'), makeNode('c')],
      edges: [
        makeColumnEdge('e1', 'a', 'b'),
        makeColumnEdge('e2', 'a', 'c'),
        { type: 'positional' as const, id: 'e3', source_node: 'b', target_node: 'a', positional_index: 1 },
      ],
    }

    const payload = serializeGraphSelection(
      graph,
      new Set(['a', 'b']),
      (name) => (name === 'tool_a' ? makeTool() : undefined),
      { sourceWorkflowName: 'source' },
    )

    expect(payload.bioimageflow_clipboard).toBe(true)
    expect(payload.clipboard_version).toBe(2)
    expect(payload.source_workflow_name).toBe('source')
    expect(payload.nodes.map((node) => node.id)).toEqual(['a', 'b'])
    expect(payload.nodes[0]).toMatchObject({
      tool_package: 'bioimageflow-core',
      tool_package_version: '1.2.0',
      resources: { file: '/tmp/a.tif' },
      output_templates: { result: '{name}.tif' },
      enabled: false,
      collapsed: true,
    })
    expect(payload.edges.map((edge) => edge.id)).toEqual(['e1', 'e3'])
    expect(payload.edges[1]).toMatchObject({ type: 'positional', positional_index: 1 })
  })
})

describe('reconcileParameters', () => {
  it('keeps valid values and resets invalid optional values to defaults', () => {
    const tool = makeTool({
      inputs: {
        keep_bool: { type: 'bool', required: false, nullable: false, connectable: 'never', default: false },
        bounded_int: { type: 'int', required: false, nullable: false, connectable: 'never', default: 3, min: 1, max: 5 },
        choice: { type: 'str', required: false, nullable: false, connectable: 'never', default: 'a', choices: ['a', 'b'] },
        nullable_text: { type: 'str', required: false, nullable: true, connectable: 'never', default: null },
        required_text: { type: 'str', required: true, nullable: false, connectable: 'never' },
        path: { type: 'Path', required: false, nullable: false, connectable: 'never', default: '/tmp' },
      },
    })

    const result = reconcileParameters({
      keep_bool: true,
      bounded_int: 9,
      choice: 'z',
      nullable_text: null,
      required_text: 42,
      unknown: 'drop',
      path: '/data/image.tif',
    }, tool.inputs)

    expect(result.parameters).toEqual({
      keep_bool: true,
      bounded_int: 3,
      choice: 'a',
      nullable_text: null,
      path: '/data/image.tif',
    })
    expect(result.kept).toEqual(['keep_bool', 'nullable_text', 'path'])
    expect(result.reset).toEqual(['bounded_int', 'choice'])
    expect(result.removed).toEqual(['unknown'])
    expect(result.omitted_required).toEqual(['required_text'])
  })

  it('accepts arrays and objects for matching schema types', () => {
    const tool = makeTool({
      inputs: {
        values: { type: 'array', required: false, nullable: false, connectable: 'never', default: [] },
        config: { type: 'object', required: false, nullable: false, connectable: 'never', default: {} },
      },
    })

    const result = reconcileParameters({ values: [1, 2], config: { a: 1 } }, tool.inputs)

    expect(result.parameters).toEqual({ values: [1, 2], config: { a: 1 } })
  })
})

describe('prepareClipboardPaste', () => {
  it('generates unique IDs and deterministic edge IDs while preserving positional edges and state', () => {
    const payload: ClipboardPayload = {
      bioimageflow_clipboard: true,
      clipboard_version: 2,
      nodes: [makeNode('a', 10, 20), { ...makeNode('b', 30, 40), tool_name: 'tool_a' }],
      edges: [
        makeColumnEdge('edge', 'a', 'b'),
        { type: 'positional', id: 'edge', source_node: 'b', target_node: 'a', positional_index: 0 },
      ],
    }

    const result = prepareClipboardPaste(payload, {
      existingIds: ['tool_a_1'],
      existingNames: ['Node a 1'],
      getToolByName: () => makeTool(),
    })

    expect(result.nodes).toHaveLength(2)
    expect(result.nodes[0].id).not.toBe('a')
    expect(result.nodes[0].position).toEqual([60, 70])
    expect(result.nodes[0].enabled).toBe(false)
    expect(result.nodes[0].collapsed).toBe(true)
    expect(result.edges).toEqual([
      expect.objectContaining({ id: 'pasted_edge_1', type: 'column_ref' }),
      expect.objectContaining({ id: 'pasted_edge_2', type: 'positional', positional_index: 0 }),
    ])
  })

  it('omits missing tools and drops edges connected to omitted nodes', () => {
    const payload: ClipboardPayload = {
      bioimageflow_clipboard: true,
      clipboard_version: 2,
      nodes: [makeNode('a'), { ...makeNode('b'), tool_name: 'missing' }],
      edges: [makeColumnEdge('e1', 'a', 'b')],
    }

    const result = prepareClipboardPaste(payload, {
      existingIds: [],
      existingNames: [],
      getToolByName: (name) => (name === 'tool_a' ? makeTool() : undefined),
    })

    expect(result.nodes.map((node) => node.tool_name)).toEqual(['tool_a'])
    expect(result.edges).toEqual([])
    expect(result.summary.missingTools).toEqual(['missing'])
  })

  it('regenerates pasted edge IDs without colliding with existing edge IDs', () => {
    const payload: ClipboardPayload = {
      bioimageflow_clipboard: true,
      clipboard_version: 2,
      nodes: [makeNode('a'), { ...makeNode('b'), tool_name: 'tool_a' }],
      edges: [makeColumnEdge('e1', 'a', 'b')],
    }

    const result = prepareClipboardPaste(payload, {
      existingIds: [],
      existingNames: [],
      existingEdgeIds: ['pasted_edge_1'],
      getToolByName: () => makeTool(),
    })

    expect(result.edges[0].id).toBe('pasted_edge_2')
  })

  it('warns when the source package differs even if the version string matches', () => {
    const payload: ClipboardPayload = {
      bioimageflow_clipboard: true,
      clipboard_version: 2,
      nodes: [{
        ...makeNode('a'),
        tool_package: 'other-package',
        tool_package_version: '1.2.0',
      }],
      edges: [],
    }

    const result = prepareClipboardPaste(payload, {
      existingIds: [],
      existingNames: [],
      getToolByName: () => makeTool(),
    })

    expect(result.summary.versionMismatches).toHaveLength(1)
    expect(result.summary.versionMismatches[0].packageName).toBe('other-package')
  })

  it('recursively reconciles sub-workflow internals while preserving outer published parameters', () => {
    const payload: ClipboardPayload = {
      bioimageflow_clipboard: true,
      clipboard_version: 2,
      nodes: [{
        ...makeNode('outer'),
        tool_name: '__sub_workflow__',
        parameters: { exposed: 'keep', hidden: 'drop' },
        published_inputs: [{
          name: 'exposed',
          internal_node_id: 'inner',
          internal_field: 'a',
          kind: 'parameter',
          schema: null,
          default: 'keep',
        }],
        sub_workflow: {
          nodes: [{ ...makeNode('inner'), parameters: { a: 99, unknown: true } }],
          edges: [],
        },
      }],
      edges: [],
    }

    const result = prepareClipboardPaste(payload, {
      existingIds: [],
      existingNames: [],
      getToolByName: () => makeTool(),
    })

    expect(result.nodes[0].parameters).toEqual({ exposed: 'keep' })
    expect(result.nodes[0].sub_workflow?.nodes[0].parameters).toEqual({ a: 99 })
  })
})

describe('legacy compatibility helpers', () => {
  it('keeps deserializeSelection compatible with old callers', () => {
    const clipboard = {
      nodes: [makeNode('a', 100, 200)],
      edges: [makeColumnEdge('e1', 'a', 'a')],
    }

    const result = deserializeSelection(clipboard, [], [])

    expect(result.nodes[0].position).toEqual([150, 250])
    expect(result.edges[0].id).toBe('pasted_edge_1')
  })
})

describe('system clipboard fallback', () => {
  beforeEach(() => {
    _resetClipboardForTest()
    vi.unstubAllGlobals()
  })

  it('falls back to in-memory payload when browser clipboard reads fail', async () => {
    const payload = serializeSelection([makeNode('a')], [], new Set(['a']))
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    const readText = vi.fn().mockRejectedValue(new Error('denied'))
    vi.stubGlobal('navigator', { clipboard: { writeText, readText } })

    await writeClipboardPayload(payload)
    const parsed = await readClipboardPayload()

    expect(parsed?.nodes[0].id).toBe('a')
    expect(writeText).toHaveBeenCalled()
    expect(readText).toHaveBeenCalled()
  })

  it('returns invalid system clipboard text instead of pasting a stale memory payload', async () => {
    const payload = serializeSelection([makeNode('a')], [], new Set(['a']))
    const writeText = vi.fn().mockResolvedValue(undefined)
    const readText = vi.fn().mockResolvedValue('{')
    vi.stubGlobal('navigator', { clipboard: { writeText, readText } })

    await writeClipboardPayload(payload)
    const parsed = await readClipboardPayloadResult()

    expect(parsed.kind).toBe('invalid')
  })
})
