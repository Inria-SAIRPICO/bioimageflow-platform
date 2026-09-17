import { ref } from 'vue'
import type { NapariViewingRequirementGroup } from '@/api/types'

// Module-level state — the dialog is a singleton, so a Pinia store would be
// overkill. Components import {open, close, isOpen} and they all share state.
const isOpen = ref(false)
export type SettingsTab = 'external' | 'viewers' | 'execution' | 'display' | 'storage' | 'omero'
const activeTab = ref<SettingsTab>('external')
const napariCreatePrefills = ref<NapariViewingRequirementGroup[]>([])

export function useSettingsPanel() {
  return {
    isOpen,
    activeTab,
    napariCreatePrefills,
    open: (tab: SettingsTab = 'external') => {
      activeTab.value = tab
      isOpen.value = true
    },
    close: () => {
      isOpen.value = false
    },
    toggle: () => {
      if (!isOpen.value) activeTab.value = 'external'
      isOpen.value = !isOpen.value
    },
    prepareNapariCreate: (groups: NapariViewingRequirementGroup[]) => {
      napariCreatePrefills.value = groups
    },
    consumeNapariCreatePrefill: (groupId: string) => {
      napariCreatePrefills.value = napariCreatePrefills.value.filter(group => group.id !== groupId)
    },
  }
}
