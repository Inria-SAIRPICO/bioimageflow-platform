const TYPE_COLOR_MAP: Record<string, string> = {
  ImageFile: '#4A90D9',
  ImageShared: '#4A90D9',
  MaskPath: '#AF52DE',
  Path: '#34C759',
  int: '#8E8E93',
  float: '#8E8E93',
  str: '#8E8E93',
  bool: '#8E8E93',
  any: '#B0A060',
}

const DEFAULT_COLOR = '#8E8E93'

/** Neutral wildcard color for `"any"`-typed columns. */
export const ANY_TYPE_COLOR = '#B0A060'

/**
 * Return a hex color for a given data type name.
 */
export function getTypeColor(typeName: string): string {
  return TYPE_COLOR_MAP[typeName] ?? DEFAULT_COLOR
}
