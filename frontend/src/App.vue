<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { ref, watch, h, onMounted, onBeforeUnmount } from 'vue'
import {
  BookOutlined,
  FolderOutlined,
  CloudUploadOutlined,
  MessageOutlined,
  EditOutlined,
  HomeOutlined,
  BulbOutlined,
  MenuOutlined,
  CloseOutlined,
} from '@ant-design/icons-vue'
import { useGlobalStore } from './stores/global'

const router = useRouter()
const route = useRoute()
const globalStore = useGlobalStore()
const current = ref(['home'])
const mobileMenuOpen = ref(false)

watch(
  () => route.path,
  (path) => {
    const key = path.replace('/', '') || 'home'
    current.value = [key]
    // 路由切换时关闭移动端菜单
    mobileMenuOpen.value = false
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

// 监听窗口尺寸，桌面端自动关闭抽屉
function handleResize() {
  if (window.innerWidth > 992) mobileMenuOpen.value = false
}

onMounted(() => {
  globalStore.initTheme()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => window.removeEventListener('resize', handleResize))
</script>

<template>
  <a-layout class="app-layout">
    <a-layout-header class="app-header">
      <div class="header-inner">
        <div class="app-brand" @click="router.push('/')">
          <BookOutlined class="brand-icon" />
          <span class="brand-text">edu_rag</span>
          <span class="brand-sub">智能题库</span>
        </div>

        <!-- 桌面端横向菜单 -->
        <a-menu
          v-model:selectedKeys="current"
          mode="horizontal"
          theme="dark"
          :items="menuItems"
          class="app-menu hidden-mobile"
          @click="onMenuClick"
        />

        <div class="header-actions">
          <a-tooltip :title="globalStore.isDark ? '切换到亮色模式' : '切换到暗色模式'">
            <a-button type="text" class="theme-toggle" @click="globalStore.toggleTheme">
              <template #icon>
                <BulbOutlined />
              </template>
            </a-button>
          </a-tooltip>

          <!-- 移动端汉堡按钮 -->
          <a-button type="text" class="menu-trigger hidden-desktop" @click="mobileMenuOpen = true">
            <MenuOutlined />
          </a-button>
        </div>
      </div>
    </a-layout-header>

    <a-layout-content class="app-content">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </a-layout-content>

    <a-layout-footer class="app-footer">
      edu_rag — 基于 RAG 的智能教育题库系统
    </a-layout-footer>

    <!-- 移动端抽屉菜单 -->
    <a-drawer
      v-model:open="mobileMenuOpen"
      placement="right"
      :width="260"
      :closable="false"
      class="mobile-drawer"
    >
      <template #title>
        <div class="drawer-title">
          <span>导航菜单</span>
          <a-button type="text" size="small" @click="mobileMenuOpen = false">
            <CloseOutlined />
          </a-button>
        </div>
      </template>
      <a-menu
        v-model:selectedKeys="current"
        mode="vertical"
        :items="menuItems"
        class="mobile-menu"
        @click="onMenuClick"
      />
    </a-drawer>
  </a-layout>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  background: var(--bg-body);
}

.app-header {
  display: flex;
  align-items: center;
  padding: 0;
  position: sticky;
  top: 0;
  z-index: var(--z-header);
  background: var(--bg-elevated);
  box-shadow: var(--shadow-sm);
  border-bottom: 1px solid var(--border-color);
  height: var(--header-height);
  line-height: var(--header-height);
}

.header-inner {
  display: flex;
  align-items: center;
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 0 var(--space-lg);
  gap: var(--space-lg);
}

.app-brand {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  cursor: pointer;
  white-space: nowrap;
  transition: opacity var(--duration-fast) ease;
}
.app-brand:hover {
  opacity: 0.85;
}
.brand-icon {
  font-size: 22px;
  color: var(--color-primary);
}
.brand-text {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.brand-sub {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  font-weight: var(--font-weight-normal);
}

.app-menu {
  flex: 1;
  min-width: 0;
  background: transparent !important;
  border-bottom: none !important;
  line-height: var(--header-height);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  flex-shrink: 0;
}
.theme-toggle {
  color: var(--text-secondary);
  width: 40px;
  height: 40px;
  border-radius: var(--border-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-normal) var(--ease-premium);
}
.theme-toggle:hover {
  color: var(--color-primary);
  background: var(--bg-active);
  transform: rotate(15deg);
}
.menu-trigger {
  color: var(--text-primary);
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.app-content {
  padding: var(--space-lg);
  max-width: var(--content-max-width);
  margin: 0 auto;
  width: 100%;
  min-height: calc(100vh - var(--header-height) - var(--footer-height));
}

.app-footer {
  text-align: center;
  background: var(--bg-body);
  color: var(--text-tertiary);
  padding: var(--space-lg);
  font-size: var(--font-size-sm);
}

/* Dark mode header */
html[data-theme='dark'] .app-header {
  background: var(--bg-card);
}

/* 抽屉标题 */
.drawer-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: var(--font-weight-semibold);
}
.mobile-menu {
  border-right: none;
}
</style>
