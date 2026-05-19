<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'send', value: string): void
}>()

const text = ref('')

function submit() {
  const value = text.value.trim()

  if (!value) return

  emit('send', value)
  text.value = ''
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <footer class="input-wrap">
    <form class="chat-input" @submit.prevent="submit">
      <textarea
        v-model="text"
        aria-label="消息内容"
        placeholder="输入消息，告诉 Agent 你的目标"
        :disabled="loading"
        @keydown="handleKeydown"
      />

      <button
        type="submit"
        :disabled="loading || !text.trim()"
      >
        {{ loading ? '发送中' : '发送' }}
      </button>
    </form>
  </footer>
</template>

<style scoped>
.input-wrap {
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(14px);
}

.chat-input {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 96px;
  align-items: stretch;
  gap: 12px;
  max-width: 980px;
  margin: 0 auto;
}

textarea {
  width: 100%;
  min-height: 58px;
  max-height: 170px;
  resize: vertical;
  padding: 14px 15px;
  border: 1px solid var(--border);
  border-radius: 8px;
  outline: none;
  color: var(--text-primary);
  background: #ffffff;
  box-shadow: 0 8px 22px rgba(27, 45, 39, 0.07);
  font-size: 15px;
  line-height: 1.55;
}

textarea::placeholder {
  color: var(--text-muted);
}

textarea:focus {
  border-color: var(--accent);
  box-shadow:
    0 0 0 4px rgba(47, 111, 99, 0.1),
    0 8px 22px rgba(27, 45, 39, 0.08);
}

button {
  min-height: 58px;
  border: 0;
  border-radius: 8px;
  color: #ffffff;
  background: var(--accent);
  cursor: pointer;
  font-weight: 800;
  box-shadow: 0 12px 24px rgba(47, 111, 99, 0.22);
}

button:not(:disabled):hover {
  background: var(--accent-strong);
}

button:disabled {
  color: rgba(255, 255, 255, 0.72);
  background: var(--text-muted);
  box-shadow: none;
  cursor: not-allowed;
}

@media (max-width: 680px) {
  .input-wrap {
    padding: 12px 16px 16px;
  }

  .chat-input {
    grid-template-columns: 1fr;
  }

  button {
    min-height: 44px;
  }
}
</style>
