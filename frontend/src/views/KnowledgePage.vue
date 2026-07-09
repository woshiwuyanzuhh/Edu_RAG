<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { FolderOutlined, PlusOutlined, UploadOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { listKnowledgeBases, createKnowledgeBase, deleteKnowledgeBase } from '../api/knowledge'
import type { KnowledgeBase } from '../api/types'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const kbs = ref<KnowledgeBase[]>([])
const loading = ref(false)
const createVisible = ref(false)
const newName = ref('')
const newDesc = ref('')
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

async function load() {
  loading.value = true
  try {
    const data = await listKnowledgeBases(pagination.value.current, pagination.value.pageSize)
    kbs.value = data.items
    pagination.value.total = data.total
  } catch (e: any) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!newName.value.trim()) return message.warning('请输入知识库名称')
  try {
    await createKnowledgeBase({ name: newName.value.trim(), description: newDesc.value.trim() })
    message.success('创建成功')
    createVisible.value = false
    newName.value = ''
    newDesc.value = ''
    load()
  } catch (e: any) {
    message.error(e.message)
  }
}

async function handleDelete(kb: KnowledgeBase) {
  try {
    await deleteKnowledgeBase(kb.id)
    message.success('已删除')
    load()
  } catch (e: any) {
    message.error(e.message)
  }
}

function handleTableChange(p: { current: number; pageSize: number }) {
  pagination.value.current = p.current
  pagination.value.pageSize = p.pageSize
  load()
}

onMounted(load)

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 80 },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  {
    title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180,
    customRender: ({ text }: { text: string }) => text ? new Date(text).toLocaleDateString('zh-CN') : '-',
  },
  { title: '操作', key: 'action', width: 200 },
]
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px">
      <h2 style="margin: 0"><FolderOutlined /> 知识库管理</h2>
      <a-button type="primary" @click="createVisible = true"><PlusOutlined /> 创建知识库</a-button>
    </div>

    <a-table :columns="columns" :data-source="kbs" :loading="loading" :pagination="pagination" row-key="id" @change="handleTableChange">
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button size="small" @click="router.push(`/upload?kb=${record.id}`)"><UploadOutlined /> 上传文档</a-button>
            <a-popconfirm title="确定删除此知识库？所有文档和向量数据将被清除" @confirm="handleDelete(record)">
              <a-button size="small" danger><DeleteOutlined /></a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal v-model:open="createVisible" title="创建知识库" @ok="handleCreate">
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="newName" placeholder="例如：机器学习期中考试" @keydown.enter="handleCreate" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="newDesc" rows="3" placeholder="简要描述知识库内容..." />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
