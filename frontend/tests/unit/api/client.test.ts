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

  it('sets default Content-Type header to application/json', () => {
    const headers = api.defaults.headers
    const contentType = headers['Content-Type']
      ?? headers.common?.['Content-Type']
      ?? headers.post?.['Content-Type']
    expect(contentType).toBe('application/json')
  })

  it('does not set a baseURL', () => {
    expect(api.defaults.baseURL).toBeUndefined()
  })
})
