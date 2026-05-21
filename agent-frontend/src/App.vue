<script setup lang="ts">
import { onMounted, ref } from 'vue'
import LoginPage from './pages/LoginPage.vue'
import ChatPage from './pages/ChatPage.vue'
import MonitorPage from './pages/MonitorPage.vue'
import { getMe, logout as doLogout } from './api/auth'
import { getToken } from './api/http'
import type { User } from './types/auth'

const loading = ref(true)
const user = ref<User | null>(null)
const activePage = ref<'chat' | 'monitor'>('chat')

async function loadUser() {
  if (!getToken()) {
    loading.value = false
    return
  }

  try {
    user.value = await getMe()
  } catch {
    user.value = null
  } finally {
    loading.value = false
  }
}

async function handleLoginSuccess() {
  loading.value = true
  await loadUser()
}

function handleLogout() {
  doLogout()
  user.value = null
  activePage.value = 'chat'
}

onMounted(loadUser)
</script>

<template>
  <div v-if="loading" class="loading-page">
    <span class="loading-mark" aria-hidden="true"></span>
    <span>正在连接工作台...</span>
  </div>

  <LoginPage
    v-else-if="!user"
    @login-success="handleLoginSuccess"
  />

  <ChatPage
    v-else-if="activePage === 'chat'"
    :user="user"
    @open-monitor="activePage = 'monitor'"
    @logout="handleLogout"
  />

  <MonitorPage
    v-else
    :user="user"
    @back="activePage = 'chat'"
    @logout="handleLogout"
  />
</template>

<style scoped>
.loading-page {
  height: 100vh;
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  background: var(--app-bg);
  font-size: 15px;
}

.loading-mark {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border-strong);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
