// STUB: a minimal error-report store so that useWebSocket (and any other
// client code) can report errors to a single sink. The canonical global
// error-handling store from spec §3.11 will replace this when implemented.
// Kept minimal on purpose — only `report` and the `errors` array.

import { ref } from 'vue'
import { defineStore } from 'pinia'

export interface ReportedError {
  kind: string
  detail?: string
  [extra: string]: unknown
}

export const useErrorStore = defineStore('errors', () => {
  const errors = ref<ReportedError[]>([])

  function report(err: ReportedError): void {
    errors.value.push(err)
  }

  function clear(): void {
    errors.value = []
  }

  return { errors, report, clear }
})
