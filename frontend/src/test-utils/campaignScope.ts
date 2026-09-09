export const CAMPAIGN_EXCLUSION_REASONS = [
  'parallel-scheduling',
  'parsl',
  'managed-remote',
  'distributed-engine',
] as const

export type CampaignExclusionReason = typeof CAMPAIGN_EXCLUSION_REASONS[number]
export const CAMPAIGN_ANNOTATION = 'campaign-excluded'
export const CAMPAIGN_META_KEY = 'campaignExcluded'

export interface CollectedCampaignCase {
  nodeid: string
  reason?: unknown
}

interface CampaignManifestSuite {
  runner: string
  root: string
  excluded: unknown[]
}

interface CampaignManifest {
  schema_version: number
  suites: Record<string, CampaignManifestSuite>
}

export function loadCampaignExclusions(
  document: unknown,
  suiteName: string,
  runner: string,
): Map<string, CampaignExclusionReason> {
  if (!document || typeof document !== 'object') throw new Error('campaign manifest must be an object')
  const manifest = document as Partial<CampaignManifest>
  if (manifest.schema_version !== 1) throw new Error('campaign manifest schema_version must be 1')
  const suite = manifest.suites?.[suiteName]
  if (!suite || suite.runner !== runner || suite.root !== 'frontend') {
    throw new Error(`${suiteName} suite must declare ${runner} with root 'frontend'`)
  }
  if (!Array.isArray(suite.excluded)) throw new Error(`${suiteName} excluded must be a list`)

  const exclusions = new Map<string, CampaignExclusionReason>()
  for (const [index, rawEntry] of suite.excluded.entries()) {
    if (!rawEntry || typeof rawEntry !== 'object') {
      throw new Error(`${suiteName} excluded entry ${index} must be an object`)
    }
    const entry = rawEntry as Record<string, unknown>
    if (Object.keys(entry).sort().join(',') !== 'nodeid,reason') {
      throw new Error(`${suiteName} excluded entry ${index} must contain only nodeid and reason`)
    }
    const { nodeid, reason } = entry
    if (typeof nodeid !== 'string' || !nodeid) {
      throw new Error(`${suiteName} excluded entry ${index} has an invalid nodeid`)
    }
    if (!CAMPAIGN_EXCLUSION_REASONS.includes(reason as CampaignExclusionReason)) {
      throw new Error(`${suiteName} excluded entry ${nodeid} has invalid reason ${String(reason)}`)
    }
    if (exclusions.has(nodeid)) {
      throw new Error(`campaign manifest has duplicate ${suiteName} nodeids: ${nodeid}`)
    }
    exclusions.set(nodeid, reason as CampaignExclusionReason)
  }
  return exclusions
}

export function auditCampaignCollection(
  suiteName: string,
  cases: CollectedCampaignCase[],
  manifest: Map<string, CampaignExclusionReason>,
): { selected: string[], excluded: string[] } {
  const errors: string[] = []
  const collected = new Set<string>()
  const marked = new Map<string, CampaignExclusionReason>()
  const duplicateNodeids = new Set<string>()
  for (const testCase of cases) {
    if (collected.has(testCase.nodeid)) duplicateNodeids.add(testCase.nodeid)
    collected.add(testCase.nodeid)
    if (testCase.reason === undefined) continue
    if (!CAMPAIGN_EXCLUSION_REASONS.includes(testCase.reason as CampaignExclusionReason)) {
      errors.push(`${testCase.nodeid}: invalid exclusion reason ${String(testCase.reason)}`)
      continue
    }
    const reason = testCase.reason as CampaignExclusionReason
    const previous = marked.get(testCase.nodeid)
    if (previous !== undefined && previous !== reason) {
      errors.push(`${testCase.nodeid}: conflicting collected exclusion reasons`)
      continue
    }
    marked.set(testCase.nodeid, reason)
  }
  if (duplicateNodeids.size) {
    errors.push(`duplicate collected nodeids: ${[...duplicateNodeids].sort().join(', ')}`)
  }
  const missing = [...manifest.keys()].filter(nodeid => !collected.has(nodeid)).sort()
  const unmanifested = [...marked.keys()].filter(nodeid => !manifest.has(nodeid)).sort()
  const unmarked = [...manifest.keys()].filter(nodeid => collected.has(nodeid) && !marked.has(nodeid)).sort()
  const drift = [...marked.entries()]
    .filter(([nodeid, reason]) => manifest.has(nodeid) && manifest.get(nodeid) !== reason)
    .map(([nodeid, reason]) => `${nodeid}: annotation=${reason}, manifest=${manifest.get(nodeid)}`)
    .sort()
  if (missing.length) errors.push(`manifest nodeids missing from collection: ${missing.join(', ')}`)
  if (unmanifested.length) errors.push(`marked nodeids missing from manifest: ${unmanifested.join(', ')}`)
  if (unmarked.length) errors.push(`manifest nodeids missing campaign annotations: ${unmarked.join(', ')}`)
  if (drift.length) errors.push(`campaign exclusion reason drift: ${drift.join(', ')}`)
  const selected = [...collected].filter(nodeid => !marked.has(nodeid)).sort()
  if (!selected.length) errors.push('campaign selection contains zero tests')
  if (errors.length) throw new Error(`invalid ${suiteName} local campaign scope:\n- ${errors.join('\n- ')}`)
  return { selected, excluded: [...marked.keys()].sort() }
}
