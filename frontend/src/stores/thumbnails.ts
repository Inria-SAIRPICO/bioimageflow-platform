import { computed, reactive } from 'vue'
import { defineStore } from 'pinia'

export interface ThumbnailState {
  status: 'pending' | 'ready' | 'failed' | 'unavailable'
  blob?: Blob
  environment?: string | null
}

interface ThumbnailEntry {
  key: string
  url: string
  state: ThumbnailState
  listeners: Set<(state: ThumbnailState) => void>
  running: boolean
  attempts: number
  timer: ReturnType<typeof setTimeout> | null
}

interface ThumbnailResourceOptions {
  maxEntries?: number
  maxBytes?: number
  fetcher?: typeof fetch
  onInstallingChange?: (key: string, installing: boolean) => void
}

/** One request/poll chain per exact source within an accepted inspection epoch. */
export function createThumbnailResources(options: ThumbnailResourceOptions = {}) {
  const entries = new Map<string, ThumbnailEntry>()
  const completed = new Map<string, ThumbnailState & { blob: Blob }>()
  const maxEntries = options.maxEntries ?? 128
  const maxBytes = options.maxBytes ?? 32 * 1024 * 1024
  let cachedBytes = 0

  function installation(entry: ThumbnailEntry): void {
    options.onInstallingChange?.(entry.key,
      entry.listeners.size > 0 && entry.state.status === 'pending' && entry.state.environment === 'installing')
  }

  function notify(entry: ThumbnailEntry, state: ThumbnailState): void {
    entry.state = state
    installation(entry)
    for (const listener of [...entry.listeners]) {
      if (entry.listeners.has(listener)) listener(state)
    }
  }

  function remember(key: string, state: ThumbnailState & { blob: Blob }): void {
    if (state.blob.size > maxBytes || maxEntries < 1) return
    const previous = completed.get(key)
    if (previous) cachedBytes -= previous.blob.size
    completed.delete(key)
    completed.set(key, state)
    cachedBytes += state.blob.size
    while (completed.size > maxEntries || cachedBytes > maxBytes) {
      const oldest = completed.keys().next().value
      if (oldest === undefined) break
      cachedBytes -= completed.get(oldest)!.blob.size
      completed.delete(oldest)
    }
  }

  async function pump(entry: ThumbnailEntry): Promise<void> {
    if (entry.running || entry.timer !== null || entry.listeners.size === 0 || entry.state.status !== 'pending') return
    entry.running = true
    try {
      const url = new URL(entry.url, 'http://thumbnail.local')
      url.searchParams.delete('wait')
      if (entry.attempts > 0) url.searchParams.set('wait', '20')
      entry.attempts += 1
      // The backend owns file fingerprint validation. This cache only reuses
      // bytes inside the caller's inspection epoch; Refresh supplies a new key.
      const response = await (options.fetcher ?? fetch)(`${url.pathname}${url.search}`, { cache: 'no-store' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const status = response.headers.get('X-Thumbnail-Status')
      const environment = response.headers.get('X-Thumbnail-Environment')
      const blob = await response.blob()
      if (status === 'ready') {
        const state = { status: 'ready' as const, blob, environment }
        remember(entry.key, state)
        notify(entry, state)
      } else if (status === 'pending') {
        notify(entry, { status, environment })
      } else {
        notify(entry, { status: status === 'unavailable' ? 'unavailable' : 'failed', environment })
      }
    } catch {
      notify(entry, { status: 'failed' })
    } finally {
      entry.running = false
      if (entry.listeners.size === 0) {
        if (entries.get(entry.key) === entry) entries.delete(entry.key)
      } else if (entry.state.status === 'pending') {
        entry.timer = setTimeout(() => {
          entry.timer = null
          void pump(entry)
        }, 250)
      }
    }
  }

  function subscribe(key: string, url: string, listener: (state: ThumbnailState) => void): () => void {
    let entry = entries.get(key)
    if (!entry) {
      const ready = completed.get(key)
      if (ready) {
        completed.delete(key)
        completed.set(key, ready)
      }
      entry = { key, url, state: ready ?? { status: 'pending' }, listeners: new Set(), running: false, attempts: 0, timer: null }
      entries.set(key, entry)
    }
    entry.listeners.add(listener)
    installation(entry)
    listener(entry.state)
    void pump(entry)
    const subscribed = entry
    return () => {
      subscribed.listeners.delete(listener)
      installation(subscribed)
      if (subscribed.listeners.size === 0) {
        if (subscribed.timer !== null) clearTimeout(subscribed.timer)
        subscribed.timer = null
        // Do not abort an issued wait: a remounted sibling can join it and the
        // backend render is service-owned. Its completion cannot restart polls
        // without a subscriber, nor notify cells belonging to a newer epoch.
        if (!subscribed.running && entries.get(key) === subscribed) entries.delete(key)
      }
    }
  }

  return { subscribe }
}

export const useThumbnailsStore = defineStore('thumbnails', () => {
  const installingResources = reactive(new Set<string>())
  const resources = createThumbnailResources({
    onInstallingChange(key, installing) {
      if (installing) installingResources.add(key)
      else installingResources.delete(key)
    },
  })
  const installing = computed(() => installingResources.size > 0)
  return { installing, subscribe: resources.subscribe }
})
