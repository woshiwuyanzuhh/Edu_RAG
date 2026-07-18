<script setup lang="ts">
import { h } from 'vue'

defineProps<{
  icon?: any
  title: string
  description?: string
}>()
</script>

<template>
  <div class="page-header">
    <div class="page-header-content">
      <component v-if="icon" :is="icon" class="page-header-icon" />
      <div>
        <h2 class="page-header-title">{{ title }}</h2>
        <p v-if="description" class="page-header-desc">{{ description }}</p>
      </div>
    </div>
    <div class="page-header-extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-lg);
  gap: var(--space-md);
  animation: slide-in-left var(--duration-normal) var(--ease-premium);
}
.page-header-content {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.page-header-icon {
  font-size: 24px;
  color: var(--color-primary);
  padding: var(--space-sm);
  background: var(--bg-active);
  border-radius: var(--border-radius-md);
}
.page-header-title {
  margin: 0;
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  line-height: var(--line-height-snug);
}
.page-header-desc {
  margin: 2px 0 0;
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  line-height: var(--line-height-base);
}
.page-header-extra {
  flex-shrink: 0;
}
</style>
