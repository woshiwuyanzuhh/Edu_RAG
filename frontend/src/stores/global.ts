import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useGlobalStore = defineStore('global', () => {
  // === Theme ===
  const theme = ref<'light' | 'dark'>(localStorage.getItem('edu-rag-theme') as 'light' | 'dark' || 'light')

  const isDark = computed(() => theme.value === 'dark')

  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    localStorage.setItem('edu-rag-theme', theme.value)
    applyTheme()
  }

  function applyTheme() {
    document.documentElement.setAttribute('data-theme', theme.value)
  }

  function initTheme() {
    applyTheme()
  }

  // === Stats (cached from backend) ===
  const stats = ref({
    kbCount: 0,
    docCount: 0,
    qaCount: 0,
    examCount: 0,
  })

  function updateStats(partial: Partial<typeof stats.value>) {
    stats.value = { ...stats.value, ...partial }
  }

  // === Current Knowledge Base ===
  const currentKbId = ref<number | undefined>(
    Number(localStorage.getItem('edu-rag-current-kb')) || undefined
  )

  function setCurrentKb(id: number | undefined) {
    currentKbId.value = id
    if (id) localStorage.setItem('edu-rag-current-kb', String(id))
    else localStorage.removeItem('edu-rag-current-kb')
  }

  return {
    theme,
    isDark,
    toggleTheme,
    initTheme,
    stats,
    updateStats,
    currentKbId,
    setCurrentKb,
  }
})
