import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SourceItem } from '../api/types'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceItem[]
  streaming?: boolean
  feedback?: 'like' | 'dislike' | null
  createdAt: number
}

export interface ChatSession {
  id: string
  title: string
  kbId?: number
  messages: ChatMessage[]
  updatedAt: number
}

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string>('')

  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value)
  )

  const currentMessages = computed(() => currentSession.value?.messages || [])

  function loadSessions() {
    try {
      const raw = localStorage.getItem('edu-rag-chat-sessions')
      if (raw) sessions.value = JSON.parse(raw)
    } catch { /* ignore */ }
  }

  function saveSessions() {
    localStorage.setItem('edu-rag-chat-sessions', JSON.stringify(sessions.value))
  }

  function createSession(kbId?: number, title?: string) {
    const session: ChatSession = {
      id: generateId(),
      title: title || '新对话',
      kbId,
      messages: [],
      updatedAt: Date.now(),
    }
    sessions.value.unshift(session)
    currentSessionId.value = session.id
    saveSessions()
    return session
  }

  function switchSession(id: string) {
    currentSessionId.value = id
  }

  function deleteSession(id: string) {
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (currentSessionId.value === id) {
      currentSessionId.value = sessions.value[0]?.id || ''
    }
    saveSessions()
  }

  function renameSession(id: string, title: string) {
    const s = sessions.value.find(s => s.id === id)
    if (s) { s.title = title; saveSessions() }
  }

  function addMessage(sessionId: string, msg: Omit<ChatMessage, 'id' | 'createdAt'>) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (!session) return
    const fullMsg: ChatMessage = { ...msg, id: generateId(), createdAt: Date.now() }
    session.messages.push(fullMsg)
    session.updatedAt = Date.now()
    if (msg.role === 'assistant' && session.title === '新对话' && session.messages.length === 2) {
      const userMsg = session.messages[0]
      session.title = userMsg.content.slice(0, 20) + (userMsg.content.length > 20 ? '...' : '')
    }
    saveSessions()
  }

  function updateMessage(sessionId: string, index: number, patch: Partial<ChatMessage>) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (!session || !session.messages[index]) return
    Object.assign(session.messages[index], patch)
    session.updatedAt = Date.now()
    saveSessions()
  }

  function setFeedback(sessionId: string, messageIndex: number, feedback: 'like' | 'dislike') {
    updateMessage(sessionId, messageIndex, { feedback })
  }

  function clearSessionMessages(sessionId: string) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      session.messages = []
      session.updatedAt = Date.now()
      saveSessions()
    }
  }

  return {
    sessions,
    currentSessionId,
    currentSession,
    currentMessages,
    loadSessions,
    saveSessions,
    createSession,
    switchSession,
    deleteSession,
    renameSession,
    addMessage,
    updateMessage,
    setFeedback,
    clearSessionMessages,
  }
})
