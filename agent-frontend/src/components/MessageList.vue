<script setup lang="ts">
import { nextTick, onUpdated, ref } from 'vue'
import type { ChatMessage } from '../types/chat'

defineProps<{
  messages: ChatMessage[]
  loading?: boolean
}>()

const containerRef = ref<HTMLDivElement | null>(null)

function roleLabel(role: ChatMessage['role']) {
  if (role === 'user') return '你'
  if (role === 'system') return '系统'
  return 'Agent'
}

function roleInitial(role: ChatMessage['role']) {
  if (role === 'user') return 'U'
  if (role === 'system') return 'S'
  return 'A'
}

onUpdated(async () => {
  await nextTick()
  if (containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight
  }
})
</script>

<template>
  <section ref="containerRef" class="messages" aria-label="消息列表">
    <div v-if="messages.length === 0 && !loading" class="empty-state">
      <h2>开始一次新的协作</h2>
      <p>把你的目标发给 Agent，消息会在这里汇总。</p>
    </div>

    <div
      v-for="(msg, index) in messages"
      :key="index"
      class="message"
      :class="msg.role"
    >
      <div class="avatar" aria-hidden="true">
        {{ roleInitial(msg.role) }}
      </div>

      <div class="bubble">
        <div class="role">
          {{ roleLabel(msg.role) }}
        </div>
        <div class="content">
          {{ msg.content }}
        </div>
      </div>
    </div>

    <div v-if="loading" class="message assistant">
      <div class="avatar" aria-hidden="true">A</div>
      <div class="bubble thinking">
        <div class="role">Agent</div>
        <div class="content loading-copy">
          正在思考<span></span><span></span><span></span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 28px 24px;
  scroll-behavior: smooth;
}

.messages::-webkit-scrollbar {
  width: 10px;
}

.messages::-webkit-scrollbar-track {
  background: transparent;
}

.messages::-webkit-scrollbar-thumb {
  border: 3px solid transparent;
  border-radius: 999px;
  background: rgba(98, 112, 107, 0.36);
  background-clip: content-box;
}

.empty-state {
  max-width: 520px;
  margin: 12vh auto 0;
  padding: 30px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.78);
  text-align: center;
  box-shadow: var(--shadow-sm);
}

.empty-state h2 {
  margin: 0 0 8px;
  color: var(--text-primary);
  font-size: 22px;
  letter-spacing: 0;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
}

.message {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 980px;
  margin: 0 auto 18px;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  flex: 0 0 34px;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(47, 111, 99, 0.16);
  border-radius: 50%;
  color: var(--accent);
  background: var(--accent-soft);
  font-size: 13px;
  font-weight: 900;
}

.message.user .avatar {
  color: #ffffff;
  background: var(--ink);
  border-color: var(--ink);
}

.message.system .avatar {
  color: #ffffff;
  background: var(--gold);
  border-color: var(--gold);
}

.bubble {
  max-width: min(760px, calc(100% - 48px));
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow-sm);
}

.message.user .bubble {
  border-color: transparent;
  color: #ffffff;
  background: var(--accent);
}

.message.system .bubble {
  background: #fff8e8;
  border-color: rgba(216, 155, 61, 0.28);
}

.role {
  margin-bottom: 7px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 900;
}

.message.user .role {
  color: rgba(255, 255, 255, 0.72);
}

.content {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.72;
  font-size: 15px;
  text-align: left;
}

.thinking {
  min-width: 180px;
}

.loading-copy {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.loading-copy span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1s ease-in-out infinite;
}

.loading-copy span:nth-child(2) {
  animation-delay: 0.12s;
}

.loading-copy span:nth-child(3) {
  animation-delay: 0.24s;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }

  50% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

@media (max-width: 680px) {
  .messages {
    padding: 20px 16px;
  }

  .message {
    margin-bottom: 14px;
  }

  .avatar {
    flex-basis: 30px;
    width: 30px;
    height: 30px;
    font-size: 12px;
  }

  .bubble {
    max-width: calc(100% - 40px);
    padding: 12px 13px;
  }
}
</style>
