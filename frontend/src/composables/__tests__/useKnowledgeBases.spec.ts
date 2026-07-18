import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useKnowledgeBases } from '../useKnowledgeBases'
import type { KnowledgeBase } from '../../api/types'

// Mock vue 的 onMounted，避免在非组件上下文中调用报 warn
vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue')>()
  return {
    ...actual,
    onMounted: vi.fn((fn?: () => void) => {
      // 在测试环境中不自动执行，避免无组件实例的 warn
    }),
  }
})

// Mock ant-design-vue message
vi.mock('ant-design-vue', () => ({
  message: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

// Mock API
vi.mock('../../api/knowledge', () => ({
  listKnowledgeBases: vi.fn(),
}))

import { listKnowledgeBases } from '../../api/knowledge'
import { message } from 'ant-design-vue'

const mockListKB = vi.mocked(listKnowledgeBases)
const mockMessage = vi.mocked(message)

const mockKBList: KnowledgeBase[] = [
  { id: 1, name: '知识库A', description: '描述A', created_at: '', updated_at: '' },
  { id: 2, name: '知识库B', description: '描述B', created_at: '', updated_at: '' },
]

beforeEach(() => {
  mockListKB.mockReset()
  mockMessage.error.mockReset()
})

describe('useKnowledgeBases', () => {
  it('初始状态：kbList 为空，loading 为 false', () => {
    // 不触发 onMounted，仅测试初始 ref 状态
    const { kbList, loading } = useKnowledgeBases()
    expect(kbList.value).toEqual([])
    expect(loading.value).toBe(false)
  })

  it('load 成功后填充 kbList', async () => {
    mockListKB.mockResolvedValueOnce({
      items: mockKBList,
      total: 2,
      page: 1,
      page_size: 100,
      pages: 1,
    })
    const { kbList, load, loading } = useKnowledgeBases()
    await load(1, 100)
    expect(kbList.value).toEqual(mockKBList)
    expect(loading.value).toBe(false)
  })

  it('load 时 loading 先变 true 再变 false', async () => {
    mockListKB.mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 100, pages: 0 })
    const { load, loading } = useKnowledgeBases()

    const promise = load()
    expect(loading.value).toBe(true)
    await promise
    expect(loading.value).toBe(false)
  })

  it('load 失败时显示错误消息', async () => {
    const error = new Error('网络错误')
    mockListKB.mockRejectedValueOnce(error)
    const { load, loading } = useKnowledgeBases()

    await load()
    expect(loading.value).toBe(false)
    expect(mockMessage.error).toHaveBeenCalledWith('网络错误')
  })

  it('load 失败且错误无 message 时使用默认消息', async () => {
    mockListKB.mockRejectedValueOnce({})
    const { load } = useKnowledgeBases()

    await load()
    expect(mockMessage.error).toHaveBeenCalledWith('加载知识库失败')
  })

  it('load 传递分页参数', async () => {
    mockListKB.mockResolvedValueOnce({ items: [], total: 0, page: 2, page_size: 50, pages: 0 })
    const { load } = useKnowledgeBases()

    await load(2, 50)
    expect(mockListKB).toHaveBeenCalledWith(2, 50)
  })
})
