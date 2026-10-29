import { describe, expect, it } from 'vitest'
import type { InputFieldSchema, ToolMetadata, ToolNodeState } from '@/api/types'
import { emptyGraph } from '@/sessions/graphDocument'
import { decodeWorkflowConstant, encodeWorkflowConstant } from '../workflowConstants'
import { workflowInputPresentations } from '../workflowInputPresentation'

const field: InputFieldSchema = { type: 'float', nullable: true, required: false, connectable: 'not_by_default', min: 0, max: 1, step: .000001, default: null }
const tool: ToolMetadata = { name: 'Atlas', display_name: 'Atlas', package: 'example', package_version: '1', tool_type: 'ProcessingTool', inputs: { p: field }, outputs: {}, accepts_upstream: true, dynamic_outputs: false, dataframe_output: true, row_consumption: 'mapped', documentation: '', tags: [], categories: [], source_kind: 'package', editable: false, environment: null }
function leaf(id: string): ToolNodeState {
  return { type: 'tool', id, name: id, tool_name: 'Atlas', position: [0, 0], parameters: {}, enabled: true, collapsed: false }
}
function graph() {
  const inner = emptyGraph('inner', 'Inner')
  inner.nodes = [leaf('detect')]
  inner.interface.inputs = [{ id: 'p', name: 'P value', kind: 'field', schema: { type: 'float' }, default: { __type__: 'float', value: .001 }, targets: [{ node: 'detect', port: { kind: 'field', name: 'p' } }] }]
  const middle = emptyGraph('middle', 'Middle')
  middle.nodes = [{ type: 'workflow', id: 'inner', name: 'Inner', position: [0, 0], workflow: inner, bindings: {}, enabled: true, collapsed: false }]
  middle.interface.inputs = [{ ...inner.interface.inputs[0]!, id: 'forward', targets: [{ node: 'inner', port: { kind: 'workflow', id: 'p' } }] }]
  return middle
}

describe('workflow constants', () => {
  it('encodes float integers, explicit null, tuple and recursive JSON values', () => {
    expect(JSON.parse(JSON.stringify(encodeWorkflowConstant(1, 'float')))).toEqual({ __type__: 'float', value: 1 })
    expect(encodeWorkflowConstant(null)).toEqual({ __type__: 'none', value: null })
    const wire = encodeWorkflowConstant([1, { key: [false, null] }], 'tuple')
    expect(wire.__type__).toBe('tuple')
    expect((wire.value as any[])[1]).toEqual({ __type__: 'dict', value: [{ key: { __type__: 'str', value: 'key' }, value: { __type__: 'list', value: [{ __type__: 'bool', value: false }, { __type__: 'none', value: null }] } }] })
    expect(decodeWorkflowConstant(wire)).toEqual([1, { key: [false, null] }])
  })
  it('preserves nested float, path and tuple identity when editing another item', () => {
    const previous = { __type__: 'list', value: [{ __type__: 'tuple', value: [{ __type__: 'float', value: 1 }, { __type__: 'path', value: '/a' }] }, { __type__: 'int', value: 2 }] }
    expect(encodeWorkflowConstant([[1, '/a'], 3], 'list', previous)).toEqual({ ...previous, value: [previous.value[0], { __type__: 'int', value: 3 }] })
    expect(encodeWorkflowConstant([[1, '/a'], 2], 'list', previous)).toEqual(previous)
  })
  it('keeps maps with extra __type__ keys literal and reads old raw arrays', () => {
    const value = [{ __type__: 'str', value: 'x', extra: true }]
    expect(decodeWorkflowConstant(encodeWorkflowConstant(value))).toEqual(value)
    expect(decodeWorkflowConstant({ __type__: 'list', value: [1, 'two'] })).toEqual([1, 'two'])
    expect(() => decodeWorkflowConstant({ __type__: 'dict', value: [{ key: { __type__: 'int', value: 1 }, value: { __type__: 'str', value: 'x' } }] })).toThrow('non-string keys')
  })
})

describe('recursive workflow parameter presentation', () => {
  it('uses public defaults and exact scoped leaf hints through depth two', () => {
    const calls: string[] = []
    const result = workflowInputPresentations(graph(), 'fols', (_node, scope) => { calls.push(scope); return tool }).forward!
    expect(calls).toEqual(['fols/inner/detect'])
    expect(result.field).toMatchObject({ type: 'float', display_name: 'P value', default: .001, min: 0, max: 1, step: .000001, nullable: true })
    expect(result.canPin).toBe(true)
    expect(result.targets).toEqual([{ node: 'fols/inner/detect', field: 'p' }])
  })
  it('keeps authored defaults when hints are missing or fan-out disagrees', () => {
    const current = graph()
    const nested = current.nodes[0]!
    if (nested.type !== 'workflow') throw new Error('fixture')
    nested.workflow.nodes.push(leaf('other'))
    nested.workflow.interface.inputs[0]!.targets.push({ node: 'other', port: { kind: 'field', name: 'p' } })
    const result = workflowInputPresentations(current, 'fols', (_node, scope) => scope.endsWith('/other') ? { ...tool, inputs: { p: { ...field, step: .1 } } } : tool).forward!
    expect(result.field.step).toBeUndefined()
    expect(result.field.default).toBe(.001)
    const missing = workflowInputPresentations(current, 'fols', () => null).forward!
    expect(missing.field.default).toBe(.001)
    expect(missing.canPin).toBe(false)
    expect(missing.field.step).toBeUndefined()
  })
  it('publishes constant DataFrame parameters without offering a column pin', () => {
    const result = workflowInputPresentations(graph(), 'fols', () => ({ ...tool, tool_type: 'DataFrameTool' })).forward!
    expect(result.canPin).toBe(false)
    expect(result.field.default).toBe(.001)
  })
})
