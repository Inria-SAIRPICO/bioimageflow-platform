import { ref, shallowRef } from 'vue'
import type { NapariViewingRequirementGroup } from '@/api/types'

// Module-level state — the dialog is a singleton, so a Pinia store would be
// overkill. Components import {open, close, isOpen} and they all share state.
const isOpen = ref(false)
export type SettingsTab = 'external' | 'viewers' | 'execution' | 'display' | 'storage' | 'omero'
const activeTab = ref<SettingsTab>('external')
const napariCreatePrefills = ref<NapariViewingRequirementGroup[]>([])
const napariCreatePrefillVersion = ref(0)
let napariCreateOwner: object | null = null
const napariCreateTransfer = shallowRef<{ group: NapariViewingRequirementGroup; version: number } | null>(null)

export function useSettingsPanel() {
  return {
    isOpen,
    activeTab,
    napariCreatePrefills,
    napariCreatePrefillVersion,
    napariCreateTransfer,
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
    prepareNapariCreate: (groups: NapariViewingRequirementGroup[], owner: object | null = null) => {
      napariCreateOwner = owner
      napariCreatePrefillVersion.value += 1
      napariCreateTransfer.value = null
      napariCreatePrefills.value = JSON.parse(JSON.stringify(groups)) as NapariViewingRequirementGroup[]
    },
    clearNapariCreate: (owner: object) => {
      if (napariCreateOwner !== owner) return
      napariCreateOwner = null
      napariCreatePrefillVersion.value += 1
      napariCreateTransfer.value = null
      napariCreatePrefills.value = []
    },
    selectNapariCreateGroup: (group: NapariViewingRequirementGroup) => {
      napariCreateTransfer.value = {
        group: JSON.parse(JSON.stringify(group)) as NapariViewingRequirementGroup,
        version: napariCreatePrefillVersion.value,
      }
      activeTab.value = 'viewers'
      isOpen.value = true
    },
    consumeNapariCreatePrefill: (groupId: string, version: number) => {
      if (version !== napariCreatePrefillVersion.value) return
      napariCreatePrefills.value = napariCreatePrefills.value.filter(group => group.id !== groupId)
    },
  }
}
