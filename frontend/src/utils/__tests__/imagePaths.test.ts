import { describe, expect, it } from 'vitest'
import { isImagePath } from '@/utils/imagePaths'

describe('isImagePath', () => {
  it.each([
    '/data/a.tif',
    '/data/a.TIFF',
    '/data/a.ome.tif',
    '/data/a.OME.TIFF',
    'a.png',
    'a.jpg',
    'a.jpeg',
    'a.czi',
    'a.lsm',
    'a.nd2',
  ])('recognizes %s', (value) => expect(isImagePath(value)).toBe(true))

  it.each(['/data/a.csv', '/data/tiff-not-an-extension', '', null, 42])(
    'rejects %s',
    (value) => expect(isImagePath(value)).toBe(false),
  )
})
