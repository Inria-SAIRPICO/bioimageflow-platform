export const DATASET_TREE_DRAG_MIME = 'application/bioimageflow-datasets'

export function encodeDatasetTreeDrag(paths: string[]): string {
  return JSON.stringify({ paths: [...new Set(paths.filter(path => path.length > 0))] })
}

export function decodeDatasetTreeDrag(value: string): string[] | null {
  if (!value) return null
  try {
    const parsed: unknown = JSON.parse(value)
    if (!parsed || typeof parsed !== 'object' || !('paths' in parsed)) return null
    const paths = (parsed as { paths?: unknown }).paths
    if (!Array.isArray(paths) || !paths.every(path => typeof path === 'string')) return null
    const uniquePaths = [...new Set(paths.filter(path => path.length > 0))]
    return uniquePaths.length > 0 ? uniquePaths : null
  } catch {
    return null
  }
}
