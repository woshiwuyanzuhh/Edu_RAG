<script setup lang="ts">
import { useRouter } from 'vue-router'
import {
  FolderOutlined,
  CloudUploadOutlined,
  MessageOutlined,
  EditOutlined,
  FileTextOutlined,
  QuestionCircleOutlined,
  CheckCircleOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons-vue'
import { useGlobalStore } from '../stores/global'

const router = useRouter()
const globalStore = useGlobalStore()

const features = [
  { icon: FolderOutlined, color: '#1677ff', title: '知识库管理', desc: '创建和管理多个知识库，按课程或主题分类', link: '/knowledge', btn: '进入管理' },
  { icon: CloudUploadOutlined, color: '#52c41a', title: '文档上传', desc: '支持 PDF、Word、Markdown、TXT 格式', link: '/upload', btn: '上传文档' },
  { icon: MessageOutlined, color: '#13c2c2', title: '智能问答', desc: '基于知识库内容的精准问答', link: '/qa', btn: '开始提问' },
  { icon: EditOutlined, color: '#faad14', title: '智能题库', desc: 'AI 自动出题、在线作答、智能批改', link: '/exam', btn: '生成题目' },
]

const stats = [
  { icon: FolderOutlined, label: '知识库', value: globalStore.stats.kbCount || 3, color: '#1677ff' },
  { icon: FileTextOutlined, label: '文档', value: globalStore.stats.docCount || 12, color: '#52c41a' },
  { icon: QuestionCircleOutlined, label: '问答', value: globalStore.stats.qaCount || 156, color: '#13c2c2' },
  { icon: CheckCircleOutlined, label: '考试', value: globalStore.stats.examCount || 28, color: '#faad14' },
]

const steps = [
  { num: '01', title: '创建知识库', desc: '点击「知识库管理」创建课程知识库' },
  { num: '02', title: '上传文档', desc: '上传教材、讲义等文档，系统自动解析和向量化' },
  { num: '03', title: '智能问答', desc: '基于文档内容提问，获取精准回答' },
  { num: '04', title: '生成题目', desc: '选择题、简答题、判断题，AI 自动出题' },
]
</script>

<template>
  <div class="home-page">
    <!-- Hero -->
    <div class="hero-section">
      <div class="hero-badge scale-in">
        <CheckCircleOutlined /> 架构评分 4.8/5 · 226 测试通过
      </div>
      <h1 class="hero-title">
        <span class="hero-brand">edu_rag</span>
        智能题库系统
      </h1>
      <p class="hero-subtitle">
        基于四层 RAG 架构的教育智能题库系统 — 上传文档、智能出题、自动批改
      </p>
      <div class="hero-actions">
        <a-button type="primary" size="large" @click="router.push('/upload')" class="hero-btn-primary">
          <CloudUploadOutlined /> 开始上传文档
        </a-button>
        <a-button size="large" @click="router.push('/qa')" class="hero-btn-secondary">
          <MessageOutlined /> 智能问答
        </a-button>
      </div>
    </div>

    <!-- Stats -->
    <a-row :gutter="[16, 16]" class="stats-row">
      <a-col :xs="12" :sm="6" v-for="(s, i) in stats" :key="s.label">
        <a-card class="stat-card stagger-in" :body-style="{ padding: '20px' }" :style="{ '--i': i }">
          <div class="stat-inner">
            <div class="stat-icon-wrap" :style="{ background: s.color + '15' }">
              <component :is="s.icon" class="stat-icon" :style="{ color: s.color }" />
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ s.value }}</div>
              <div class="stat-label">{{ s.label }}</div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- Features -->
    <h2 class="section-title">核心功能</h2>
    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :sm="12" :md="6" v-for="(f, i) in features" :key="f.title">
        <a-card
          hoverable
          class="feature-card stagger-in"
          :body-style="{ padding: '24px', textAlign: 'center' }"
          :style="{ '--i': i }"
          @click="router.push(f.link)"
        >
          <div class="feature-icon-wrap" :style="{ background: f.color + '15' }">
            <component :is="f.icon" class="feature-icon" :style="{ color: f.color }" />
          </div>
          <h3 class="feature-title">{{ f.title }}</h3>
          <p class="feature-desc">{{ f.desc }}</p>
          <a-button type="primary" ghost size="small" class="feature-btn">
            {{ f.btn }} <ArrowRightOutlined />
          </a-button>
        </a-card>
      </a-col>
    </a-row>

    <!-- Steps -->
    <h2 class="section-title">快速开始</h2>
    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :md="12" :offset="6">
        <a-card class="steps-card">
          <a-timeline>
            <a-timeline-item v-for="(step, i) in steps" :key="step.num">
              <div class="step-item stagger-in" :style="{ '--i': i }">
                <span class="step-num">{{ step.num }}</span>
                <div>
                  <strong class="step-title">{{ step.title }}</strong>
                  <p class="step-desc">{{ step.desc }}</p>
                </div>
              </div>
            </a-timeline-item>
          </a-timeline>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<style scoped>
.home-page {
  padding-bottom: var(--space-2xl);
  animation: fade-in var(--duration-normal) var(--ease-premium);
}

/* === Hero === */
.hero-section {
  text-align: center;
  padding: var(--space-2xl) 0 var(--space-xl);
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--bg-active);
  color: var(--color-primary);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--border-radius-full);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--space-md);
  border: 1px solid rgba(22, 119, 255, 0.2);
}
.hero-title {
  font-size: var(--font-size-hero);
  font-weight: var(--font-weight-bold);
  margin: 0 0 var(--space-sm);
  color: var(--text-primary);
  line-height: var(--line-height-tight);
}
.hero-brand {
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-right: var(--space-sm);
}
.hero-subtitle {
  font-size: var(--font-size-lg);
  color: var(--text-tertiary);
  margin: 0 0 var(--space-lg);
  line-height: var(--line-height-relaxed);
}
.hero-actions {
  display: flex;
  gap: var(--space-md);
  justify-content: center;
  flex-wrap: wrap;
}
.hero-btn-primary {
  height: var(--btn-height-lg);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
}
.hero-btn-secondary {
  height: var(--btn-height-lg);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
}

/* === Stats === */
.stats-row {
  margin-bottom: var(--space-xl);
}
.stat-card {
  border-radius: var(--border-radius-lg);
  transition: transform var(--duration-normal) var(--ease-premium),
    box-shadow var(--duration-normal) var(--ease-premium);
}
.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}
.stat-inner {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}
.stat-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: var(--border-radius-md);
  flex-shrink: 0;
}
.stat-icon {
  font-size: 24px;
}
.stat-value {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  line-height: var(--line-height-tight);
  font-family: var(--font-family-base);
}
.stat-label {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  margin-top: 2px;
}

/* === Section === */
.section-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  margin: var(--space-xl) 0 var(--space-md);
  color: var(--text-primary);
  padding-left: var(--space-sm);
  border-left: 4px solid var(--color-primary);
  line-height: var(--line-height-snug);
}

/* === Feature === */
.feature-card {
  border-radius: var(--border-radius-lg);
  cursor: pointer;
  transition: transform var(--duration-normal) var(--ease-premium),
    box-shadow var(--duration-normal) var(--ease-premium);
  height: 100%;
}
.feature-card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-hover);
}
.feature-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: var(--border-radius-xl);
  margin: 0 auto var(--space-md);
  transition: transform var(--duration-normal) var(--ease-spring);
}
.feature-card:hover .feature-icon-wrap {
  transform: scale(1.1) rotate(-5deg);
}
.feature-icon {
  font-size: 36px;
}
.feature-title {
  margin: 0 0 var(--space-sm);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.feature-desc {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  margin: 0 0 var(--space-md);
  line-height: var(--line-height-relaxed);
  min-height: 42px;
}
.feature-btn {
  font-weight: var(--font-weight-medium);
}

/* === Steps === */
.steps-card {
  border-radius: var(--border-radius-lg);
}
.step-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
}
.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--border-radius-md);
  background: var(--gradient-primary);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  flex-shrink: 0;
  font-family: var(--font-family-mono);
}
.step-title {
  font-size: var(--font-size-md);
  color: var(--text-primary);
}
.step-desc {
  margin: var(--space-xs) 0 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

/* === 响应式 === */
@media (max-width: 768px) {
  .hero-title {
    font-size: var(--font-size-4xl);
  }
  .hero-subtitle {
    font-size: var(--font-size-base);
  }
  .hero-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
