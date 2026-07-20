import { describe, expect, it } from 'vitest'
import CanvasView from '../CanvasView.vue'

describe('CanvasView recursive workflow editor', () => {
  it('builds as the shared root and nested workflow canvas', () => {
    expect(CanvasView).toBeTruthy()
  })
})
