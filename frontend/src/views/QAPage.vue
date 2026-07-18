<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import {
  MessageOutlined,
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  PlusOutlined,
  DeleteOutlined,
  CopyOutlined,
  RedoOutlined,
  LikeOutlined,
  DislikeOutlined,
  LikeFilled,
  DislikeFilled,
  SearchOutlined,
  LoadingOutlined,
  MenuOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue'
import { listKnowledgeBases } from '../api/knowledge'
import { askQuestion, askQuestionStream } from '../api/qa'
import { sendFeedback } from '../api/feedback'
import type { KnowledgeBase, SourceItem } from '../api/types'
import { message } from 'ant-design-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useChatStore } from '../stores/chat'
import EmptyState from '../components/EmptyState.vue'

const chatStore = useChatStore()
const kbList = ref<KnowledgeBase[]>([])
const selectedKbId = ref<number | undefined>()
const topK = ref(5)
const question = ref('')
const streaming = ref(false)
const chatArea = ref<HTMLDivElement>()
const sidebarCollapsed = ref(false)
const mobileSidebarOpen = ref(false)
const searchKey = ref('')
const retrieving = ref(false)

// Ensure chat store is loaded
chatStore.loadSessions()

const filteredSessions = computed(() => {
  if (!searchKey.value) return chatStore.sessions
  return chatStore.sessions.filter(s =>
    s.title.toLowerCase().includes(searchKey.value.toLowerCase())
  )
})

async function loadKBs() {
  try {
    const data = await listKnowledgeBases(1, 100)
    kbList.value = data.items
  } catch {}
}

function scrollToBottom() {
  nextTick(() => {
    if (chatArea.value) chatArea.value.scrollTop = chatArea.value.scrollHeight
  })
}

function formatTime(ts: number) {
  const d = new Date(ts)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function handleAsk() {
  const q = question.value.trim()
  if (!q || streaming.value) return
  question.value = ''

  // Ensure we have an active session
  if (!chatStore.currentSessionId) {
    chatStore.createSession(selectedKbId.value)
  }

  const sessionId = chatStore.currentSessionId
  const kbId = selectedKbId.value || undefined

  // Add user message
  chatStore.addMessage(sessionId!, { role: 'user', content: q })
  scrollToBottom()

  // Add assistant placeholder
  chatStore.addMessage(sessionId!, { role: 'assistant', content: '', streaming: true })
  const msgIndex = chatStore.currentMessages.length - 1
  scrollToBottom()

  streaming.value = true
  retrieving.value = true

  try {
    const resp = await fetch('/api/qa/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: q,
        knowledge_base_id: kbId || null,
        top_k: topK.value,
      }),
    })

    retrieving.value = false

    if (!resp.ok) {
      // Fallback to non-streaming
      const data = await askQuestion({
        question: q,
        knowledge_base_id: kbId || null,
        top_k: topK.value,
      })
      chatStore.updateMessage(sessionId!, msgIndex, {
        content: data.answer,
        sources: data.sources,
        streaming: false,
      })
      scrollToBottom()
      return
    }

    const reader = resp.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullAnswer = ''
    let sources: SourceItem[] = []

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const token = line.slice(6)
          if (token === '[DONE]') {
            chatStore.updateMessage(sessionId!, msgIndex, { streaming: false })
            continue
          }
          if (token.startsWith('{') && token.includes('"sources"')) {
            try {
              const parsed = JSON.parse(token)
              if (parsed.type === 'sources' && parsed.data) {
                sources = parsed.data
                chatStore.updateMessage(sessionId!, msgIndex, { sources })
              }
            } catch {}
            continue
          }
          fullAnswer += token
          chatStore.updateMessage(sessionId!, msgIndex, { content: fullAnswer })
          scrollToBottom()
        }
      }
    }
  } catch (e: any) {
    chatStore.updateMessage(sessionId!, msgIndex, {
      content: `请求失败: ${e.message}`,
      streaming: false,
    })
  } finally {
    streaming.value = false
    retrieving.value = false
  }
}

async function handleRegenerate(msgIndex: number) {
  // Find the user message before this assistant message
  const session = chatStore.currentSession
  if (!session) return
  let userMsgIndex = -1
  for (let i = msgIndex - 1; i >= 0; i--) {
    if (session.messages[i].role === 'user') {
      userMsgIndex = i
      break
    }
  }
  if (userMsgIndex < 0) return

  const userMsg = session.messages[userMsgIndex]
  question.value = userMsg.content

  // Remove the old assistant message and any messages after it
  session.messages = session.messages.slice(0, msgIndex)
  chatStore.saveSessions()

  // Trigger ask
  await handleAsk()
}

function handleCopy(content: string) {
  navigator.clipboard.writeText(content).then(() => {
    message.success('已复制到剪贴板')
  }).catch(() => {
    message.error('复制失败')
  })
}

async function handleFeedback(msgIndex: number, rating: 'like' | 'dislike') {
  const session = chatStore.currentSession
  if (!session) return
  const msg = session.messages[msgIndex]
  const userMsg = session.messages[msgIndex - 1]
  if (!userMsg || userMsg.role !== 'user') return

  chatStore.setFeedback(session.id, msgIndex, rating)

  try {
    await sendFeedback({
      question: userMsg.content,
      answer: msg.content,
      rating,
    })
  } catch {
    // Silent fail for feedback
  }
}

function handleNewChat() {
  chatStore.createSession(selectedKbId.value)
  mobileSidebarOpen.value = false
}

function handleSelectSession(id: string) {
  chatStore.switchSession(id)
  const session = chatStore.sessions.find(s => s.id === id)
  if (session?.kbId) {
    selectedKbId.value = session.kbId
  }
  mobileSidebarOpen.value = false
}

function handleDeleteSession(id: string) {
  chatStore.deleteSession(id)
}

function renderMarkdown(text: string) {
  if (!text) return ''
  // P1-2: DOMPurify 净化，防止存储型 XSS（LLM 输出可能含恶意 HTML/JS）
  return DOMPurify.sanitize(marked.parse(text, { breaks: true, gfm: true }) as string)
}

onMounted(() => {
  loadKBs()
  if (!chatStore.currentSessionId) {
    chatStore.createSession()
  }
})

watch(() => chatStore.currentMessages, scrollToBottom, { deep: true })
</script>

<template>
  <div class="qa-page">
    <div class="qa-layout">
      <!-- ========== 桌面端侧边栏 ========== -->
      <aside class="qa-sidebar hidden-mobile" :class="{ collapsed: sidebarCollapsed }">
        <div class="sidebar-inner">
          <a-button type="primary" block size="large" class="new-chat-btn" @click="handleNewChat">
            <PlusOutlined /> 新对话
          </a-button>
          <a-input
            v-model:value="searchKey"
            placeholder="搜索会话..."
            size="middle"
            class="sidebar-search"
          >
            <template #prefix><SearchOutlined /></template>
          </a-input>
          <div class="session-list">
            <div
              v-for="(s, idx) in filteredSessions"
              :key="s.id"
              class="session-item stagger-in"
              :style="{ '--i': idx }"
              :class="{ active: s.id === chatStore.currentSessionId }"
              @click="handleSelectSession(s.id)"
            >
              <div class="session-content">
                <div class="session-title truncate">{{ s.title }}</div>
                <div class="session-meta">
                  <span>{{ s.messages.length }} 条</span>
                  <span>·</span>
                  <span>{{ formatTime(s.updatedAt) }}</span>
                </div>
              </div>
              <a-button
                v-if="s.id === chatStore.currentSessionId"
                type="text"
                size="small"
                class="session-delete"
                danger
                @click.stop="handleDeleteSession(s.id)"
              >
                <DeleteOutlined />
              </a-button>
            </div>
          </div>
        </div>
      </aside>

      <!-- ========== 主聊天区 ========== -->
      <main class="qa-main">
        <!-- 工具栏 -->
        <div class="chat-toolbar">
          <div class="toolbar-left">
            <a-button
              type="text"
              size="small"
              class="toolbar-btn hidden-mobile"
              @click="sidebarCollapsed = !sidebarCollapsed"
            >
              <MenuOutlined />
            </a-button>
            <a-button
              type="text"
              size="small"
              class="toolbar-btn hidden-desktop"
              @click="mobileSidebarOpen = true"
            >
              <MenuOutlined />
            </a-button>
            <a-select
              v-model:value="selectedKbId"
              placeholder="全部知识库"
              style="width: 160px"
              allow-clear
              size="small"
            >
              <a-select-option v-for="kb in kbList" :key="kb.id" :value="kb.id">{{ kb.name }}</a-select-option>
            </a-select>
          </div>
          <div class="toolbar-right">
            <span class="toolbar-label">片段数</span>
            <a-select v-model:value="topK" style="width: 64px" size="small">
              <a-select-option :value="3">3</a-select-option>
              <a-select-option :value="5">5</a-select-option>
              <a-select-option :value="10">10</a-select-option>
              <a-select-option :value="15">15</a-select-option>
            </a-select>
          </div>
        </div>

        <!-- 消息区 -->
        <div ref="chatArea" class="chat-messages">
          <EmptyState
            v-if="chatStore.currentMessages.length === 0"
            type="robot"
            title="开始对话"
            description="在下方输入问题，基于知识库内容获取回答。支持 Markdown 格式。"
          />

          <div
            v-for="(m, i) in chatStore.currentMessages"
            :key="m.id"
            class="message-wrapper fade-in"
            :class="m.role"
          >
            <!-- 用户消息 -->
            <div v-if="m.role === 'user'" class="msg-user">
              <div class="msg-bubble-user">
                <p>{{ m.content }}</p>
              </div>
              <div class="msg-avatar msg-avatar-user">
                <UserOutlined />
              </div>
            </div>

            <!-- AI 消息 -->
            <div v-else class="msg-ai">
              <div class="msg-avatar msg-avatar-ai">
                <RobotOutlined />
              </div>
              <div class="msg-bubble-ai">
                <!-- 检索中 -->
                <div v-if="retrieving && m.streaming && !m.content" class="retrieving-indicator">
                  <LoadingOutlined spin />
                  <span>正在检索相关文档...</span>
                </div>

                <!-- 内容 -->
                <div v-if="m.content" class="markdown-body" v-html="renderMarkdown(m.content)"></div>
                <span v-else-if="m.streaming && !retrieving" class="typing-cursor thinking-text">思考中</span>

                <!-- 参考来源 -->
                <template v-if="m.sources && m.sources.length">
                  <div class="msg-sources">
                    <div class="sources-label">参考来源</div>
                    <div class="sources-tags">
                      <a-tag
                        v-for="s in m.sources"
                        :key="s.doc_id + '-' + s.chunk_index"
                        color="blue"
                        size="small"
                        class="source-tag"
                      >
                        文档#{{ s.doc_id }} · {{ (s.score * 100).toFixed(0) }}%
                      </a-tag>
                    </div>
                  </div>
                </template>

                <!-- 操作按钮 -->
                <div v-if="!m.streaming" class="msg-actions">
                  <a-tooltip title="重新生成">
                    <a-button type="text" size="small" @click="handleRegenerate(i)">
                      <RedoOutlined />
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="复制">
                    <a-button type="text" size="small" @click="handleCopy(m.content)">
                      <CopyOutlined />
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="有用">
                    <a-button
                      type="text"
                      size="small"
                      :class="{ 'action-active': m.feedback === 'like' }"
                      @click="handleFeedback(i, 'like')"
                    >
                      <LikeOutlined v-if="m.feedback !== 'like'" />
                      <LikeFilled v-else class="action-liked" />
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="无用">
                    <a-button
                      type="text"
                      size="small"
                      :class="{ 'action-active': m.feedback === 'dislike' }"
                      @click="handleFeedback(i, 'dislike')"
                    >
                      <DislikeOutlined v-if="m.feedback !== 'dislike'" />
                      <DislikeFilled v-else class="action-disliked" />
                    </a-button>
                  </a-tooltip>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="chat-input-area">
          <a-textarea
            v-model:value="question"
            :auto-size="{ minRows: 1, maxRows: 4 }"
            placeholder="输入你的问题...（Enter 发送，Shift+Enter 换行）"
            class="chat-input"
            @keydown.enter.exact.prevent="handleAsk"
          />
          <a-button
            type="primary"
            :loading="streaming"
            :disabled="!question.trim()"
            class="chat-send-btn"
            @click="handleAsk"
          >
            <SendOutlined />
          </a-button>
        </div>
      </main>
    </div>

    <!-- ========== 移动端侧边栏抽屉 ========== -->
    <a-drawer
      v-model:open="mobileSidebarOpen"
      placement="left"
      :width="280"
      :closable="false"
      class="mobile-sidebar-drawer"
    >
      <template #title>
        <div class="drawer-header">
          <span>历史会话</span>
          <a-button type="text" size="small" @click="mobileSidebarOpen = false">
            <DeleteOutlined />
          </a-button>
        </div>
      </template>
      <a-button type="primary" block size="large" class="new-chat-btn" @click="handleNewChat">
        <PlusOutlined /> 新对话
      </a-button>
      <a-input
        v-model:value="searchKey"
        placeholder="搜索会话..."
        size="middle"
        class="sidebar-search"
      >
        <template #prefix><SearchOutlined /></template>
      </a-input>
      <div class="session-list">
        <div
          v-for="s in filteredSessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === chatStore.currentSessionId }"
          @click="handleSelectSession(s.id)"
        >
          <div class="session-content">
            <div class="session-title truncate">{{ s.title }}</div>
            <div class="session-meta">
              <span>{{ s.messages.length }} 条</span>
              <span>·</span>
              <span>{{ formatTime(s.updatedAt) }}</span>
            </div>
          </div>
        </div>
      </div>
    </a-drawer>
  </div>
</template>

<style scoped>
.qa-page {
  height: calc(100vh - var(--header-height) - var(--footer-height) - var(--space-lg) * 2);
}
.qa-layout {
  height: 100%;
  display: flex;
  gap: var(--space-md);
}

/* === 侧边栏 === */
.qa-sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  transition: width var(--duration-normal) var(--ease-premium);
}
.qa-sidebar.collapsed {
  width: 0;
  overflow: hidden;
}
.sidebar-inner {
  height: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-lg);
  padding: var(--space-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}
.new-chat-btn {
  font-weight: var(--font-weight-medium);
}
.sidebar-search {
  flex-shrink: 0;
}
.session-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.session-item {
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--border-radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-premium);
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  border: 1px solid transparent;
}
.session-item:hover {
  background: var(--bg-hover);
}
.session-item.active {
  background: var(--bg-active);
  border-color: rgba(22, 119, 255, 0.2);
}
.session-content {
  flex: 1;
  min-width: 0;
}
.session-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}
.session-meta {
  display: flex;
  gap: var(--space-xs);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}
.session-delete {
  opacity: 0;
  transition: opacity var(--duration-fast) ease;
  flex-shrink: 0;
}
.session-item:hover .session-delete {
  opacity: 1;
}

/* === 主聊天区 === */
.qa-main {
  flex: 1;
  min-width: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 工具栏 */
.chat-toolbar {
  padding: var(--space-sm) var(--space-md);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  flex-wrap: wrap;
  background: var(--bg-card);
}
.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.toolbar-btn {
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.toolbar-btn:hover {
  color: var(--color-primary);
}
.toolbar-label {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  white-space: nowrap;
}

/* 消息区 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md);
  background: var(--bg-body);
}
.message-wrapper {
  margin-bottom: var(--space-md);
}

/* 用户消息 */
.msg-user {
  display: flex;
  justify-content: flex-end;
  align-items: flex-start;
  gap: var(--space-sm);
}
.msg-bubble-user {
  background: var(--gradient-primary);
  color: #fff;
  border-radius: var(--border-radius-lg) var(--border-radius-lg) var(--border-radius-sm) var(--border-radius-lg);
  padding: var(--space-sm) var(--space-md);
  max-width: 75%;
  font-size: var(--font-size-base);
  line-height: var(--line-height-relaxed);
  word-break: break-word;
  box-shadow: var(--shadow-sm);
}
.msg-bubble-user p {
  margin: 0;
}

/* AI 消息 */
.msg-ai {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
}
.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--border-radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
}
.msg-avatar-user {
  background: var(--bg-hover);
  color: var(--text-secondary);
}
.msg-avatar-ai {
  background: var(--gradient-primary);
  color: #fff;
  box-shadow: var(--shadow-primary);
}
.msg-bubble-ai {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm) var(--border-radius-lg) var(--border-radius-lg) var(--border-radius-lg);
  padding: var(--space-sm) var(--space-md);
  max-width: 80%;
  font-size: var(--font-size-base);
  line-height: var(--line-height-relaxed);
  word-break: break-word;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--duration-fast) ease;
}
.msg-bubble-ai:hover {
  box-shadow: var(--shadow-md);
}

/* 检索中指示器 */
.retrieving-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  padding: var(--space-xs) 0;
}
.retrieving-indicator :deep(.anticon) {
  color: var(--color-primary);
}
.thinking-text {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}

/* 参考来源 */
.msg-sources {
  margin-top: var(--space-sm);
  padding-top: var(--space-sm);
  border-top: 1px solid var(--border-color);
}
.sources-label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--space-xs);
}
.sources-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
}
.source-tag {
  font-size: var(--font-size-xs);
}

/* 操作按钮 */
.msg-actions {
  display: flex;
  gap: 2px;
  margin-top: var(--space-sm);
  padding-top: var(--space-sm);
  border-top: 1px solid var(--border-color);
  opacity: 0;
  transition: opacity var(--duration-fast) ease;
}
.msg-bubble-ai:hover .msg-actions {
  opacity: 1;
}
.msg-actions :deep(.ant-btn) {
  padding: 0 var(--space-sm);
  height: 26px;
  color: var(--text-tertiary);
}
.msg-actions :deep(.ant-btn:hover) {
  color: var(--color-primary);
  background: var(--bg-hover);
}
.action-liked {
  color: var(--color-primary) !important;
}
.action-disliked {
  color: var(--color-error) !important;
}

/* 输入区 */
.chat-input-area {
  padding: var(--space-sm) var(--space-md);
  border-top: 1px solid var(--border-color);
  display: flex;
  gap: var(--space-sm);
  background: var(--bg-card);
}
.chat-input {
  flex: 1;
}
.chat-input :deep(.ant-input) {
  border-radius: var(--border-radius-lg);
  padding: var(--space-sm) var(--space-md);
}
.chat-send-btn {
  align-self: flex-end;
  height: var(--btn-height-lg);
  width: var(--btn-height-lg);
  border-radius: var(--border-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

/* 抽屉标题 */
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: var(--font-weight-semibold);
}

/* === 响应式 === */
@media (max-width: 768px) {
  .qa-page {
    height: calc(100vh - var(--header-height) - var(--footer-height) - var(--space-md) * 2);
  }
  .msg-bubble-user,
  .msg-bubble-ai {
    max-width: 90%;
  }
}
</style>
