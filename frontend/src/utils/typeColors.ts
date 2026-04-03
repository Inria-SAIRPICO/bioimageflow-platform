const TYPE_COLOR_MAP: Record<string, string> = {
  ImagePath: '#4A90D9',
  ImageShared: '#4A90D9',
  Path: '#34C759',
  int: '#8E8E93',
  float: '#8E8E93',
  str: '#8E8E93',
  bool: '#8E8E93',
}

const DEFAULT_COLOR = '#8E8E93'

/**
 * Return a hex color for a given data type name.
 */
export function getTypeColor(typeName: string): string {
  return TYPE_COLOR_MAP[typeName] ?? DEFAULT_COLOR
}
