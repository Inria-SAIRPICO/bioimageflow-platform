import { describe, expect, it } from 'vitest'
import { createSubWorkflowFromSelection } from '../subWorkflow'
import type { ToolMetadata } from '@/api/types'

function makeTool(name: string, inputs: Record<string, any>, outputs: Record<string, any>): ToolMetadata {
  return {
    name,
    display_name: name,
    package: 'core',
    package_version: '1.0.0',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    documentation: '',
    tags: [],
    categories: [],
    inputs,
    outputs,
    environment: null,
  }
}

const sourceTool = makeTool('files', {}, { image: { type: 'ImagePath' } })
const blurTool = makeTool(
  'blur',
  {
    image: { type: 'ImagePath', required: true, nullable: false, connectable: 'by_default' },
    sigma: { type: 'float', required: false, nullable: false, connectable: 'never', default: 1 },
  },
  { result: { type: 'ImagePath' } },
)
const thresholdTool = makeTool(
  'threshold',
  {
    image: { type: 'ImagePath', required: true, nullable: false, connectable: 'by_default' },
    level: { type: 'float', required: false, nullable: false, connectable: 'never', default: 0.5 },
  },
  { mask: { type: 'MaskPath' } },
)
const sinkTool = makeTool(
  'sink',
  { mask: { type: 'MaskPath', required: true, nullable: false, connectable: 'by_default' } },
  {},
)

function node(id: string, x: number, tool: ToolMetadata) {
  return {
    id,
    type: 'tool',
    selected: id === 'blur_1' || id === 'threshold_1',
    position: { x, y: 100 },
    data: {
      name: id,
      toolName: tool.name,
      tool,
      status: 'unexecuted',
      parameters: {},
      collapsed: false,
      enabled: true,
      connectedInputs: {},
      pinnedInputs: {},
      output_templates: {},
    },
  }
}

describe('createSubWorkflowFromSelection', () => {
  it('moves selected nodes and internal edges into a nested graph and rewires external edges to published pins', () => {
    const result = createSubWorkflowFromSelection({
      nodes: [
        node('files_1', 0, sourceTool),
        node('blur_1', 100, blurTool),
        node('threshold_1', 300, thresholdTool),
        node('sink_1', 500, sinkTool),
      ],
      edges: [
        {
          id: 'e-in',
          source: 'files_1',
          target: 'blur_1',
          sourceHandle: 'image',
          targetHandle: 'image',
          type: 'column_ref',
        },
        {
          id: 'e-internal',
          source: 'blur_1',
          target: 'threshold_1',
          sourceHandle: 'result',
          targetHandle: 'image',
          type: 'column_ref',
        },
        {
          id: 'e-out',
          source: 'threshold_1',
          target: 'sink_1',
          sourceHandle: 'mask',
          targetHandle: 'mask',
          type: 'column_ref',
        },
      ],
      selectedNodeIds: new Set(['blur_1', 'threshold_1']),
      subWorkflowId: 'sub_workflow_1',
      subWorkflowName: 'Sub-workflow 1',
    })

    expect(result.nodes.map((n) => n.id)).toEqual(['files_1', 'sink_1', 'sub_workflow_1'])
    const subNode = result.nodes.find((n) => n.id === 'sub_workflow_1')!
    const subData = subNode.data as any
    expect(subNode.type).toBe('sub_workflow')
    expect(subNode.position).toEqual({ x: 200, y: 100 })
    expect(subData.toolName).toBe('__sub_workflow__')
    expect(subData.sub_workflow.nodes.map((n: any) => n.id)).toEqual(['blur_1', 'threshold_1'])
    expect(subData.sub_workflow.edges.map((e: any) => e.id)).toEqual(['e-internal'])
    expect(subData.published_inputs).toEqual([
      expect.objectContaining({
        name: 'blur_1.image',
        internal_node_id: 'blur_1',
        internal_field: 'image',
        kind: 'input',
        schema: blurTool.inputs.image,
      }),
    ])
    expect(subData.published_outputs).toEqual([
      expect.objectContaining({
        name: 'threshold_1.mask',
        internal_node_id: 'threshold_1',
        internal_output: 'mask',
        schema: thresholdTool.outputs.mask,
      }),
    ])
    expect(result.edges).toEqual([
      expect.objectContaining({
        id: 'e-in',
        source: 'files_1',
        target: 'sub_workflow_1',
        sourceHandle: 'image',
        targetHandle: 'blur_1.image',
      }),
      expect.objectContaining({
        id: 'e-out',
        source: 'sub_workflow_1',
        target: 'sink_1',
        sourceHandle: 'threshold_1.mask',
        targetHandle: 'mask',
      }),
    ])
  })

  it('allows detached selected branches with no published pins', () => {
    const result = createSubWorkflowFromSelection({
      nodes: [node('blur_1', 100, blurTool), node('threshold_1', 300, thresholdTool)],
      edges: [{
        id: 'e-internal',
        source: 'blur_1',
        target: 'threshold_1',
        sourceHandle: 'result',
        targetHandle: 'image',
        type: 'column_ref',
      }],
      selectedNodeIds: new Set(['blur_1', 'threshold_1']),
      subWorkflowId: 'sub_workflow_1',
      subWorkflowName: 'Sub-workflow 1',
    })

    const subNode = result.nodes.find((n) => n.id === 'sub_workflow_1')!
    const subData = subNode.data as any
    expect(result.edges).toEqual([])
    expect(subData.published_inputs).toEqual([])
    expect(subData.published_outputs).toEqual([])
    expect(subData.sub_workflow.edges).toHaveLength(1)
  })
})
