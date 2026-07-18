<script setup lang="ts">
import {
  RobotOutlined,
  FileSearchOutlined,
  InboxOutlined,
  ThunderboltOutlined,
  CloudUploadOutlined,
  FolderOutlined,
} from '@ant-design/icons-vue'

defineProps<{
  type?: 'robot' | 'search' | 'inbox' | 'bolt' | 'upload' | 'folder'
  title: string
  description?: string
  actionText?: string
}>()

const emit = defineEmits<{
  action: []
}>()

const iconMap: Record<string, any> = {
  robot: RobotOutlined,
  search: FileSearchOutlined,
  inbox: InboxOutlined,
  bolt: ThunderboltOutlined,
  upload: CloudUploadOutlined,
  folder: FolderOutlined,
}
</script>

<template>
  <div class="empty-state">
    <div class="empty-state-icon-wrapper">
      <component :is="iconMap[type || 'robot']" class="empty-state-icon" />
    </div>
    <h3 class="empty-state-title">{{ title }}</h3>
    <p v-if="description" class="empty-state-desc">{{ description }}</p>
    <a-button v-if="actionText" type="primary" ghost @click="emit('action')">
      {{ actionText }}
    </a-button>
  </div>
</template>

<style scoped>
.empty-state {
  text-align: center;
  padding: var(--space-2xl) var(--space-lg);
  color: var(--text-tertiary);
  animation: fade-in var(--duration-normal) var(--ease-premium);
}
.empty-state-icon-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: var(--border-radius-full);
  background: var(--bg-active);
  margin-bottom: var(--space-md);
  transition: transform var(--duration-normal) var(--ease-spring);
}
.empty-state:hover .empty-state-icon-wrapper {
  transform: scale(1.08);
}
.empty-state-icon {
  font-size: 40px;
  color: var(--color-primary);
}
.empty-state-title {
  margin: 0 0 var(--space-sm);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
}
.empty-state-desc {
  margin: 0 0 var(--space-md);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  max-width: 360px;
  margin-left: auto;
  margin-right: auto;
}
</style>
