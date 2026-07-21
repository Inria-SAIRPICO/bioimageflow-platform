import { describe, expect, it } from 'vitest'
import {
  decodeDatasetTreeDrag,
  encodeDatasetTreeDrag,
} from '@/utils/datasetDrag'

describe('dataset tree drag payload', () => {
  it('round-trips unique managed paths', () => {
    expect(decodeDatasetTreeDrag(encodeDatasetTreeDrag([
      '/managed/a.tif',
      '/managed/a.tif',
      '/managed/b.tif',
    ]))).toEqual(['/managed/a.tif', '/managed/b.tif'])
  })

  it.each([
    '',
    'not json',
    '{}',
    '{"paths":[]}',
    '{"paths":[1]}',
  ])('rejects an invalid or empty payload: %s', (payload) => {
    expect(decodeDatasetTreeDrag(payload)).toBeNull()
  })
})
