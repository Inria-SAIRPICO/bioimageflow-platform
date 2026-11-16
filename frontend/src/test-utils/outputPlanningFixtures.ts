import type { OutputPlanningReport } from '@/api/types'

export function makeOutputPlanningReport(overrides: Partial<OutputPlanningReport> = {}): OutputPlanningReport {
  return {
    code: 'output_path_collision',
    node_id: 'atlas',
    detail: 'Six rows produce the same filename: image_detections.tif.',
    fields: [{
      field: 'output_image', template: '{input_image.stem}_detections{ext}', kind: 'exact',
      group: { kind: 'per_row', keys: [] }, description: 'One file per input row.',
    }],
    conflicts: [{
      path: 'image_detections.tif', total_members: 6,
      members: [{
        field: 'output_image', row_position: 0, row_index: '0', group_index: 0, group_key: {},
        parts: [
          { kind: 'token', text: '{input_image.stem}', value: 'image' },
          { kind: 'literal', text: '_detections', value: '_detections' },
          { kind: 'token', text: '{ext}', value: '.tif' },
        ],
      }],
    }],
    total_conflicts: 1, total_owners: 6,
    suggested_templates: { output_image: '{input_image.stem}_detections_{row_index}{ext}' },
    correction_available: true, correction_unavailable_reason: null,
    ...overrides,
  }
}
