import { describe, expect, it } from 'vitest'
import { auditCampaignCollection, loadCampaignExclusions } from '../../src/test-utils/campaignScope'

function manifest(entries: Array<{ nodeid: string, reason: string }>) {
  return {
    schema_version: 1,
    suites: {
      browser: { runner: 'playwright', root: 'frontend', excluded: entries },
    },
  }
}

describe('campaign local scope audit', () => {
  it('returns the exact selected and excluded partition', () => {
    const exclusions = loadCampaignExclusions(manifest([
      { nodeid: 'tests/e2e/remote.spec.ts::remote', reason: 'managed-remote' },
    ]), 'browser', 'playwright')

    expect(auditCampaignCollection('browser', [
      { nodeid: 'tests/e2e/local.spec.ts::local' },
      { nodeid: 'tests/e2e/remote.spec.ts::remote', reason: 'managed-remote' },
    ], exclusions)).toEqual({
      selected: ['tests/e2e/local.spec.ts::local'],
      excluded: ['tests/e2e/remote.spec.ts::remote'],
    })
  })

  it.each([
    ['a missing collected case', [{ nodeid: 'local' }], [{ nodeid: 'missing', reason: 'parsl' }], 'missing from collection'],
    ['an unmanifested annotation', [{ nodeid: 'local' }, { nodeid: 'remote', reason: 'managed-remote' }], [], 'missing from manifest'],
    ['an unmarked manifest case', [{ nodeid: 'local' }, { nodeid: 'remote' }], [{ nodeid: 'remote', reason: 'managed-remote' }], 'missing campaign annotations'],
    ['reason drift', [{ nodeid: 'local' }, { nodeid: 'remote', reason: 'parsl' }], [{ nodeid: 'remote', reason: 'managed-remote' }], 'reason drift'],
    ['an invalid annotation reason', [{ nodeid: 'local' }, { nodeid: 'remote', reason: 'hpc' }], [], 'invalid exclusion reason'],
    ['duplicate collected nodeids', [{ nodeid: 'local' }, { nodeid: 'local' }], [], 'duplicate collected nodeids'],
    ['duplicate annotated nodeids with the same reason', [{ nodeid: 'local' }, { nodeid: 'remote', reason: 'parsl' }, { nodeid: 'remote', reason: 'parsl' }], [{ nodeid: 'remote', reason: 'parsl' }], 'duplicate collected nodeids'],
    ['zero selected tests', [{ nodeid: 'remote', reason: 'managed-remote' }], [{ nodeid: 'remote', reason: 'managed-remote' }], 'zero tests'],
  ])('rejects %s', (_label, cases, entries, message) => {
    const exclusions = loadCampaignExclusions(manifest(entries), 'browser', 'playwright')
    expect(() => auditCampaignCollection('browser', cases, exclusions)).toThrow(message)
  })

  it('rejects duplicate nodeids and reasons outside the allowed vocabulary', () => {
    expect(() => loadCampaignExclusions(manifest([
      { nodeid: 'remote', reason: 'parsl' },
      { nodeid: 'remote', reason: 'parsl' },
    ]), 'browser', 'playwright')).toThrow('duplicate')
    expect(() => loadCampaignExclusions(manifest([
      { nodeid: 'remote', reason: 'hpc' },
    ]), 'browser', 'playwright')).toThrow('invalid reason')
  })
})
