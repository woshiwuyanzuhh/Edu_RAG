import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '../chat'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value }),
    removeItem: vi.fn((key: string) => { delete store[key] }),
    clear: vi.fn(() => { store = {} }),
  }
})()
vi.stubGlobal('localStorage', localStorageMock)

beforeEach(() => {
  setActivePinia(createPinia())
  localStorageMock.clear()
  localStorageMock.getItem.mockClear()
  localStorageMock.setItem.mockClear()
})

describe('chat store', () => {
  describe('初始状态', () => {
    it('sessions 为空数组', () => {
      const store = useChatStore()
      expect(store.sessions).toEqual([])
    })

    it('currentSessionId 为空字符串', () => {
      const store = useChatStore()
      expect(store.currentSessionId).toBe('')
    })

    it('currentSession 为 undefined', () => {
      const store = useChatStore()
      expect(store.currentSession).toBeUndefined()
    })

    it('currentMessages 为空数组', () => {
      const store = useChatStore()
      expect(store.currentMessages).toEqual([])
    })
  })

  describe('createSession', () => {
    it('创建新会话并设为当前会话', () => {
      const store = useChatStore()
      const session = store.createSession(24)
      expect(store.sessions).toHaveLength(1)
      expect(store.sessions[0]).toEqual(session)
      expect(store.currentSessionId).toBe(session.id)
      expect(session.title).toBe('新对话')
      expect(session.kbId).toBe(24)
      expect(session.messages).toEqual([])
    })

    it('使用自定义标题', () => {
      const store = useChatStore()
      const session = store.createSession(undefined, '我的对话')
      expect(session.title).toBe('我的对话')
    })

    it('新会话插入到列表头部', () => {
      const store = useChatStore()
      const s1 = store.createSession()
      const s2 = store.createSession()
      expect(store.sessions[0].id).toBe(s2.id)
      expect(store.sessions[1].id).toBe(s1.id)
    })

    it('创建后持久化到 localStorage', () => {
      const store = useChatStore()
      store.createSession()
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'edu-rag-chat-sessions',
        expect.any(String),
      )
    })
  })

  describe('switchSession', () => {
    it('切换当前会话', () => {
      const store = useChatStore()
      const s1 = store.createSession()
      const s2 = store.createSession()
      store.switchSession(s1.id)
      expect(store.currentSessionId).toBe(s1.id)
      store.switchSession(s2.id)
      expect(store.currentSessionId).toBe(s2.id)
    })
  })

  describe('deleteSession', () => {
    it('删除指定会话', () => {
      const store = useChatStore()
      const s1 = store.createSession()
      const s2 = store.createSession()
      store.deleteSession(s2.id)
      expect(store.sessions).toHaveLength(1)
      expect(store.sessions[0].id).toBe(s1.id)
    })

    it('删除当前会话后自动切换到第一个', () => {
      const store = useChatStore()
      const s1 = store.createSession()
      const s2 = store.createSession()
      store.deleteSession(s2.id)
      expect(store.currentSessionId).toBe(s1.id)
    })

    it('删除所有会话后 currentSessionId 为空', () => {
      const store = useChatStore()
      const s1 = store.createSession()
      store.deleteSession(s1.id)
      expect(store.sessions).toHaveLength(0)
      expect(store.currentSessionId).toBe('')
    })
  })

  describe('renameSession', () => {
    it('重命名会话', () => {
      const store = useChatStore()
      const session = store.createSession()
      store.renameSession(session.id, '重命名后的标题')
      expect(store.sessions[0].title).toBe('重命名后的标题')
    })

    it('重命名不存在的会话不会报错', () => {
      const store = useChatStore()
      expect(() => store.renameSession('nonexistent', '标题')).not.toThrow()
    })
  })

  describe('addMessage', () => {
    it('向会话添加消息', () => {
      const store = useChatStore()
      const session = store.createSession()
      store.addMessage(session.id, {
        role: 'user',
        content: '你好',
      })
      expect(session.messages).toHaveLength(1)
      expect(session.messages[0].role).toBe('user')
      expect(session.messages[0].content).toBe('你好')
      expect(session.messages[0].id).toBeTruthy()
      expect(session.messages[0].createdAt).toBeGreaterThan(0)
    })

    it('向不存在的会话添加消息不会报错', () => {
      const store = useChatStore()
      expect(() => {
        store.addMessage('nonexistent', { role: 'user', content: '测试' })
      }).not.toThrow()
    })

    it('首条 assistant 消息后自动更新会话标题', () => {
      const store = useChatStore()
      const session = store.createSession()
      // 使用超过 20 字符的用户消息，标题应截取前 20 字符并加 ...
      const longQuestion = '什么是机器学习的基本概念和应用场景？请详细说明'
      store.addMessage(session.id, { role: 'user', content: longQuestion })
      store.addMessage(session.id, { role: 'assistant', content: '机器学习是...' })
      expect(session.title).toBe(longQuestion.slice(0, 20) + '...')
      expect(session.title.endsWith('...')).toBe(true)
    })

    it('标题已不是"新对话"时不自动更新', () => {
      const store = useChatStore()
      const session = store.createSession(undefined, '自定义标题')
      store.addMessage(session.id, { role: 'user', content: '问题' })
      store.addMessage(session.id, { role: 'assistant', content: '回答' })
      expect(session.title).toBe('自定义标题')
    })
  })

  describe('updateMessage', () => {
    it('更新指定消息', () => {
      const store = useChatStore()
      const session = store.createSession()
      store.addMessage(session.id, { role: 'user', content: '原始' })
      store.updateMessage(session.id, 0, { content: '更新后' })
      expect(session.messages[0].content).toBe('更新后')
    })

    it('更新不存在的消息不会报错', () => {
      const store = useChatStore()
      const session = store.createSession()
      expect(() => store.updateMessage(session.id, 99, { content: 'x' })).not.toThrow()
    })
  })

  describe('setFeedback', () => {
    it('设置消息反馈', () => {
      const store = useChatStore()
      const session = store.createSession()
      store.addMessage(session.id, { role: 'assistant', content: '回答' })
      store.setFeedback(session.id, 0, 'like')
      expect(session.messages[0].feedback).toBe('like')
    })

    it('切换反馈', () => {
      const store = useChatStore()
      const session = store.createSession()
      store.addMessage(session.id, { role: 'assistant', content: '回答' })
      store.setFeedback(session.id, 0, 'like')
      store.setFeedback(session.id, 0, 'dislike')
      expect(session.messages[0].feedback).toBe('dislike')
    })
  })

  describe('clearSessionMessages', () => {
    it('清空会话消息', () => {
      const store = useChatStore()
      const session = store.createSession()
      store.addMessage(session.id, { role: 'user', content: '测试' })
      store.addMessage(session.id, { role: 'assistant', content: '回答' })
      store.clearSessionMessages(session.id)
      expect(session.messages).toHaveLength(0)
    })

    it('清空不存在的会话不会报错', () => {
      const store = useChatStore()
      expect(() => store.clearSessionMessages('nonexistent')).not.toThrow()
    })
  })

  describe('loadSessions', () => {
    it('从 localStorage 加载会话', () => {
      const saved = JSON.stringify([
        { id: 'abc', title: '已保存', messages: [], updatedAt: 1000 },
      ])
      localStorageMock.getItem.mockReturnValueOnce(saved)
      const store = useChatStore()
      store.loadSessions()
      expect(store.sessions).toHaveLength(1)
      expect(store.sessions[0].title).toBe('已保存')
    })

    it('localStorage 无数据时不加载', () => {
      localStorageMock.getItem.mockReturnValueOnce(null)
      const store = useChatStore()
      store.loadSessions()
      expect(store.sessions).toEqual([])
    })

    it('JSON 解析失败时静默忽略', () => {
      localStorageMock.getItem.mockReturnValueOnce('invalid json')
      const store = useChatStore()
      expect(() => store.loadSessions()).not.toThrow()
      expect(store.sessions).toEqual([])
    })
  })

  describe('saveSessions', () => {
    it('将会话序列化到 localStorage', () => {
      const store = useChatStore()
      store.createSession()
      store.saveSessions()
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'edu-rag-chat-sessions',
        expect.any(String),
      )
      const saved = localStorageMock.setItem.mock.calls.find(
        (c) => c[0] === 'edu-rag-chat-sessions',
      )
      expect(saved).toBeDefined()
      const parsed = JSON.parse(saved![1])
      expect(parsed).toHaveLength(1)
    })
  })
})
