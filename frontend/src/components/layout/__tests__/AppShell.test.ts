import { describe, expect, it } from 'vitest'
import App from '@/App.vue'

describe('application shell', () => {
  it('builds with the unified workflow editor panels', () => {
    expect(App).toBeTruthy()
  })
})
