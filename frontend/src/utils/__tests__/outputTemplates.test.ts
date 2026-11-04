import { describe, expect, it } from 'vitest'
import { reconcileOutputTemplates } from '../outputTemplates'
import type { ToolMetadata } from '@/api/types'

function makeTool(overrides: Partial<ToolMetadata> = {}): ToolMetadata {
  return {
    output_file_declarations: {},
    name: 'LabelOverlaps',
    display_name: 'Label Overlaps',
    package: 'bioimageflow-common-tools',
    package_version: '0.1.0',
    tool_type: 'ProcessingTool',
    accepts_upstream: true,
    dynamic_outputs: false,
    dataframe_output: false,
    row_consumption: 'mapped',
    documentation: '',
    tags: [],
    categories: [],
    inputs: {},
    outputs: {
      reference_label: { type: 'int' },
      spot_label: { type: 'int' },
      overlap_count: { type: 'int' },
    },
    environment: null,
    source_kind: 'package',
    editable: false,
    ...overrides,
  }
}

describe('reconcileOutputTemplates', () => {
  it('initializes only declared writable destinations and naming bases', () => {
    const result = reconcileOutputTemplates(makeTool({
      outputs: {
        exact: { type: 'Path', default: 'mask.tif' }, base: { type: 'Path', default: 'tile.tif' }, reference: { type: 'Path' },
      },
      output_file_declarations: {
        exact: { output_role: 'exact', file_group: { kind: 'per_row', keys: [] }, description: 'One file per input row.' },
        base: { output_role: 'base', file_group: null, description: 'Generated filenames.' },
        reference: { output_role: 'reference', file_group: null, description: '' },
      },
    }))
    expect(result).toEqual({ exact: 'mask.tif', base: 'tile.tif' })
  })

  it('preserves an authored legacy override for backend diagnosis rather than silently erasing it', () => {
    expect(reconcileOutputTemplates(makeTool({
      outputs: { reference: { type: 'Path' } },
      output_file_declarations: { reference: { output_role: 'reference', file_group: null, description: '' } },
    }), { reference: 'legacy.tif' })).toEqual({ reference: 'legacy.tif' })
  })
  it('drops stale template keys that are no longer path outputs', () => {
    const result = reconcileOutputTemplates(makeTool(), {
      overlaps: '{label_image.stem}_overlaps.csv',
    })

    expect(result).toEqual({})
  })

  it('preserves current path output templates and fills missing defaults', () => {
    const result = reconcileOutputTemplates(
      makeTool({
        outputs: {
          mask: { type: 'ImageFile', default: '{input_image.stem}_mask{ext}' },
          count: { type: 'int' },
        },
      }),
      { mask: 'custom_mask.tif', stale: 'old.csv' },
    )

    expect(result).toEqual({ mask: 'custom_mask.tif' })
  })

  it('does not create templates for DataFrameTool column declarations', () => {
    const result = reconcileOutputTemplates(
      makeTool({
        output_file_declarations: {},
        tool_type: 'DataFrameTool',
        outputs: { path: { type: 'Path' } },
      }),
      { path: 'not_a_file_template' },
    )

    expect(result).toEqual({})
  })
})
