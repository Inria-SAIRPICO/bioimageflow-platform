import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  createExecutionProfile,
  deleteExecutionProfile,
  listExecutionProfiles,
  testExecutionProfile,
  updateExecutionProfile,
  type ExecutionProfile,
  type ExecutionProfileDraft,
  type ProfileValidationResult,
} from '@/api/executionProfiles'

export const useExecutionProfilesStore = defineStore('execution-profiles', () => {
  const profiles = ref<ExecutionProfile[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const testing = ref<string | null>(null)

  const enabled = computed(() => profiles.value.filter(profile => profile.enabled))

  function message(errorValue: unknown): string {
    return errorValue instanceof Error ? errorValue.message : String(errorValue)
  }

  async function refresh(): Promise<void> {
    loading.value = true
    try {
      profiles.value = await listExecutionProfiles()
      error.value = null
    } catch (errorValue) {
      error.value = message(errorValue)
    } finally {
      loading.value = false
    }
  }

  async function create(draft: ExecutionProfileDraft): Promise<ExecutionProfile> {
    const profile = await createExecutionProfile(draft)
    profiles.value.push(profile)
    return profile
  }

  async function update(
    profile: ExecutionProfile,
    changes: Partial<ExecutionProfileDraft>,
  ): Promise<ExecutionProfile> {
    const updated = await updateExecutionProfile(profile, changes)
    const index = profiles.value.findIndex(item => item.id === profile.id)
    if (index >= 0) profiles.value[index] = updated
    return updated
  }

  async function remove(profile: ExecutionProfile): Promise<void> {
    await deleteExecutionProfile(profile)
    profiles.value = profiles.value.filter(item => item.id !== profile.id)
  }

  async function test(profile: ExecutionProfile): Promise<ProfileValidationResult> {
    testing.value = profile.id
    try {
      return await testExecutionProfile(profile)
    } finally {
      testing.value = null
    }
  }

  return { profiles, enabled, loading, error, testing, refresh, create, update, remove, test }
})
