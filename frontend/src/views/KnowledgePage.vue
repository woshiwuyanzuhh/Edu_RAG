<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { FolderOutlined, PlusOutlined, UploadOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { listKnowledgeBases, createKnowledgeBase, deleteKnowledgeBase } from '../api/knowledge'
import type { KnowledgeBase } from '../api/types'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'

const router = useRouter()
const kbs = ref<KnowledgeBase[]>([])
const loading = ref(false)
const createVisible = ref(false)
const newName = ref('')
const newDesc = ref('')
const pagination = ref({ current: 1, pageSize: 20, total: 0 })

const formRules = {
  name: [{ required: true, message: '请输入知识库名称', trigger: 'blur' }],
}

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
  if (!newName.value.trim()) {
    return message.warning('请输入知识库名称')
  }
  if (newName.value.trim().length > 50) {
    return message.warning('名称不能超过 50 个字符')
  }
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
    <PageHeader
      :icon="FolderOutlined"
      title="知识库管理"
      description="创建和管理多个知识库，按课程或主题分类"
    >
      <template #extra>
        <a-button type="primary" @click="createVisible = true">
          <PlusOutlined /> 创建知识库
        </a-button>
      </template>
    </PageHeader>

    <a-card class="content-card">
      <a-table
        :columns="columns"
        :data-source="kbs"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-space>
              <a-button size="small" @click="router.push(`/upload?kb=${record.id}`)">
                <UploadOutlined /> 上传文档
              </a-button>
              <a-popconfirm
                title="确定删除此知识库？"
                description="所有文档和向量数据将被清除，此操作不可恢复。"
                ok-text="删除"
                cancel-text="取消"
                ok-type="danger"
                @confirm="handleDelete(record)"
              >
                <a-button size="small" danger><DeleteOutlined /></a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>

        <template #emptyText>
          <EmptyState
            type="folder"
            title="暂无知识库"
            description="创建你的第一个知识库，开始上传文档"
            action-text="创建知识库"
            @action="createVisible = true"
          />
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="createVisible"
      title="创建知识库"
      @ok="handleCreate"
      :ok-button-props="{ disabled: !newName.trim() }"
    >
      <a-form layout="vertical" :rules="formRules">
        <a-form-item label="名称" required name="name">
          <a-input
            v-model:value="newName"
            placeholder="例如：机器学习期中考试"
            maxlength="50"
            show-count
            @keydown.enter="handleCreate"
          />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea
            v-model:value="newDesc"
            :rows="3"
            placeholder="简要描述知识库内容..."
            maxlength="200"
            show-count
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped>
.content-card {
  border-radius: var(--border-radius-lg);
  animation: fade-in var(--duration-normal) var(--ease-premium);
}
.content-card :deep(.ant-table) {
  border-radius: var(--border-radius-md);
}
.content-card :deep(.ant-table-thead > tr > th) {
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-sm);
}
.content-card :deep(.ant-table-tbody > tr) {
  transition: background var(--duration-fast) ease;
}
.content-card :deep(.ant-table-tbody > tr:hover > td) {
  background: var(--bg-hover);
}
</style>
