import { describe, it, expect } from 'vitest'
import { generateNodeId, generateNodeName } from '../nodeIdGenerator'

describe('generateNodeId', () => {
  it('converts CamelCase to snake_case with suffix _1', () => {
    expect(generateNodeId('CellposeSegmenter', [])).toBe('cellpose_segmenter_1')
  })

  it('strips non-alphanumeric characters', () => {
    expect(generateNodeId('My Tool (v2)', [])).toBe('my_tool_v2_1')
  })

  it('increments when the id already exists', () => {
    expect(generateNodeId('CellposeSegmenter', ['cellpose_segmenter_1'])).toBe('cellpose_segmenter_2')
  })

  it('skips to next available with multiple existing', () => {
    expect(generateNodeId('CellposeSegmenter', [
      'cellpose_segmenter_1',
      'cellpose_segmenter_2',
      'cellpose_segmenter_3',
    ])).toBe('cellpose_segmenter_4')
  })

  it('falls back to node_1 for empty name', () => {
    expect(generateNodeId('', [])).toBe('node_1')
  })

  it('handles single-word class name', () => {
    expect(generateNodeId('Threshold', [])).toBe('threshold_1')
  })

  it('handles already snake_case input', () => {
    expect(generateNodeId('my_tool', [])).toBe('my_tool_1')
  })
})

describe('generateNodeName', () => {
  it('generates space-separated display name with number', () => {
    expect(generateNodeName('CellposeSegmenter', [])).toBe('CellposeSegmenter 1')
  })

  it('increments when name exists', () => {
    expect(generateNodeName('CellposeSegmenter', ['CellposeSegmenter 1'])).toBe('CellposeSegmenter 2')
  })

  it('uses provided displayName', () => {
    expect(generateNodeName('CellposeSegmenter', [], 'Cellpose Segmenter')).toBe('Cellpose Segmenter 1')
  })

  it('uses provided displayName and increments', () => {
    expect(generateNodeName('CellposeSegmenter', ['Cellpose Segmenter 1'], 'Cellpose Segmenter')).toBe('Cellpose Segmenter 2')
  })

  it('ensures uniqueness across multiple existing names', () => {
    expect(generateNodeName('Threshold', [
      'Threshold 1',
      'Threshold 2',
    ])).toBe('Threshold 3')
  })

  it('falls back for empty className', () => {
    expect(generateNodeName('', [])).toBe(' 1')
  })

  it('uses displayName even when className is empty', () => {
    expect(generateNodeName('', [], 'My Node')).toBe('My Node 1')
  })
})
