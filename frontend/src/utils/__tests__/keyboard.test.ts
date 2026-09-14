import { describe, expect, it } from 'vitest'
import { isTextEntryTarget } from '../keyboard'

describe('keyboard focus safety', () => {
  it('recognizes native and semantic text-entry descendants', () => {
    const host = document.createElement('div')
    host.innerHTML = `
      <input><textarea></textarea><select></select>
      <div contenteditable="true"><span data-target></span></div>
      <div role="textbox"><span data-role-target></span></div>
      <button></button>
    `

    expect(isTextEntryTarget(host.querySelector('input'))).toBe(true)
    expect(isTextEntryTarget(host.querySelector('textarea'))).toBe(true)
    expect(isTextEntryTarget(host.querySelector('select'))).toBe(true)
    expect(isTextEntryTarget(host.querySelector('[data-target]'))).toBe(true)
    expect(isTextEntryTarget(host.querySelector('[data-role-target]'))).toBe(true)
    expect(isTextEntryTarget(host.querySelector('button'))).toBe(false)
    expect(isTextEntryTarget(null)).toBe(false)
  })
})
