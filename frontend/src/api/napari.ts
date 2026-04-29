import { api } from '@/api/client'
import type { NapariStatus } from '@/api/types'

/**
 * Open a list of file paths in the Napari viewer (lazily launching it).
 *
 * @throws on non-200 responses — Axios surfaces the error with `response.data.detail`.
 */
export async function openInNapari(
  paths: string[],
  clearLayers: boolean = false,
): Promise<void> {
  await api.post('/api/v1/napari/open', {
    paths,
    clear_layers: clearLayers,
  })
}

/** Snapshot of the Napari launcher state. Lock-free server-side. */
export async function getNapariStatus(): Promise<NapariStatus> {
  const response = await api.get<NapariStatus>('/api/v1/napari/status')
  return response.data
}

/** Terminate the Napari manager process. Idempotent on the server. */
export async function shutdownNapari(): Promise<void> {
  await api.post('/api/v1/napari/shutdown')
}
