<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { ref, watch, h } from 'vue'
import {
  BookOutlined,
  FolderOutlined,
  CloudUploadOutlined,
  MessageOutlined,
  EditOutlined,
  HomeOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const current = ref(['home'])

watch(
  () => route.path,
  (path) => {
    const key = path.replace('/', '') || 'home'
    current.value = [key]
  },
  { immediate: true }
)

const menuItems = [
  { key: 'home', icon: () => h(HomeOutlined), label: '首页', path: '/' },
  { key: 'knowledge', icon: () => h(FolderOutlined), label: '知识库', path: '/knowledge' },
  { key: 'upload', icon: () => h(CloudUploadOutlined), label: '上传', path: '/upload' },
  { key: 'qa', icon: () => h(MessageOutlined), label: '问答', path: '/qa' },
  { key: 'exam', icon: () => h(EditOutlined), label: '题库', path: '/exam' },
]

function onMenuClick({ key }: { key: string }) {
  const item = menuItems.find((m) => m.key === key)
  if (item) router.push(item.path)
}
</script>

<template>
  <a-layout style="min-height: 100vh">
    <a-layout-header style="display: flex; align-items: center; padding: 0 24px">
      <div style="color: #fff; font-size: 18px; font-weight: bold; margin-right: 40px; white-space: nowrap">
        <BookOutlined /> edu_rag 智能题库
      </div>
      <a-menu
        v-model:selectedKeys="current"
        mode="horizontal"
        theme="dark"
        :items="menuItems"
        style="flex: 1; min-width: 0"
        @click="onMenuClick"
      />
    </a-layout-header>
    <a-layout-content style="padding: 24px; max-width: 1200px; margin: 0 auto; width: 100%">
      <router-view />
    </a-layout-content>
    <a-layout-footer style="text-align: center">
      edu_rag — 基于 RAG 的智能教育题库系统
    </a-layout-footer>
  </a-layout>
</template>
