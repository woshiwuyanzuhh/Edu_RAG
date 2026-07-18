import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useGlobalStore } from '../global'

// Mock localStorage — 按值存储，getItem 返回实际存储的值
const localStorageStore: Record<string, string> = {}
const localStorageMock = {
  getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { localStorageStore[key] = value }),
  removeItem: vi.fn((key: string) => { delete localStorageStore[key] }),
  clear: vi.fn(() => {
    Object.keys(localStorageStore).forEach((k) => delete localStorageStore[k])
  }),
}
vi.stubGlobal('localStorage', localStorageMock)

beforeEach(() => {
  setActivePinia(createPinia())
  localStorageMock.clear()
  localStorageMock.getItem.mockClear()
  localStorageMock.setItem.mockClear()
  localStorageMock.removeItem.mockClear()
  // 重置 document.documentElement 属性
  document.documentElement.removeAttribute('data-theme')
})

describe('global store', () => {
  describe('主题管理', () => {
    it('默认主题为 light', () => {
      localStorageMock.getItem.mockReturnValueOnce(null)
      const store = useGlobalStore()
      expect(store.theme).toBe('light')
      expect(store.isDark).toBe(false)
    })

    it('从 localStorage 读取已保存的主题', () => {
      localStorageMock.getItem.mockReturnValueOnce('dark')
      const store = useGlobalStore()
      expect(store.theme).toBe('dark')
      expect(store.isDark).toBe(true)
    })

    it('toggleTheme 切换主题并持久化', () => {
      localStorageMock.getItem.mockReturnValueOnce('light')
      const store = useGlobalStore()
      store.toggleTheme()
      expect(store.theme).toBe('dark')
      expect(store.isDark).toBe(true)
      expect(localStorageMock.setItem).toHaveBeenCalledWith('edu-rag-theme', 'dark')
    })

    it('toggleTheme 从 dark 切换回 light', () => {
      localStorageMock.getItem.mockReturnValueOnce('dark')
      const store = useGlobalStore()
      store.toggleTheme()
      expect(store.theme).toBe('light')
      expect(localStorageMock.setItem).toHaveBeenCalledWith('edu-rag-theme', 'light')
    })

    it('initTheme 设置 document data-theme 属性', () => {
      localStorageMock.getItem.mockReturnValueOnce('dark')
      const store = useGlobalStore()
      store.initTheme()
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    })

    it('toggleTheme 后 data-theme 属性同步更新', () => {
      localStorageMock.getItem.mockReturnValueOnce('light')
      const store = useGlobalStore()
      store.initTheme()
      store.toggleTheme()
      expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    })
  })

  describe('统计数据', () => {
    it('初始统计数据为 0', () => {
      const store = useGlobalStore()
      expect(store.stats).toEqual({
        kbCount: 0,
        docCount: 0,
        qaCount: 0,
        examCount: 0,
      })
    })

    it('updateStats 部分更新统计数据', () => {
      const store = useGlobalStore()
      store.updateStats({ kbCount: 5, docCount: 10 })
      expect(store.stats.kbCount).toBe(5)
      expect(store.stats.docCount).toBe(10)
      expect(store.stats.qaCount).toBe(0)
      expect(store.stats.examCount).toBe(0)
    })

    it('updateStats 保留未更新的字段', () => {
      const store = useGlobalStore()
      store.updateStats({ kbCount: 3 })
      store.updateStats({ docCount: 7 })
      expect(store.stats.kbCount).toBe(3)
      expect(store.stats.docCount).toBe(7)
    })
  })

  describe('当前知识库', () => {
    it('初始 currentKbId 为 undefined（当 localStorage 无值）', () => {
      localStorageMock.getItem.mockReturnValueOnce(null)
      const store = useGlobalStore()
      expect(store.currentKbId).toBeUndefined()
    })

    it('从 localStorage 读取已保存的 currentKbId', () => {
      // 预设 localStorage 中的值（store 初始化时会读 theme 和 currentKbId）
      localStorageStore['edu-rag-current-kb'] = '24'
      const store = useGlobalStore()
      expect(store.currentKbId).toBe(24)
    })

    it('setCurrentKb 设置并持久化', () => {
      const store = useGlobalStore()
      store.setCurrentKb(42)
      expect(store.currentKbId).toBe(42)
      expect(localStorageMock.setItem).toHaveBeenCalledWith('edu-rag-current-kb', '42')
    })

    it('setCurrentKb 传入 undefined 时移除持久化', () => {
      const store = useGlobalStore()
      store.setCurrentKb(42)
      store.setCurrentKb(undefined)
      expect(store.currentKbId).toBeUndefined()
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('edu-rag-current-kb')
    })
  })
})
