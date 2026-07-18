<script setup lang="ts">
defineProps<{
  rows?: number
}>()
</script>

<template>
  <div class="skeleton-wrapper">
    <div
      v-for="i in (rows || 3)"
      :key="i"
      class="skeleton-row"
      :style="{ width: `${60 + Math.random() * 40}%`, animationDelay: `${i * 0.1}s` }"
    />
  </div>
</template>

<style scoped>
.skeleton-wrapper {
  padding: var(--space-md);
}
.skeleton-row {
  height: 16px;
  background: linear-gradient(90deg, var(--bg-hover) 25%, var(--bg-active) 50%, var(--bg-hover) 75%);
  background-size: 200% 100%;
  border-radius: var(--border-radius-sm);
  margin-bottom: var(--space-sm);
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
