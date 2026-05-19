<script setup lang="ts">
import { computed, onMounted, ref, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import {
  Plus,
  LogOut,
  MessageSquare,
  Send,
  Sparkles,
  User as UserIcon,
  Loader2,
  Menu,
  TerminalSquare,
  BrainCircuit,
  X,
  RefreshCw,
  Save
} from 'lucide-vue-next'
import { getMessages, getSessions, sendStreamMessage } from '../api/chat'
import { createSkill, getSkills } from '../api/skills'
import type { User } from '../types/auth'
import type { ChatMessage, ChatSession } from '../types/chat'
import type { Skill } from '../types/skill'

const props = defineProps<{
  user: User
}>()

const emit = defineEmits(['logout'])

// ================= Markdown 渲染 =================
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true // 允许回车换行
})

function renderMarkdown(content: string) {
  if (!content) return ''
  
  // 1. 暴力修复多重转义的换行符 (应对后端奇葩的流式返回)
  let safeContent = content
    .replace(/\\\\n/g, '\n') // 修复双重转义
    .replace(/\\n/g, '\n')   // 修复单重转义
    .replace(/\\r/g, '')     // 剔除回车符干扰

  // 2. 补全未闭合的代码块 (防止打字机过程中代码块吞噬后续普通文本)
  const codeBlockCount = (safeContent.match(/```/g) || []).length
  if (codeBlockCount % 2 !== 0) {
    safeContent += '\n```'
  }
  
  // 3. 补全未闭合的加粗标记 (截图里看到 ** 没被解析，通常是因为残缺)
  const boldCount = (safeContent.match(/\*\*/g) || []).length
  if (boldCount % 2 !== 0) {
    safeContent += '**'
  }

  try {
    const rawHtml = md.render(safeContent)
    
    // 兼容 Vite/Webpack 不同的 DOMPurify 导出形式
    const sanitize = DOMPurify.sanitize || (DOMPurify as any).default?.sanitize
    if (typeof sanitize === 'function') {
      return sanitize(rawHtml)
    }
    return rawHtml 
  } catch (e) {
    console.error('[Markdown 渲染失败]:', e)
    // 兜底：直接返回原生文本。因为我们在 CSS 加了 pre-wrap，所以这里照样能换行！
    return safeContent
  }
}

// ================= 状态管理 =================
const sessions = ref<ChatSession[]>([])
const messages = ref<ChatMessage[]>([])
const skills = ref<Skill[]>([])
const activeThreadId = ref('')
const inputText = ref('')

const loadingSessions = ref(false)
const loadingMessages = ref(false)
const loadingSkills = ref(false)
const sending = ref(false)
const sidebarOpen = ref(true)
const skillPanelOpen = ref(false)
const creatingSkill = ref(false)
const skillError = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const skillForm = ref({
  name: '',
  description: '',
  content: '',
  needs_time_context: false
})

const displayName = computed(() => props.user.nickname || props.user.username)

// ================= 核心逻辑 =================
function createThreadId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `thread_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

async function loadSessions() {
  loadingSessions.value = true
  try {
    sessions.value = await getSessions()
  } catch (e) {
    console.error('Failed to load sessions', e)
  } finally {
    loadingSessions.value = false
  }
}

async function loadSkills() {
  loadingSkills.value = true
  try {
    skills.value = await getSkills()
  } catch (e) {
    console.error('Failed to load skills', e)
  } finally {
    loadingSkills.value = false
  }
}

function openSkillPanel() {
  skillPanelOpen.value = true
  skillError.value = ''
  loadSkills()
}

function closeSkillPanel() {
  skillPanelOpen.value = false
}

function resetSkillForm() {
  skillForm.value = {
    name: '',
    description: '',
    content: '',
    needs_time_context: false
  }
}

async function handleCreateSkill() {
  if (creatingSkill.value) return

  const payload = {
    name: skillForm.value.name.trim(),
    description: skillForm.value.description.trim(),
    content: skillForm.value.content.trim(),
    needs_time_context: skillForm.value.needs_time_context
  }

  if (!payload.name || !payload.description || !payload.content) {
    skillError.value = 'Name, description, and prompt are required.'
    return
  }

  creatingSkill.value = true
  skillError.value = ''

  try {
    const skill = await createSkill(payload)
    skills.value = [skill, ...skills.value.filter((item) => item.name !== skill.name)]
    resetSkillForm()
  } catch (e: any) {
    skillError.value = e.message || 'Failed to create skill.'
  } finally {
    creatingSkill.value = false
  }
}

async function selectSession(threadId: string) {
  if (activeThreadId.value === threadId) return

  activeThreadId.value = threadId
  loadingMessages.value = true

  try {
    messages.value = await getMessages(threadId)
    scrollToBottom()
  } catch (e) {
    console.error('Failed to load messages', e)
  } finally {
    loadingMessages.value = false
  }
}

function newSession() {
  activeThreadId.value = createThreadId()
  messages.value = []

  if (window.innerWidth < 768) {
    sidebarOpen.value = false
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || sending.value) return

  inputText.value = ''
  sending.value = true

  // 推入用户消息
  messages.value.push({
    role: 'user',
    content: text
  })
  scrollToBottom()

  // 关键：先在数组里“垫”一个空的 AI 回复气泡
  messages.value.push({
    role: 'assistant',
    content: ''
  })
  // 记住这个 AI 气泡的索引，一会儿要把字塞进这里面
  const aiMessageIndex = messages.value.length - 1

  try {
    // 调用新的流式接口，传入一个回调函数
    await sendStreamMessage(text, activeThreadId.value, (chunkText) => {
      // 每次收到后端吐出的字，就追加到对应气泡的 content 中
      // Vue 的响应式会自动更新页面，并触发 Markdown 渲染
      const currentMessage = messages.value[aiMessageIndex]
      messages.value[aiMessageIndex] = {
        ...currentMessage,
        content: currentMessage.content + chunkText
      }
      
      // 边打字边滚动
      scrollToBottom()
    })

    // 等流式输出全部完成后，如果这是新会话的第一轮对话，刷新会话列表
    if (messages.value.length === 2) {
      await loadSessions()
    }
  } catch (e: any) {
    // 报错时，把错误信息写进刚才的气泡里
    messages.value[aiMessageIndex].content = `[System Error]: ${e.message || '请求失败'}`
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
}

onMounted(async () => {
  await Promise.all([loadSessions(), loadSkills()])

  if (sessions.value.length > 0) {
    await selectSession(sessions.value[0].thread_id)
  } else {
    newSession()
  }
})
</script>

<template>
  <div class="nx-layout">
    <div v-if="sidebarOpen" class="nx-overlay" @click="toggleSidebar"></div>

    <div class="nx-sidebar" :class="{ 'nx-closed': !sidebarOpen }">
      <div class="nx-sidebar-top">
        <div class="nx-brand">
          <TerminalSquare color="#10B981" :size="24" />
          <span>Nexus OS</span>
        </div>

        <button class="nx-btn-new" @click="newSession">
          <Plus :size="18" />
          <span>New Chat</span>
        </button>

        <button class="nx-btn-skills" @click="openSkillPanel">
          <BrainCircuit :size="18" />
          <span>Skills</span>
        </button>
      </div>

      <div class="nx-session-wrap">
        <div class="nx-list-title">Recent Workspaces</div>

        <div v-if="loadingSessions" class="nx-center-loader">
          <Loader2 class="nx-spin" :size="18" />
        </div>

        <template v-else>
          <button
            v-for="s in sessions"
            :key="s.thread_id"
            class="nx-session-item"
            :class="{ 'nx-active': s.thread_id === activeThreadId }"
            @click="selectSession(s.thread_id)"
          >
            <MessageSquare :size="16" class="nx-icon-muted" />
            <span>{{ s.title }}</span>
          </button>
        </template>
      </div>

      <div class="nx-sidebar-bottom">
        <div class="nx-user">
          <div class="nx-avatar">{{ displayName.charAt(0).toUpperCase() }}</div>
          <span>{{ displayName }}</span>
        </div>

        <button class="nx-btn-logout" @click="emit('logout')" title="Log out">
          <LogOut :size="18" />
        </button>
      </div>
    </div>

    <div v-if="skillPanelOpen" class="nx-skill-backdrop" @click="closeSkillPanel"></div>
    <aside class="nx-skill-panel" :class="{ 'nx-open': skillPanelOpen }">
      <div class="nx-skill-head">
        <div>
          <div class="nx-skill-kicker">Agent Skills</div>
          <h2>Skill Library</h2>
        </div>

        <div class="nx-skill-actions">
          <button class="nx-icon-btn" title="Refresh skills" @click="loadSkills">
            <RefreshCw :class="{ 'nx-spin': loadingSkills }" :size="18" />
          </button>
          <button class="nx-icon-btn" title="Close" @click="closeSkillPanel">
            <X :size="18" />
          </button>
        </div>
      </div>

      <div class="nx-skill-list">
        <div v-if="loadingSkills" class="nx-center-loader">
          <Loader2 class="nx-spin" :size="18" />
        </div>

        <template v-else>
          <div
            v-for="skill in skills"
            :key="skill.name"
            class="nx-skill-item"
          >
            <div class="nx-skill-item-top">
              <strong>{{ skill.name }}</strong>
              <span>{{ skill.tool_count }} tools</span>
            </div>
            <p>{{ skill.description }}</p>
          </div>
        </template>
      </div>

      <form class="nx-skill-form" @submit.prevent="handleCreateSkill">
        <div class="nx-form-title">Add Skill</div>

        <label>
          <span>Name</span>
          <input
            v-model="skillForm.name"
            autocomplete="off"
            placeholder="product-support"
          />
        </label>

        <label>
          <span>Description</span>
          <input
            v-model="skillForm.description"
            autocomplete="off"
            placeholder="Routes product support questions"
          />
        </label>

        <label>
          <span>Prompt</span>
          <textarea
            v-model="skillForm.content"
            rows="8"
            placeholder="# Purpose&#10;Describe what this skill should do.&#10;&#10;# Summary For Runtime&#10;- Add routing hints and constraints."
          ></textarea>
        </label>

        <label class="nx-check-row">
          <input v-model="skillForm.needs_time_context" type="checkbox" />
          <span>Needs current time context</span>
        </label>

        <p v-if="skillError" class="nx-form-error">{{ skillError }}</p>

        <button class="nx-btn-save" :disabled="creatingSkill" type="submit">
          <Loader2 v-if="creatingSkill" class="nx-spin" :size="17" />
          <Save v-else :size="17" />
          <span>Create Skill</span>
        </button>
      </form>
    </aside>

    <div class="nx-main-area">
      <div class="nx-grid-bg"></div>

      <div class="nx-topbar">
        <button class="nx-btn-menu" @click="toggleSidebar">
          <Menu :size="20" />
        </button>

        <div class="nx-badge">
          <span class="nx-dot"></span>
          Thread: {{ activeThreadId.slice(0, 8) }}
        </div>
      </div>

      <div class="nx-messages" ref="messagesContainer">
        <div v-if="messages.length === 0 && !loadingMessages" class="nx-empty">
          <div class="nx-empty-icon">
            <Sparkles color="#10B981" :size="32" />
          </div>
          <h2>How can I help you today?</h2>
          <p>部署多智能体协作、分析数据或编写代码。</p>
        </div>

        <div v-if="loadingMessages" class="nx-center-loader full">
          <Loader2 class="nx-spin" color="#10B981" :size="32" />
        </div>

        <div class="nx-feed" v-else>
          <div
            v-for="(msg, index) in messages"
            :key="index"
            class="nx-msg-row"
            :class="msg.role"
          >
            <div v-if="msg.role === 'assistant'" class="nx-msg-avatar ai-avatar">
              <Sparkles :size="16" />
            </div>

            <div
              class="nx-bubble"
              :class="{ 'nx-markdown': msg.role === 'assistant' }"
            >
              <div v-if="msg.role === 'assistant' && !msg.content" class="nx-typing">
                <span></span>
                <span></span>
                <span></span>
              </div>

              <div
                v-else-if="msg.role === 'assistant' && msg.content"
                v-html="renderMarkdown(msg.content)"
              ></div>

              <template v-else-if="msg.role === 'user'">
                {{ msg.content }}
              </template>
            </div>

            <div v-if="msg.role === 'user'" class="nx-msg-avatar user-avatar">
              <UserIcon :size="16" />
            </div>
          </div>
          </div>
      </div>

      <div class="nx-input-zone">
        <div class="nx-input-island">
          <textarea
            v-model="inputText"
            class="nx-textarea"
            placeholder="Send a message to Nexus..."
            rows="1"
            @keydown="handleKeydown"
          ></textarea>

          <button
            class="nx-btn-send"
            :disabled="!inputText.trim() || sending"
            @click="handleSend"
          >
            <Send :size="18" />
          </button>
        </div>

        <div class="nx-footer-text">
          Nexus OS · Multi-Agent Collaboration Engine
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@600;700&display=swap');

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

.nx-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  background-color: #FFFFFF;
  font-family: 'Inter', -apple-system, sans-serif;
  overflow: hidden;
}

/* ================= 侧边栏 ================= */
.nx-sidebar {
  width: 280px;
  flex-shrink: 0;
  background-color: #0B1120 !important;
  color: #F8FAFC !important;
  border-right: 1px solid #1E293B;
  display: flex;
  flex-direction: column;
  transition: margin-left 0.3s ease;
  z-index: 20;
}

.nx-sidebar.nx-closed {
  margin-left: -280px;
}

.nx-sidebar-top {
  padding: 20px;
}

.nx-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 24px;
}

.nx-btn-new {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background-color: #10B981 !important;
  color: #FFFFFF !important;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.nx-btn-new:hover {
  background-color: #059669 !important;
}

.nx-btn-skills {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 11px 16px;
  background-color: transparent;
  color: #CBD5E1;
  border: 1px solid #334155;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.nx-btn-skills:hover {
  background-color: #1E293B;
  color: #FFFFFF;
}

.nx-session-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px;
}

.nx-session-wrap::-webkit-scrollbar {
  width: 4px;
}

.nx-session-wrap::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 4px;
}

.nx-list-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748B;
  text-transform: uppercase;
  margin: 16px 8px 8px;
}

.nx-session-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #CBD5E1;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.nx-session-item:hover {
  background-color: #1E293B;
  color: #FFFFFF;
}

.nx-session-item.nx-active {
  background-color: rgba(16, 185, 129, 0.15);
  color: #34D399;
  font-weight: 500;
}

.nx-icon-muted {
  opacity: 0.7;
}

.nx-session-item.nx-active .nx-icon-muted {
  opacity: 1;
}

.nx-sidebar-bottom {
  padding: 16px 20px;
  border-top: 1px solid #1E293B;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nx-user {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 500;
}

.nx-avatar {
  width: 32px;
  height: 32px;
  background-color: #1E293B;
  border: 1px solid #334155;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nx-btn-logout {
  background: transparent;
  border: none;
  color: #64748B;
  cursor: pointer;
  padding: 6px;
}

.nx-btn-logout:hover {
  color: #EF4444;
}

.nx-skill-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.28);
  z-index: 28;
}

.nx-skill-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: min(440px, 100vw);
  height: 100vh;
  background: #FFFFFF;
  border-left: 1px solid #E2E8F0;
  box-shadow: -18px 0 40px rgba(15, 23, 42, 0.16);
  transform: translateX(100%);
  transition: transform 0.24s ease;
  z-index: 30;
  display: flex;
  flex-direction: column;
  color: #0F172A;
}

.nx-skill-panel.nx-open {
  transform: translateX(0);
}

.nx-skill-head {
  min-height: 78px;
  padding: 18px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #E2E8F0;
}

.nx-skill-kicker {
  color: #64748B;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.nx-skill-head h2 {
  margin-top: 3px;
  font-size: 20px;
  line-height: 1.2;
}

.nx-skill-actions {
  display: flex;
  gap: 8px;
}

.nx-icon-btn {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  background: #FFFFFF;
  color: #475569;
  cursor: pointer;
}

.nx-icon-btn:hover {
  background: #F8FAFC;
  color: #0F172A;
}

.nx-skill-list {
  max-height: 32vh;
  min-height: 160px;
  overflow-y: auto;
  padding: 14px 20px;
  border-bottom: 1px solid #E2E8F0;
}

.nx-skill-item {
  padding: 12px 0;
  border-bottom: 1px solid #F1F5F9;
}

.nx-skill-item:last-child {
  border-bottom: 0;
}

.nx-skill-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.nx-skill-item strong {
  font-size: 14px;
  color: #0F172A;
  word-break: break-word;
}

.nx-skill-item-top span {
  flex-shrink: 0;
  color: #0F766E;
  background: #CCFBF1;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 700;
}

.nx-skill-item p {
  color: #64748B;
  font-size: 13px;
  line-height: 1.5;
}

.nx-skill-form {
  flex: 1;
  overflow-y: auto;
  padding: 18px 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.nx-form-title {
  font-size: 14px;
  font-weight: 800;
  color: #0F172A;
}

.nx-skill-form label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.nx-skill-form input,
.nx-skill-form textarea {
  width: 100%;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  background: #FFFFFF;
  color: #0F172A;
  font: inherit;
  font-weight: 500;
  outline: none;
}

.nx-skill-form input {
  height: 40px;
  padding: 0 12px;
}

.nx-skill-form textarea {
  min-height: 168px;
  padding: 10px 12px;
  resize: vertical;
  line-height: 1.55;
}

.nx-skill-form input:focus,
.nx-skill-form textarea:focus {
  border-color: #14B8A6;
  box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.12);
}

.nx-check-row {
  flex-direction: row !important;
  align-items: center;
  gap: 9px !important;
  font-weight: 600 !important;
}

.nx-check-row input {
  width: 16px;
  height: 16px;
}

.nx-form-error {
  color: #B91C1C;
  background: #FEF2F2;
  border: 1px solid #FECACA;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 13px;
}

.nx-btn-save {
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 0;
  border-radius: 8px;
  background: #0F172A;
  color: #FFFFFF;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}

.nx-btn-save:disabled {
  background: #94A3B8;
  cursor: not-allowed;
}

/* ================= 右侧主区域 ================= */
.nx-main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background-color: #FFFFFF !important;
  color: #0F172A;
  z-index: 10;
}

.nx-grid-bg {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, #F1F5F9 1px, transparent 1px),
    linear-gradient(to bottom, #F1F5F9 1px, transparent 1px);
  background-size: 32px 32px;
  z-index: 0;
  pointer-events: none;
}

/* ================= 顶部导航 ================= */
.nx-topbar {
  position: relative;
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid #E2E8F0;
  background-color: #FFFFFF !important;
  z-index: 5;
}

.nx-btn-menu {
  background: transparent;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  color: #0F172A;
  cursor: pointer;
  padding: 6px;
  margin-right: 16px;
}

.nx-btn-menu:hover {
  background: #F8FAFC;
}

.nx-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: #64748B;
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid #E2E8F0;
}

.nx-dot {
  width: 8px;
  height: 8px;
  background-color: #10B981;
  border-radius: 50%;
}

/* ================= 消息区 ================= */
.nx-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  position: relative;
  z-index: 5;
  scroll-behavior: smooth;
}

.nx-feed {
  max-width: 860px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-bottom: 40px;
}

.nx-msg-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.nx-msg-row.assistant {
  justify-content: flex-start;
}

.nx-msg-row.user {
  flex-direction: row-reverse;
}

.nx-msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ai-avatar {
  background-color: #ECFDF5;
  color: #10B981;
}

.user-avatar {
  background-color: #0F172A;
  color: #FFFFFF;
}

.nx-bubble {
  max-width: 82%;
  padding: 14px 18px;
  font-size: 15px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.assistant .nx-bubble {
  background-color: #F8FAFC;
  border: 1px solid #E2E8F0;
  color: #0F172A;
  border-radius: 4px 16px 16px 16px;
}

.user .nx-bubble {
  background-color: #10B981;
  color: #FFFFFF;
  border-radius: 16px 4px 16px 16px;
  box-shadow: 0 4px 10px rgba(16, 185, 129, 0.2);
}

/* ================= Markdown 美化 ================= */
.nx-markdown {
  white-space: normal;
}

.nx-markdown :deep(p) {
  margin: 0 0 12px;
}

.nx-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.nx-markdown :deep(ul),
.nx-markdown :deep(ol) {
  margin: 10px 0;
  padding-left: 24px;
}

.nx-markdown :deep(li) {
  margin: 8px 0;
  line-height: 1.8;
}

.nx-markdown :deep(strong) {
  font-weight: 700;
  color: #0F172A;
}

.nx-markdown :deep(h1),
.nx-markdown :deep(h2),
.nx-markdown :deep(h3),
.nx-markdown :deep(h4) {
  margin: 16px 0 10px;
  font-weight: 700;
  line-height: 1.4;
  color: #0F172A;
}

.nx-markdown :deep(h1) {
  font-size: 24px;
}

.nx-markdown :deep(h2) {
  font-size: 21px;
}

.nx-markdown :deep(h3) {
  font-size: 18px;
}

.nx-markdown :deep(code) {
  background: #EEF2F7;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 13px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
}

.nx-markdown :deep(pre) {
  background: #0F172A;
  color: #F8FAFC;
  padding: 14px;
  border-radius: 12px;
  overflow-x: auto;
  margin: 12px 0;
}

.nx-markdown :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.nx-markdown :deep(blockquote) {
  border-left: 4px solid #10B981;
  padding-left: 12px;
  color: #475569;
  margin: 12px 0;
}

.nx-markdown :deep(a) {
  color: #059669;
  text-decoration: underline;
  word-break: break-all;
}

.nx-markdown :deep(hr) {
  border: none;
  border-top: 1px solid #E2E8F0;
  margin: 18px 0;
}

.nx-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
  font-size: 14px;
}

.nx-markdown :deep(th),
.nx-markdown :deep(td) {
  border: 1px solid #E2E8F0;
  padding: 8px 10px;
  text-align: left;
}

.nx-markdown :deep(th) {
  background: #F1F5F9;
  font-weight: 700;
}

/* ================= 输入区 ================= */
.nx-input-zone {
  padding: 0 24px 24px;
  position: relative;
  z-index: 5;
  background: linear-gradient(to top, #FFFFFF 80%, transparent);
}

.nx-input-island {
  max-width: 860px;
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background-color: #FFFFFF;
  border: 1px solid #CBD5E1 !important;
  border-radius: 24px;
  padding: 8px 8px 8px 20px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
  transition: border-color 0.3s, box-shadow 0.3s;
}

.nx-input-island:focus-within {
  border-color: #10B981 !important;
  box-shadow: 0 8px 24px rgba(16, 185, 129, 0.1);
}

.nx-textarea {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px 0;
  font-family: 'Inter', sans-serif;
  font-size: 15px;
  color: #0F172A;
  resize: none;
  outline: none;
  max-height: 150px;
}

.nx-textarea::placeholder {
  color: #94A3B8;
}

.nx-btn-send {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #10B981 !important;
  color: #FFFFFF;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.nx-btn-send:disabled {
  background-color: #E2E8F0 !important;
  color: #94A3B8;
  cursor: not-allowed;
}

.nx-footer-text {
  text-align: center;
  font-size: 12px;
  color: #94A3B8;
  margin-top: 12px;
}

/* ================= 辅助与动画 ================= */
.nx-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748B;
}

.nx-empty-icon {
  width: 64px;
  height: 64px;
  background: #ECFDF5;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.nx-empty h2 {
  color: #0F172A;
  font-family: 'Space Grotesk', sans-serif;
  margin-bottom: 8px;
}

.nx-center-loader {
  display: flex;
  justify-content: center;
  padding: 20px;
}

.nx-center-loader.full {
  height: 100%;
  align-items: center;
}

.nx-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ================= 打字动画 ================= */
.nx-typing {
  display: flex;
  gap: 4px;
  align-items: center;
  height: 48px;
}

.nx-typing span {
  width: 6px;
  height: 6px;
  background-color: #94A3B8;
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out both;
}

.nx-typing span:nth-child(1) {
  animation-delay: -0.32s;
}

.nx-typing span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes typing {
  0%,
  80%,
  100% {
    transform: scale(0);
  }

  40% {
    transform: scale(1);
  }
}

/* ================= 移动端 ================= */
@media (max-width: 768px) {
  .nx-sidebar {
    position: absolute;
    height: 100%;
    margin-left: -280px;
  }

  .nx-sidebar:not(.nx-closed) {
    margin-left: 0;
    box-shadow: 4px 0 24px rgba(0, 0, 0, 0.5);
  }

  .nx-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 15;
  }

  .nx-messages {
    padding: 16px;
  }

  .nx-bubble {
    max-width: 86%;
  }

  .nx-input-zone {
    padding: 0 16px 18px;
  }
}
</style>
