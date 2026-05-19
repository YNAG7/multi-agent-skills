<script setup lang="ts">
import type { ChatSession } from '../types/chat'

defineProps<{
  sessions: ChatSession[]
  activeThreadId: string
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'new-session'): void
  (e: 'select-session', threadId: string): void
}>()

function formatTime(value?: string) {
  if (!value) return ''

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 19).replace('T', ' ')
  }

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <div>
        <p>History</p>
        <h2>会话</h2>
      </div>
      <button type="button" title="新建会话" @click="emit('new-session')">
        + 新建
      </button>
    </div>

    <div v-if="loading" class="empty">正在加载会话...</div>

    <div v-else-if="sessions.length === 0" class="empty">
      暂无历史会话
    </div>

    <div v-else class="session-list">
      <button
        v-for="item in sessions"
        :key="item.thread_id"
        type="button"
        class="session-item"
        :class="{ active: item.thread_id === activeThreadId }"
        @click="emit('select-session', item.thread_id)"
      >
        <span class="title">
          {{ item.title || '新的会话' }}
        </span>
        <span class="time">
          {{ formatTime(item.updated_at) }}
        </span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 304px;
  height: 100svh;
  flex: 0 0 304px;
  display: flex;
  flex-direction: column;
  color: rgba(244, 250, 248, 0.92);
  background:
    linear-gradient(180deg, rgba(47, 111, 99, 0.28), transparent 38%),
    var(--sidebar);
}

.sidebar-header {
  min-height: 86px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.sidebar-header p {
  margin: 0 0 4px;
  color: #90c9bd;
  font-size: 12px;
  font-weight: 800;
}

.sidebar-header h2 {
  margin: 0;
  color: #ffffff;
  font-size: 22px;
  line-height: 1.1;
  letter-spacing: 0;
}

.sidebar-header button {
  flex: 0 0 auto;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: #ffffff;
  background: var(--accent);
  cursor: pointer;
  font-size: 14px;
  font-weight: 800;
}

.sidebar-header button:hover {
  background: #3b8274;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.session-list::-webkit-scrollbar {
  width: 10px;
}

.session-list::-webkit-scrollbar-track {
  background: transparent;
}

.session-list::-webkit-scrollbar-thumb {
  border: 3px solid transparent;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.26);
  background-clip: content-box;
}

.session-item {
  width: 100%;
  display: block;
  margin: 0 0 8px;
  padding: 13px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: rgba(244, 250, 248, 0.78);
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.session-item:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.08);
}

.session-item.active {
  border-color: rgba(255, 255, 255, 0.14);
  color: #ffffff;
  background: var(--sidebar-soft);
  box-shadow: inset 3px 0 0 var(--gold);
}

.title,
.time {
  display: block;
}

.title {
  overflow: hidden;
  color: inherit;
  font-size: 14px;
  font-weight: 750;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time {
  margin-top: 7px;
  color: rgba(244, 250, 248, 0.52);
  font-size: 12px;
}

.empty {
  margin: 12px;
  padding: 16px;
  border: 1px dashed rgba(255, 255, 255, 0.16);
  border-radius: 8px;
  color: rgba(244, 250, 248, 0.66);
  background: rgba(255, 255, 255, 0.04);
  font-size: 14px;
}

@media (max-width: 860px) {
  .sidebar {
    width: 100%;
    height: auto;
    max-height: 220px;
    flex-basis: auto;
  }

  .sidebar-header {
    min-height: 72px;
    padding: 14px 16px;
  }

  .session-list {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 10px 16px 14px;
  }

  .session-item {
    min-width: 220px;
    margin: 0;
  }
}
</style>
