/**
 * Convert a class name (CamelCase or mixed) to a snake_case base,
 * stripping non-alphanumeric characters.
 */
function toSnakeCase(name: string): string {
  if (!name) return 'node'

  // Insert underscore before uppercase letters (CamelCase splitting)
  let result = name.replace(/([a-z0-9])([A-Z])/g, '$1_$2')
  // Replace non-alphanumeric with underscore
  result = result.replace(/[^a-zA-Z0-9]+/g, '_')
  // Collapse multiple underscores and trim
  result = result.replace(/_+/g, '_').replace(/^_|_$/g, '')
  return result.toLowerCase()
}

/**
 * Generate a unique node ID in snake_case with an incrementing suffix.
 */
export function generateNodeId(className: string, existingIds: string[]): string {
  const base = toSnakeCase(className)
  const existing = new Set(existingIds)
  let counter = 1
  while (existing.has(`${base}_${counter}`)) {
    counter++
  }
  return `${base}_${counter}`
}

/**
 * Generate a unique display name with an incrementing numeric suffix.
 */
export function generateNodeName(
  className: string,
  existingNames: string[],
  displayName?: string,
): string {
  const base = displayName ?? className
  const existing = new Set(existingNames)
  let counter = 1
  while (existing.has(`${base} ${counter}`)) {
    counter++
  }
  return `${base} ${counter}`
}
