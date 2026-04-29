import { ref } from 'vue'

// Module-level state — the dialog is a singleton, so a Pinia store would be
// overkill. Components import {open, close, isOpen} and they all share state.
const isOpen = ref(false)

export function useSettingsPanel() {
  return {
    isOpen,
    open: () => {
      isOpen.value = true
    },
    close: () => {
      isOpen.value = false
    },
    toggle: () => {
      isOpen.value = !isOpen.value
    },
  }
}
