import { describe, it, expect } from 'vitest'
import { getTypeColor } from '../typeColors'

describe('getTypeColor', () => {
  it('returns blue for ImagePath', () => {
    expect(getTypeColor('ImagePath')).toBe('#4A90D9')
  })

  it('returns blue for ImageShared', () => {
    expect(getTypeColor('ImageShared')).toBe('#4A90D9')
  })

  it('returns green for Path', () => {
    expect(getTypeColor('Path')).toBe('#34C759')
  })

  it('returns gray for int', () => {
    expect(getTypeColor('int')).toBe('#8E8E93')
  })

  it('returns gray for float', () => {
    expect(getTypeColor('float')).toBe('#8E8E93')
  })

  it('returns gray for str', () => {
    expect(getTypeColor('str')).toBe('#8E8E93')
  })

  it('returns gray for bool', () => {
    expect(getTypeColor('bool')).toBe('#8E8E93')
  })

  it('returns default gray for unknown type', () => {
    expect(getTypeColor('SomethingElse')).toBe('#8E8E93')
  })
})
