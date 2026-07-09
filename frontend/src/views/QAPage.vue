<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { MessageOutlined, SendOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons-vue'
import { listKnowledgeBases } from '../api/knowledge'
import { askQuestion, askQuestionStream } from '../api/qa'
import type { KnowledgeBase, SourceItem } from '../api/types'
import { message } from 'ant-design-vue'
import { marked } from 'marked'

const kbList = ref<KnowledgeBase[]>([])
const selectedKbId = ref<number | undefined>()
const topK = ref(5)
const question = ref('')
const streaming = ref(false)
const chatArea = ref<HTMLDivElement>()

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: SourceItem[]
  streaming?: boolean
}

const messages = ref<ChatMessage[]>([])

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

async function handleAsk() {
  const q = question.value.trim()
  if (!q) return
  question.value = ''

  messages.value.push({ role: 'user', content: q })
  const aiMsg: ChatMessage = { role: 'assistant', content: '', streaming: true }
  messages.value.push(aiMsg)
  scrollToBottom()

  streaming.value = true
  const kbId = selectedKbId.value || undefined

  try {
    // 使用 SSE 流式
    let fullAnswer = ''
    let sources: SourceItem[] = []

    const resp = await fetch('/api/qa/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, knowledge_base_id: kbId || null, top_k: topK.value }),
    })

    if (!resp.ok) {
      // 降级到非流式
      const data = await askQuestion({ question: q, knowledge_base_id: kbId || null, top_k: topK.value })
      aiMsg.content = data.answer
      aiMsg.sources = data.sources
      aiMsg.streaming = false
      scrollToBottom()
      return
    }

    const reader = resp.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

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
            aiMsg.streaming = false
            continue
          }
          // 解析来源 JSON
          if (token.startsWith('{') && token.includes('"sources"')) {
            try {
              const parsed = JSON.parse(token)
              if (parsed.type === 'sources' && parsed.data) {
                sources = parsed.data
                aiMsg.sources = sources
              }
            } catch {}
            continue
          }
          fullAnswer += token
          aiMsg.content = fullAnswer
          scrollToBottom()
        }
      }
    }

    aiMsg.streaming = false
    // 如果没有从流中获取到 sources，用非流式补充
    if (sources.length === 0 && fullAnswer) {
      aiMsg.sources = []
    }
  } catch (e: any) {
    aiMsg.content = `请求失败: ${e.message}`
    aiMsg.streaming = false
  } finally {
    streaming.value = false
  }
}

function renderMarkdown(text: string) {
  if (!text) return ''
  return marked.parse(text, { breaks: true, gfm: true }) as string
}

onMounted(loadKBs)
</script>

<template>
  <div>
    <h2 style="margin-bottom: 24px"><MessageOutlined /> 智能问答</h2>
    <a-row :gutter="16">
      <a-col :span="18">
        <a-card :body-style="{ padding: 0 }">
          <!-- 设置栏 -->
          <div style="padding: 12px 16px; border-bottom: 1px solid #f0f0f0; display: flex; gap: 12px; align-items: center">
            <a-select v-model:value="selectedKbId" placeholder="全部知识库" style="flex: 1" allow-clear>
              <a-select-option v-for="kb in kbList" :key="kb.id" :value="kb.id">{{ kb.name }}</a-select-option>
            </a-select>
            <span style="white-space: nowrap; color: #999">片段数:</span>
            <a-select v-model:value="topK" style="width: 80px">
              <a-select-option :value="3">3</a-select-option>
              <a-select-option :value="5">5</a-select-option>
              <a-select-option :value="10">10</a-select-option>
              <a-select-option :value="15">15</a-select-option>
            </a-select>
          </div>

          <!-- 对话区 -->
          <div ref="chatArea" style="height: 450px; overflow-y: auto; padding: 16px; background: #fafafa">
            <div v-if="messages.length === 0" style="text-align: center; padding: 80px 0; color: #999">
              <RobotOutlined :style="{ fontSize: '64px', display: 'block', marginBottom: '16px' }" />
              <p>在下方输入问题，基于知识库内容获取回答</p>
            </div>
            <div v-for="(m, i) in messages" :key="i" style="margin-bottom: 16px">
              <!-- 用户消息 -->
              <div v-if="m.role === 'user'" style="display: flex; justify-content: flex-end">
                <div style="background: #1677ff; color: #fff; border-radius: 8px; padding: 12px 16px; max-width: 80%">
                  <p style="margin: 0">{{ m.content }}</p>
                </div>
              </div>
              <!-- AI 消息 -->
              <div v-else style="display: flex; gap: 8px">
                <RobotOutlined style="font-size: 20px; color: #1677ff; margin-top: 4px" />
                <div style="background: #fff; border: 1px solid #e8e8e8; border-radius: 8px; padding: 12px 16px; max-width: 85%">
                  <div v-if="m.content" class="markdown-body" v-html="renderMarkdown(m.content)"></div>
                  <span v-else-if="m.streaming" style="color: #999">思考中...</span>
                  <template v-if="m.sources && m.sources.length">
                    <a-divider style="margin: 8px 0" />
                    <small style="color: #999">参考来源：
                      <a-tag v-for="s in m.sources" :key="s.doc_id" color="blue" size="small">
                        文档#{{ s.doc_id }} ({{ (s.score * 100).toFixed(0) }}%)
                      </a-tag>
                    </small>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <!-- 输入区 -->
          <div style="padding: 12px 16px; border-top: 1px solid #f0f0f0; display: flex; gap: 8px">
            <a-textarea
              v-model:value="question"
              :auto-size="{ minRows: 1, maxRows: 4 }"
              placeholder="输入你的问题..."
              style="flex: 1"
              @keydown.enter.exact.prevent="handleAsk"
            />
            <a-button type="primary" :loading="streaming" @click="handleAsk"><SendOutlined /> 发送</a-button>
          </div>
        </a-card>
      </a-col>

      <a-col :span="6">
        <a-card title="使用说明" size="small">
          <ul style="padding-left: 20px; font-size: 14px; color: #666">
            <li>选择知识库范围提问</li>
            <li>系统自动检索相关文档片段</li>
            <li>基于检索结果生成回答</li>
            <li>回答底部会标注引用来源</li>
            <li>支持 Markdown 格式回答</li>
          </ul>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<style scoped>
.markdown-body :deep(pre) {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
}
.markdown-body :deep(code) {
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 2px;
  font-size: 13px;
}
.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #ddd;
  padding: 8px;
  text-align: left;
}
</style>
