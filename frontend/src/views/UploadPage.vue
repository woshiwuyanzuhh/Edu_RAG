<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { CloudUploadOutlined, InboxOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { listKnowledgeBases } from '../api/knowledge'
import { uploadDocument, listDocuments, deleteDocument } from '../api/documents'
import type { KnowledgeBase, DocumentItem } from '../api/types'
import { message } from 'ant-design-vue'

const route = useRoute()
const kbList = ref<KnowledgeBase[]>([])
const selectedKbId = ref<number | undefined>()
const docType = ref('general')
const docList = ref<DocumentItem[]>([])
const uploading = ref(false)
const fileList = ref<any[]>([])
const docLoading = ref(false)

async function loadKBs() {
  try {
    const data = await listKnowledgeBases(1, 100)
    kbList.value = data.items
    const urlKb = route.query.kb
    if (urlKb) selectedKbId.value = Number(urlKb)
  } catch {}
}

async function loadDocs() {
  docLoading.value = true
  try {
    const data = await listDocuments(selectedKbId.value)
    docList.value = data.items
  } catch { docList.value = [] }
  finally { docLoading.value = false }
}

async function handleUpload() {
  if (!selectedKbId.value) return message.warning('请选择知识库')
  if (fileList.value.length === 0) return message.warning('请选择文件')
  uploading.value = true
  try {
    const file = fileList.value[0].originFileObj || fileList.value[0]
    const result = await uploadDocument(file, selectedKbId.value, docType.value)
    message.success(`上传成功，共 ${result.chunk_count} 个片段`)
    fileList.value = []
    loadDocs()
  } catch (e: any) { message.error(e.message) }
  finally { uploading.value = false }
}

async function handleDelete(doc: DocumentItem) {
  try { await deleteDocument(doc.id); message.success('已删除'); loadDocs() }
  catch (e: any) { message.error(e.message) }
}

function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const statusMap: Record<string, { color: string; text: string }> = {
  done: { color: 'success', text: '已完成' },
  processing: { color: 'processing', text: '处理中' },
  error: { color: 'error', text: '失败' },
}

watch(selectedKbId, loadDocs)
onMounted(loadKBs)

const docColumns = [
  { title: '文件名', dataIndex: 'filename', key: 'filename' },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '块数', dataIndex: 'chunk_count', key: 'chunk_count', width: 80 },
  { title: '大小', dataIndex: 'file_size', key: 'file_size', width: 100, customRender: ({ text }: { text: number }) => formatSize(text) },
  { title: '操作', key: 'action', width: 80 },
]
</script>

<template>
  <div>
    <h2 style="margin-bottom: 24px"><CloudUploadOutlined /> 文档上传</h2>
    <a-row :gutter="16">
      <a-col :span="16">
        <a-card title="上传文档">
          <a-form layout="vertical">
            <a-form-item label="选择知识库" required>
              <a-select v-model:value="selectedKbId" placeholder="请选择知识库" style="width: 100%">
                <a-select-option v-for="kb in kbList" :key="kb.id" :value="kb.id">{{ kb.name }}</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="文档类型">
              <a-select v-model:value="docType" style="width: 200px">
                <a-select-option value="general">通用</a-select-option>
                <a-select-option value="education">教育</a-select-option>
                <a-select-option value="gaming">游戏</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="选择文件">
              <a-upload-dragger v-model:file-list="fileList" :max-count="1" :before-upload="() => false" accept=".pdf,.txt,.docx,.doc,.md">
                <p class="ant-upload-drag-icon"><InboxOutlined /></p>
                <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
                <p class="ant-upload-hint">支持 PDF、Word (.docx)、Markdown (.md)、TXT</p>
              </a-upload-dragger>
            </a-form-item>
            <a-button type="primary" :loading="uploading" @click="handleUpload" :disabled="!selectedKbId || fileList.length === 0">
              <CloudUploadOutlined /> 上传并处理
            </a-button>
          </a-form>
        </a-card>
      </a-col>

      <a-col :span="8">
        <a-card title="说明" size="small" style="margin-bottom: 16px">
          <ul style="padding-left: 20px; font-size: 14px; color: #666">
            <li>上传后系统自动解析文档内容</li>
            <li>文本自动分块并生成向量</li>
            <li>向量存入 ChromaDB，支持语义检索</li>
            <li>文件大小限制：50MB</li>
          </ul>
        </a-card>
        <a-card title="已上传文档" size="small">
          <template #extra><a-button size="small" @click="loadDocs"><ReloadOutlined /></a-button></template>
          <a-table :columns="docColumns" :data-source="docList" :loading="docLoading" :pagination="false" row-key="id" size="small">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'">
                <a-tag :color="statusMap[record.status]?.color">{{ statusMap[record.status]?.text || record.status }}</a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <a-popconfirm title="确定删除？" @confirm="handleDelete(record)">
                  <a-button size="small" danger><DeleteOutlined /></a-button>
                </a-popconfirm>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>
