import { ref, onMounted } from 'vue'
import { listKnowledgeBases } from '../api/knowledge'
import type { KnowledgeBase } from '../api/types'
import { message } from 'ant-design-vue'

export function useKnowledgeBases() {
  const kbList = ref<KnowledgeBase[]>([])
  const loading = ref(false)

  async function load(page = 1, pageSize = 100) {
    loading.value = true
    try {
      const data = await listKnowledgeBases(page, pageSize)
      kbList.value = data.items
    } catch (e: any) {
      message.error(e.message || '加载知识库失败')
    } finally {
      loading.value = false
    }
  }

  onMounted(() => load())

  return {
    kbList,
    loading,
    load,
  }
}
