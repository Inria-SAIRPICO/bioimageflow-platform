import { computed, reactive } from 'vue'
import { defineStore } from 'pinia'

interface ThumbnailResponse {
  blob: Blob
  status: string | null
  environment: string | null
}

export const useThumbnailsStore = defineStore('thumbnails', () => {
  const inflight = new Map<string, Promise<ThumbnailResponse>>()
  const installingCells = reactive(new Set<symbol>())
  const installing = computed(() => installingCells.size > 0)

  function setInstalling(cell: symbol, value: boolean): void {
    if (value) installingCells.add(cell)
    else installingCells.delete(cell)
  }

  async function request(url: string, sourceIdentity: string, signal: AbortSignal): Promise<ThumbnailResponse> {
    const key = `${url}::${sourceIdentity}`
    let pending = inflight.get(key)
    if (!pending) {
      pending = (async () => {
        // The URL identifies a table row, so a browser's old cached response
        // cannot establish the current file's fingerprint. The server owns it.
        const response = await fetch(url, { cache: 'no-store' })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return {
          blob: await response.blob(),
          status: response.headers.get('X-Thumbnail-Status'),
          environment: response.headers.get('X-Thumbnail-Environment'),
        }
      })()
      inflight.set(key, pending)
    }
    try {
      const response = await pending
      if (signal.aborted) throw new DOMException('Thumbnail subscriber left', 'AbortError')
      return response
    } finally {
      if (inflight.get(key) === pending) inflight.delete(key)
    }
  }

  return { installing, request, setInstalling }
})
