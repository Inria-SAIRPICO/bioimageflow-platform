import { describe, it, expect } from 'vitest'
import { api } from '@/api/client'

describe('API client', () => {
  it('exports an axios instance with standard HTTP methods', () => {
    for (const method of ['get', 'post', 'put', 'delete', 'patch'] as const) {
      expect(typeof api[method]).toBe('function')
    }
  })

  it('has request/interceptors (axios instance marker)', () => {
    expect(api.interceptors).toBeDefined()
    expect(api.interceptors.request).toBeDefined()
    expect(api.interceptors.response).toBeDefined()
  })

  it('does not hardcode a Content-Type default (lets axios auto-detect FormData vs JSON)', () => {
    const headers = api.defaults.headers
    const contentType = headers['Content-Type']
      ?? headers.common?.['Content-Type']
    // axios's built-in post default is application/x-www-form-urlencoded, which
    // it correctly overrides to multipart/... when the body is a FormData.
    expect(contentType).toBeUndefined()
  })

  it('does not set a baseURL', () => {
    expect(api.defaults.baseURL).toBeUndefined()
  })
})
