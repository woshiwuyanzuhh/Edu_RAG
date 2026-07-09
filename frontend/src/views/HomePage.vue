<script setup lang="ts">
import { useRouter } from 'vue-router'
import {
  FolderOutlined,
  CloudUploadOutlined,
  MessageOutlined,
  EditOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()

const features = [
  { icon: FolderOutlined, color: '#1677ff', title: '知识库管理', desc: '创建和管理多个知识库，按课程或主题分类', link: '/knowledge', btn: '进入管理' },
  { icon: CloudUploadOutlined, color: '#52c41a', title: '文档上传', desc: '支持 PDF、Word、Markdown、TXT 格式', link: '/upload', btn: '上传文档' },
  { icon: MessageOutlined, color: '#13c2c2', title: '智能问答', desc: '基于知识库内容的精准问答', link: '/qa', btn: '开始提问' },
  { icon: EditOutlined, color: '#faad14', title: '智能题库', desc: 'AI 自动出题、在线作答、智能批改', link: '/exam', btn: '生成题目' },
]
</script>

<template>
  <div>
    <div style="text-align: center; padding: 48px 0">
      <h1 style="font-size: 36px; font-weight: bold; margin-bottom: 12px">
        <span style="color: #1677ff">edu_rag</span>
      </h1>
      <p style="font-size: 16px; color: #999; margin-bottom: 0">
        基于 RAG 的智能教育题库系统 — 上传文档、智能出题、自动批改
      </p>
    </div>

    <a-row :gutter="16">
      <a-col :xs="24" :sm="12" :md="6" v-for="f in features" :key="f.title">
        <a-card hoverable style="text-align: center; height: 100%" @click="router.push(f.link)">
          <component :is="f.icon" :style="{ fontSize: '48px', color: f.color }" />
          <h3 style="margin-top: 16px">{{ f.title }}</h3>
          <p style="color: #999">{{ f.desc }}</p>
          <a-button type="primary" ghost>{{ f.btn }}</a-button>
        </a-card>
      </a-col>
    </a-row>

    <a-row style="margin-top: 48px">
      <a-col :xs="24" :md="12" :offset="6">
        <a-card title="💡 快速开始">
          <ol style="padding-left: 20px; line-height: 2">
            <li>创建知识库：点击「知识库管理」创建课程知识库</li>
            <li>上传文档：上传教材、讲义等文档，系统自动解析和向量化</li>
            <li>智能问答：基于文档内容提问，获取精准回答</li>
            <li>生成题目：选择题、简答题、判断题，AI 自动出题</li>
          </ol>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>
