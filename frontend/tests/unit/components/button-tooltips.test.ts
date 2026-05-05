import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const projectRoot = dirname(dirname(dirname(dirname(fileURLToPath(import.meta.url)))))
const sourceRoot = join(projectRoot, 'src')

function vueFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry)
    const stats = statSync(path)

    if (stats.isDirectory()) return vueFiles(path)
    return path.endsWith('.vue') ? [path] : []
  })
}

function hasAttr(markup: string, name: string) {
  return new RegExp(`(?:^|\\s):?${name}\\s*=`).test(markup)
}

function visibleText(markup: string) {
  return markup
    .replace(/<i\b[^>]*>.*?<\/i>/gs, '')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, '')
}

describe('button tooltips', () => {
  it('gives every unlabeled button a title tooltip', () => {
    const missing: string[] = []

    for (const file of vueFiles(sourceRoot)) {
      const source = readFileSync(file, 'utf8')
      const rel = relative(projectRoot, file)

      for (const match of source.matchAll(/<Button\b[^>]*(?:\/>|>)/g)) {
        const openingTag = match[0]
        if (!hasAttr(openingTag, 'label') && !hasAttr(openingTag, 'title')) {
          const line = source.slice(0, match.index).split('\n').length
          missing.push(`${rel}:${line}`)
        }
      }

      for (const match of source.matchAll(/<button\b[^>]*>.*?<\/button>/gs)) {
        const button = match[0]
        if (!hasAttr(button, 'title') && !visibleText(button)) {
          const line = source.slice(0, match.index).split('\n').length
          missing.push(`${rel}:${line}`)
        }
      }
    }

    expect(missing).toEqual([])
  })
})
