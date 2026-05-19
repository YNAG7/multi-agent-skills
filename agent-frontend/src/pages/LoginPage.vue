<script setup lang="ts">
import { ref } from 'vue'
import { ArrowRight, Sparkles, ShieldCheck, Loader2 } from 'lucide-vue-next'
import { login, register } from '../api/auth'

const emit = defineEmits<{
  (e: 'login-success'): void
}>()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const nickname = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''

  if (!username.value.trim()) {
    error.value = 'Username is required'
    return
  }

  if (!password.value.trim()) {
    error.value = 'Password is required'
    return
  }

  loading.value = true

  try {
    if (mode.value === 'login') {
      await login(username.value.trim(), password.value)
    } else {
      await register(
        username.value.trim(),
        password.value,
        nickname.value.trim() || undefined
      )
    }

    emit('login-success')
  } catch (e: any) {
    error.value = e.message || 'Authentication failed. Please try again.'
  } finally {
    loading.value = false
  }
}

function toggleMode() {
  error.value = ''
  mode.value = mode.value === 'login' ? 'register' : 'login'
  username.value = ''
  password.value = ''
  nickname.value = ''
}
</script>

<template>
  <main class="saas-login-container">
    <div class="presentation-side">
      <div class="tech-grid-bg dark-grid"></div>
      
      <div class="nexus-art">
        <div class="core-glow"></div>
        <div class="orbit orbit-1">
          <div class="agent-node node-a"></div>
        </div>
        <div class="orbit orbit-2">
          <div class="agent-node node-b"></div>
          <div class="agent-node node-c"></div>
        </div>
        <div class="orbit orbit-3">
          <div class="agent-node node-d"></div>
        </div>
      </div>
      
      <div class="presentation-content">
        <div class="brand-badge">
          <Sparkles :size="16" />
          <span>Agent OS v1.0</span>
        </div>
        
        <h1 class="hero-title">
            <span class="text-glow">Nexus</span>
        </h1>
        
        <p class="hero-subtitle">
          构建、调试并部署多智能体协作网络。<br/>
          一个上下文感知的工作台，让每一次对话转化为生产力。
        </p>
      </div>
    </div>

    <div class="auth-side">
      <div class="light-grid-bg"></div>

      <div class="auth-wrapper">
        <div class="auth-header">
          <h2>{{ mode === 'login' ? 'Sign in to platform' : 'Create an account' }}</h2>
          <p class="auth-subtext">
            {{ mode === 'login' ? 'Welcome back to your workspace.' : 'Start your multi-agent journey.' }}
          </p>
        </div>

        <form @submit.prevent="submit" class="auth-form">
          <div class="input-group">
            <label for="username">Username</label>
            <input
              id="username"
              v-model="username"
              type="text"
              placeholder="Enter your username"
              autocomplete="username"
              spellcheck="false"
            />
          </div>

          <Transition name="expand">
            <div v-if="mode === 'register'" class="input-group">
              <label for="nickname">Display Name <span class="optional">(Optional)</span></label>
              <input
                id="nickname"
                v-model="nickname"
                type="text"
                placeholder="How should we call you?"
                autocomplete="name"
                spellcheck="false"
              />
            </div>
          </Transition>

          <div class="input-group">
            <div class="label-row">
              <label for="password">Password</label>
              <a v-if="mode === 'login'" href="#" class="forgot-link">Forgot?</a>
            </div>
            <input
              id="password"
              v-model="password"
              type="password"
              placeholder="••••••••"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            />
          </div>

          <Transition name="fade">
            <div v-if="error" class="alert-box error">
              <ShieldCheck class="alert-icon" :size="16" />
              <span>{{ error }}</span>
            </div>
          </Transition>

          <button type="submit" class="primary-btn" :disabled="loading">
            <span v-if="!loading">{{ mode === 'login' ? 'Continue' : 'Create Account' }}</span>
            <span v-else class="loading-state">
              <Loader2 class="spinner" :size="18" /> Processing...
            </span>
            <ArrowRight v-if="!loading" class="btn-icon" :size="16" />
          </button>
        </form>

        <div class="auth-footer">
          <p>
            {{ mode === 'login' ? "Don't have an account?" : "Already have an account?" }}
            <button type="button" class="switch-mode-btn" @click="toggleMode">
              {{ mode === 'login' ? 'Sign up' : 'Sign in' }}
            </button>
          </p>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap');

:root {
  /* 专门针对右侧浅色模式的色彩系统 */
  --bg-light: #f8fafc;
  --bg-panel: #ffffff;
  
  /* 边框颜色加深，使其在白底上可见 */
  --border-subtle: #e2e8f0;
  --border-hover: #cbd5e1;
  
  /* 核心文字颜色调整为深灰/黑色，确保对比度 */
  --text-primary: #0f172a;    /* 最深的颜色，用于标题和输入内容 */
  --text-secondary: #64748b;  /* 中等灰色，用于副标题和标签 */
  --text-muted: #94a3b8;      /* 浅灰色，用于 placeholder */
  
  /* 品牌强调色（参考你截图中的深绿色） */
  --accent: #2c7a62;
  --accent-hover: #22604d;
  
  --error: #ef4444;
}

* {
  box-sizing: border-box;
}

.saas-login-container {
  display: flex;
  min-height: 100vh;
  background-color: var(--bg-light);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  /* 选中文本时的颜色 */
  selection-background: rgba(44, 122, 98, 0.2);
  selection-color: var(--text-primary);
}

/* ================= 左侧沉浸区 (保持暗黑极客风，形成撞色高级感) ================= */
.presentation-side {
  position: relative;
  flex: 1.2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 80px;
  overflow: hidden;
  border-right: 1px solid var(--border-subtle);
  background: #000000;
  color: #ffffff;
}

.dark-grid {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(to right, rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(circle at center, black 40%, transparent 80%);
  -webkit-mask-image: radial-gradient(circle at center, black 40%, transparent 80%);
  z-index: 1;
}

/* Nexus 抽象轨道 */
.nexus-art {
  position: absolute;
  top: 50%;
  right: -10%;
  transform: translateY(-50%);
  width: 800px;
  height: 800px;
  pointer-events: none;
  z-index: 2;
  opacity: 0.8;
  mask-image: radial-gradient(circle at center, black 30%, transparent 70%);
  -webkit-mask-image: radial-gradient(circle at center, black 30%, transparent 70%);
}

.core-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  filter: blur(20px);
}

.orbit {
  position: absolute;
  top: 50%;
  left: 50%;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transform: translate(-50%, -50%);
}

.orbit-1 { width: 300px; height: 300px; animation: spin 30s linear infinite; }
.orbit-2 { width: 500px; height: 500px; animation: spin 45s linear infinite reverse; }
.orbit-3 { width: 700px; height: 700px; animation: spin 60s linear infinite; }

@keyframes spin {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

.agent-node {
  position: absolute;
  width: 4px;
  height: 4px;
  background: #fff;
  border-radius: 50%;
  box-shadow: 0 0 12px 2px rgba(255, 255, 255, 0.8);
}

.node-a { top: -2px; left: 50%; transform: translateX(-50%); }
.node-b { top: 50%; left: -2px; transform: translateY(-50%); }
.node-c { bottom: -2px; left: 30%; }
.node-d { top: 20%; right: -2px; }

.presentation-content {
  position: relative;
  z-index: 10;
  max-width: 540px;
}

.brand-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 99px;
  font-size: 13px;
  font-weight: 500;
  color: #a1a1aa;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  margin-bottom: 32px;
}

.hero-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 68px;
  line-height: 1.05;
  font-weight: 700;
  letter-spacing: -0.04em;
  margin: 0 0 24px 0;
  color: #fff;
}

.text-glow {
  color: transparent;
  background: linear-gradient(180deg, #fff 0%, #a1a1aa 100%);
  -webkit-background-clip: text;
  background-clip: text;
}

.hero-subtitle {
  font-size: 18px;
  line-height: 1.6;
  color: #a1a1aa;
  max-width: 480px;
}

/* ================= 右侧表单区 (浅色高对比模式) ================= */
.auth-side {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-light);
  padding: 40px;
  color: var(--text-primary);
}

/* 匹配你截图中的浅色网格背景 */
.light-grid-bg {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(to right, rgba(0, 0, 0, 0.03) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0, 0, 0, 0.03) 1px, transparent 1px);
  background-size: 32px 32px;
  z-index: 0;
}

.auth-wrapper {
  position: relative;
  z-index: 10;
  width: 100%;
  max-width: 380px;
}

.auth-header {
  margin-bottom: 40px;
}

.auth-header h2 {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 8px 0;
  color: var(--text-primary);
}

.auth-subtext {
  color: var(--text-secondary);
  font-size: 15px;
  margin: 0;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.label-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.input-group label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.optional {
  color: var(--text-muted);
  font-weight: 400;
}

.forgot-link {
  font-size: 12px;
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s;
}

.forgot-link:hover {
  color: var(--accent); /* 鼠标悬停变成主题绿 */
}

/* 输入框样式调整 */
.input-group input {
  width: 100%;
  height: 46px;
  padding: 0 14px;
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  color: var(--text-primary);
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  transition: all 0.2s ease;
  outline: none;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

.input-group input::placeholder {
  color: var(--text-muted);
}

.input-group input:hover {
  border-color: var(--border-hover);
}

.input-group input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(44, 122, 98, 0.15); /* 聚焦时发绿色的光环 */
}

/* 按钮样式：深绿色，白字 */
.primary-btn {
  margin-top: 12px;
  width: 100%;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--accent);
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(44, 122, 98, 0.2);
}

.primary-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(44, 122, 98, 0.3);
}

.primary-btn:active:not(:disabled) {
  transform: translateY(0);
}

.primary-btn:disabled {
  background: #e2e8f0;
  color: #94a3b8;
  cursor: not-allowed;
  box-shadow: none;
}

.loading-state {
  display: flex;
  align-items: center;
  gap: 8px;
}

.spinner {
  animation: spin 1s linear infinite;
}

/* 错误提示框 */
.alert-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
}

.alert-box.error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: var(--error);
}

/* 底部切换区 */
.auth-footer {
  margin-top: 32px;
  text-align: center;
  font-size: 14px;
  color: var(--text-secondary);
}

/* 这里的 Sign up 调整了颜色和粗细，确保清晰可见 */
.switch-mode-btn {
  background: none;
  border: none;
  color: var(--accent);
  font-weight: 600;
  padding: 0;
  margin-left: 4px;
  cursor: pointer;
  text-decoration: underline;
  text-decoration-color: transparent;
  transition: text-decoration-color 0.2s;
}

.switch-mode-btn:hover {
  text-decoration-color: var(--accent);
}

/* Vue 动画 */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  transform: translateY(-10px);
  margin-top: -8px;
}

.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 80px;
  transform: translateY(0);
  margin-top: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 响应式适配 */
@media (max-width: 1024px) {
  .presentation-side {
    display: none;
  }
  
  .auth-side {
    background: var(--bg-light);
  }
}
</style>