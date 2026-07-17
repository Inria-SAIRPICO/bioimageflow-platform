export const IMAGE_PATH_GLOBS = [
  '*.tif',
  '*.tiff',
  '*.ome.tif',
  '*.ome.tiff',
  '*.png',
  '*.jpg',
  '*.jpeg',
  '*.czi',
  '*.lsm',
  '*.nd2',
] as const

const IMAGE_PATH_PATTERN = /\.(?:ome\.tiff?|tiff?|png|jpe?g|czi|lsm|nd2)$/i

export function isImagePath(value: unknown): boolean {
  if (typeof value !== 'string') return false
  return IMAGE_PATH_PATTERN.test(value.trim())
}
