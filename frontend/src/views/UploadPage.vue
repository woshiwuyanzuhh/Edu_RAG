<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  CloudUploadOutlined,
  InboxOutlined,
  DeleteOutlined,
  ReloadOutlined,
  FileOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import { listKnowledgeBases } from '../api/knowledge'
import { uploadDocument, listDocuments, deleteDocument } from '../api/documents'
import type { KnowledgeBase, DocumentItem, DocTypeOption } from '../api/types'
import { DOCUMENT_TYPES } from '../api/types'
import { message } from 'ant-design-vue'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import LoadingSkeleton from '../components/LoadingSkeleton.vue'

const route = useRoute()
const kbList = ref<KnowledgeBase[]>([])
const selectedKbId = ref<number | undefined>()
const docType = ref('general')
const docTypeOptions = ref<DocTypeOption[]>(DOCUMENT_TYPES)
const docList = ref<DocumentItem[]>([])
const uploading = ref(false)
const uploadProgress = ref<Record<string, number>>({})
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

const totalProgress = computed(() => {
  const values = Object.values(uploadProgress.value)
  if (values.length === 0) return 0
  return Math.round(values.reduce((a, b) => a + b, 0) / values.length)
})

async function handleUpload() {
  if (!selectedKbId.value) return message.warning('请选择知识库')
  if (fileList.value.length === 0) return message.warning('请选择文件')

  uploading.value = true
  uploadProgress.value = {}
  let successCount = 0
  let totalChunks = 0

  for (const fileItem of fileList.value) {
    const file = fileItem.originFileObj || fileItem
    const fileName = file.name || 'unknown'
    uploadProgress.value[fileName] = 0

    try {
      // Simulate progress animation
      const progressTimer = setInterval(() => {
        if (uploadProgress.value[fileName] < 90) {
          uploadProgress.value[fileName] += Math.random() * 15
        }
      }, 200)

      const result = await uploadDocument(file, selectedKbId.value, docType.value)
      clearInterval(progressTimer)
      uploadProgress.value[fileName] = 100
      successCount++
      totalChunks += result.chunk_count
    } catch (e: any) {
      uploadProgress.value[fileName] = -1
      message.error(`${fileName} 上传失败: ${e.message}`)
    }
  }

  if (successCount > 0) {
    message.success(`成功上传 ${successCount} 个文件，共 ${totalChunks} 个片段`)
    fileList.value = []
    loadDocs()
  }
  uploading.value = false
}

async function handleDelete(doc: DocumentItem) {
  try {
    await deleteDocument(doc.id)
    message.success('已删除')
    loadDocs()
  } catch (e: any) { message.error(e.message) }
}

function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const statusMap: Record<string, { color: string; text: string; icon: any }> = {
  done: { color: 'success', text: '已完成', icon: CheckCircleOutlined },
  processing: { color: 'processing', text: '处理中', icon: FileOutlined },
  error: { color: 'error', text: '失败', icon: DeleteOutlined },
}

watch(selectedKbId, loadDocs)
onMounted(loadKBs)

const docColumns = [
  { title: '文件名', dataIndex: 'filename', key: 'filename', ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 110 },
  { title: '块数', dataIndex: 'chunk_count', key: 'chunk_count', width: 80 },
  { title: '大小', dataIndex: 'file_size', key: 'file_size', width: 100, customRender: ({ text }: { text: number }) => formatSize(text) },
  { title: '操作', key: 'action', width: 80, align: 'center' },
]
</script>

<template>
  <div>
    <PageHeader
      :icon="CloudUploadOutlined"
      title="文档上传"
      description="支持 PDF、Word、Markdown、TXT 格式，批量上传并自动解析"
    />

    <a-row :gutter="16">
      <a-col :span="14">
        <a-card class="upload-card" title="上传文档">
          <a-form layout="vertical">
            <a-form-item label="选择知识库" required>
              <a-select v-model:value="selectedKbId" placeholder="请选择知识库" style="width: 100%">
                <a-select-option v-for="kb in kbList" :key="kb.id" :value="kb.id">{{ kb.name }}</a-select-option>
              </a-select>
            </a-form-item>
            <a-form-item label="文档类型">
              <a-select v-model:value="docType" style="width: 220px">
                <a-select-option
                  v-for="opt in docTypeOptions"
                  :key="opt.key"
                  :value="opt.key"
                  :title="opt.description"
                >{{ opt.label }}</a-select-option>
              </a-select>
              <div class="doc-type-hint text-secondary">
                {{ docTypeOptions.find(o => o.key === docType)?.description }}
              </div>
            </a-form-item>
            <a-form-item label="选择文件">
              <a-upload-dragger
                v-model:file-list="fileList"
                :multiple="true"
                :before-upload="() => false"
                accept=".pdf,.txt,.docx,.doc,.md"
              >
                <p class="ant-upload-drag-icon"><InboxOutlined /></p>
                <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
                <p class="ant-upload-hint">支持 PDF、Word (.docx)、Markdown (.md)、TXT，可批量上传</p>
              </a-upload-dragger>
            </a-form-item>

            <!-- Upload Progress -->
            <div v-if="uploading && Object.keys(uploadProgress).length > 0" class="upload-progress">
              <div class="progress-header">
                <span>上传进度</span>
                <span>{{ totalProgress }}%</span>
              </div>
              <a-progress :percent="totalProgress" status="active" />
              <div class="progress-files">
                <div
                  v-for="(prog, name) in uploadProgress"
                  :key="name"
                  class="progress-file"
                  :class="{ error: prog === -1, done: prog === 100 }"
                >
                  <FileOutlined />
                  <span class="file-name truncate">{{ name }}</span>
                  <a-progress
                    :percent="prog === -1 ? 0 : Math.round(prog)"
                    size="small"
                    :status="prog === -1 ? 'exception' : prog === 100 ? 'success' : 'active'"
                    style="width: 120px"
                  />
                </div>
              </div>
            </div>

            <a-button
              type="primary"
              :loading="uploading"
              @click="handleUpload"
              :disabled="!selectedKbId || fileList.length === 0"
              block
            >
              <CloudUploadOutlined /> 上传并处理 ({{ fileList.length }} 个文件)
            </a-button>
          </a-form>
        </a-card>
      </a-col>

      <a-col :span="10">
        <a-card title="说明" size="small" class="info-card" style="margin-bottom: 16px">
          <ul class="info-list">
            <li>上传后系统自动解析文档内容</li>
            <li>文本自动分块并生成向量</li>
            <li>向量存入 Milvus，支持语义检索</li>
            <li>支持批量上传多个文件</li>
            <li>文件大小限制：单个 50MB</li>
          </ul>
        </a-card>

        <a-card title="已上传文档" size="small" class="doc-list-card">
          <template #extra>
            <a-button size="small" @click="loadDocs"><ReloadOutlined /></a-button>
          </template>

          <LoadingSkeleton v-if="docLoading && docList.length === 0" />

          <a-table
            v-else
            :columns="docColumns"
            :data-source="docList"
            :loading="docLoading"
            :pagination="false"
            row-key="id"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'">
                <a-tag :color="statusMap[record.status]?.color">
                  <component :is="statusMap[record.status]?.icon" style="margin-right: 4px" />
                  {{ statusMap[record.status]?.text || record.status }}
                </a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <a-popconfirm title="确定删除此文档？" @confirm="handleDelete(record)">
                  <a-button size="small" danger><DeleteOutlined /></a-button>
                </a-popconfirm>
              </template>
            </template>

            <template #emptyText>
              <EmptyState
                type="upload"
                title="暂无文档"
                description="上传文档后，系统将自动解析并建立索引"
              />
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<style scoped>
.upload-card,
.info-card,
.doc-list-card {
  border-radius: var(--border-radius-lg);
  animation: fade-in var(--duration-normal) var(--ease-premium);
}
.upload-card {
  animation-delay: 0s;
}
.info-card {
  animation-delay: 0.06s;
}
.doc-list-card {
  animation-delay: 0.12s;
}
.upload-card :deep(.ant-upload-drag) {
  border-radius: var(--border-radius-lg);
  transition: all var(--duration-normal) var(--ease-premium);
  background: var(--bg-hover);
}
.upload-card :deep(.ant-upload-drag:hover) {
  border-color: var(--color-primary);
  background: var(--bg-active);
}
.upload-card :deep(.ant-upload-drag-icon) {
  color: var(--color-primary);
}
.upload-progress {
  margin-bottom: var(--space-md);
  padding: var(--space-md);
  background: var(--bg-hover);
  border-radius: var(--border-radius-md);
  border: 1px solid var(--border-color);
}
.progress-header {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
}
.progress-files {
  margin-top: var(--space-sm);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}
.progress-file {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.progress-file .file-name {
  flex: 1;
}
.progress-file.done {
  color: var(--color-success);
}
.progress-file.error {
  color: var(--color-error);
}
.info-list {
  padding-left: 20px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: var(--line-height-loose);
  margin: 0;
}
.info-list li {
  margin: var(--space-xs) 0;
}
.doc-type-hint {
  font-size: var(--font-size-xs);
  margin-top: var(--space-xs);
  min-height: 1.2em;
  line-height: var(--line-height-tight);
}

/* 响应式 */
@media (max-width: 992px) {
  .info-card,
  .doc-list-card {
    margin-top: var(--space-md);
  }
}
</style>
