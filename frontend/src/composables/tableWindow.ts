import { reactive } from 'vue'

export const CONTINUOUS_BLOCK_SIZE = 32
export const MAX_TABLE_BLOCKS = 5

/** A bounded row-payload window; snapshot/query ownership stays with its caller. */
export function createTableWindow<T>(blockSize = CONTINUOUS_BLOCK_SIZE, maxBlocks = MAX_TABLE_BLOCKS) {
  const blocks = reactive(new Map<number, T>()) as Map<number, T>
  const errors = reactive(new Map<number, string>())
  const inflight = new Map<number, AbortController>()
  let generation = 0
  let wanted: number[] = []
  let center = 0
  let visiblePages: number[] = []
  let loader: ((page: number, signal: AbortSignal) => Promise<T | null>) | null = null

  function trim(): void {
    while (blocks.size > maxBlocks) {
      const furthest = [...blocks.keys()].sort((a, b) => Math.abs(b - center) - Math.abs(a - center))[0]
      if (furthest === undefined) break
      blocks.delete(furthest)
    }
    while (errors.size > maxBlocks) {
      const furthest = [...errors.keys()].sort((a, b) => Math.abs(b - center) - Math.abs(a - center))[0]
      if (furthest === undefined) break
      errors.delete(furthest)
    }
  }

  function pump(): void {
    if (!loader) return
    while (inflight.size < 2 && wanted.length > 0) {
      const page = wanted.shift()!
      if (blocks.has(page) || inflight.has(page) || errors.has(page)) continue
      const controller = new AbortController()
      const selectedGeneration = generation
      const read = loader
      inflight.set(page, controller)
      void read(page, controller.signal).then(data => {
        if (selectedGeneration !== generation || controller.signal.aborted || data === null) return
        blocks.set(page, data)
        errors.delete(page)
        trim()
      }).catch(error => {
        if (selectedGeneration !== generation || controller.signal.aborted) return
        errors.set(page, error instanceof Error ? error.message : String(error))
        trim()
      }).finally(() => {
        if (inflight.get(page) === controller) inflight.delete(page)
        if (selectedGeneration === generation) pump()
      })
    }
  }

  function pause(): void {
    generation += 1
    for (const controller of inflight.values()) controller.abort()
    inflight.clear()
    wanted = []
    visiblePages = []
    loader = null
  }

  function reset(): void {
    pause()
    blocks.clear()
    errors.clear()
  }

  function seed(page: number, data: T): void {
    blocks.set(page, data)
    trim()
  }

  function range(start: number, end: number, total: number,
    load: (page: number, signal: AbortSignal) => Promise<T | null>): void {
    loader = load
    if (total <= 0) return
    const first = Math.floor(Math.max(0, start) / blockSize)
    const last = Math.floor(Math.max(start, Math.min(total, end) - 1) / blockSize)
    center = Math.floor((first + last) / 2)
    // The visible window always wins over an earlier prefetch after a jump.
    visiblePages = Array.from({ length: last - first + 1 }, (_, i) => first + i)
    wanted = [...visiblePages]
    if ((last + 1) * blockSize < total) wanted.push(last + 1)
    wanted = wanted.filter(page => !blocks.has(page) && !inflight.has(page))
    trim()
    pump()
  }

  function retry(): void {
    const failed = visiblePages.filter(page => errors.has(page))
    for (const page of failed) errors.delete(page)
    wanted.unshift(...failed)
    pump()
  }

  return { blocks, errors, inflight, blockSize, range, pause, reset, seed, retry }
}

export type TableWindow<T> = ReturnType<typeof createTableWindow<T>>
