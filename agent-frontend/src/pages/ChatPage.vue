<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import {
  AlertTriangle,
  BrainCircuit,
  Check,
  CircleSlash2,
  Copy,
  FolderOpen,
  Loader2,
  LogOut,
  Menu,
  MessageSquare,
  Plus,
  RefreshCw,
  Save,
  Send,
  Sparkles,
  TerminalSquare,
  Trash2,
  Upload,
  User as UserIcon,
  X,
} from 'lucide-vue-next'
import { deleteSession, getMessages, getSessions, sendStreamMessage } from '../api/chat'
import {
  createSkill,
  deleteSkill,
  getSkillDetail,
  getSkills,
  importSkillDirectory,
  importSkillZip,
  previewSkillZip,
  reloadSkills,
  setSkillEnabled,
} from '../api/skills'
import type { User } from '../types/auth'
import type { ChatMessage, ChatSession } from '../types/chat'
import type { Skill, SkillDetail, SkillImportPreview } from '../types/skill'

type ConfirmDialogState = {
  open: boolean
  title: string
  message: string
  confirmText: string
  loading: boolean
  onConfirm: (() => Promise<void>) | null
}

const props = defineProps<{
  user: User
}>()

const emit = defineEmits<{
  (e: 'logout'): void
}>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

function renderMarkdown(content: string) {
  if (!content) return ''

  const rawHtml = md.render(content.replace(/\\r/g, '').replace(/\\n/g, '\n'))
  const sanitize = DOMPurify.sanitize || (DOMPurify as any).default?.sanitize
  return typeof sanitize === 'function' ? sanitize(rawHtml) : rawHtml
}

const sessions = ref<ChatSession[]>([])
const messages = ref<ChatMessage[]>([])
const skills = ref<Skill[]>([])
const activeThreadId = ref('')
const inputText = ref('')
const selectedSkill = ref<SkillDetail | null>(null)
const selectedSkillName = ref('')

const loadingSessions = ref(false)
const loadingMessages = ref(false)
const loadingSkills = ref(false)
const loadingSkillDetail = ref(false)
const sending = ref(false)
const sidebarOpen = ref(true)
const skillPanelOpen = ref(false)
const creatingSkill = ref(false)
const skillBusyName = ref('')
const deletingThreadId = ref('')
const skillError = ref('')
const importError = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const skillFileInput = ref<HTMLInputElement | null>(null)

const skillForm = ref({
  name: '',
  description: '',
  content: '',
  needs_time_context: false,
})

const importForm = ref({
  source: '',
})

const zipFile = ref<File | null>(null)
const zipPreview = ref<SkillImportPreview | null>(null)
const importingZip = ref(false)
const importingDirectory = ref(false)
const importingZipConfirm = ref(false)
const confirmDialog = ref<ConfirmDialogState>({
  open: false,
  title: '',
  message: '',
  confirmText: 'Confirm',
  loading: false,
  onConfirm: null,
})

const displayName = computed(() => props.user.nickname || props.user.username)
const currentSkillTools = computed(() => selectedSkill.value?.tools || [])

function createThreadId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `thread_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function normalizeSkillNameInput(value: string) {
  return value.trim().replace(/\s+/g, '-').toLowerCase()
}

function formatTime(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 19).replace('T', ' ')
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function isActiveSkill(skill: Skill) {
  return selectedSkillName.value === skill.name
}

async function loadSessions() {
  loadingSessions.value = true
  try {
    sessions.value = await getSessions()
  } finally {
    loadingSessions.value = false
  }
}

async function loadSkills() {
  loadingSkills.value = true
  try {
    skills.value = await getSkills()
  } finally {
    loadingSkills.value = false
  }
}

async function refreshAllSkills() {
  loadingSkills.value = true
  try {
    skills.value = await reloadSkills()
  } finally {
    loadingSkills.value = false
  }
}

function openSkillPanel() {
  skillPanelOpen.value = true
  skillError.value = ''
  importError.value = ''
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
    needs_time_context: false,
  }
}

function resetZipImport() {
  zipFile.value = null
  zipPreview.value = null
  importError.value = ''
  if (skillFileInput.value) {
    skillFileInput.value.value = ''
  }
}

async function handleCreateSkill() {
  if (creatingSkill.value) return

  const payload = {
    name: normalizeSkillNameInput(skillForm.value.name),
    description: skillForm.value.description.trim(),
    content: skillForm.value.content.trim(),
    needs_time_context: skillForm.value.needs_time_context,
  }

  if (!payload.name || !payload.description || !payload.content) {
    skillError.value = '请填写名称、描述和提示词。'
    return
  }

  creatingSkill.value = true
  skillError.value = ''

  try {
    const skill = await createSkill(payload)
    skills.value = [skill, ...skills.value.filter((item) => item.name !== skill.name)]
    resetSkillForm()
  } catch (e: any) {
    skillError.value = e.message || '创建 Skill 失败。'
  } finally {
    creatingSkill.value = false
  }
}

async function handleZipFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] || null
  zipFile.value = file
  zipPreview.value = null
  importError.value = ''

  if (!file) return

  importingZip.value = true
  try {
    zipPreview.value = await previewSkillZip(file)
  } catch (e: any) {
    importError.value = e.message || '解析 zip 包失败。'
  } finally {
    importingZip.value = false
  }
}

async function confirmZipImport() {
  if (!zipFile.value || importingZipConfirm.value) return

  importingZipConfirm.value = true
  importError.value = ''

  try {
    const result = await importSkillZip(zipFile.value)
    skills.value = [result.skill, ...skills.value.filter((item) => item.name !== result.skill.name)]
    zipPreview.value = result.preview
    await loadSkills()
    resetZipImport()
  } catch (e: any) {
    importError.value = e.message || '导入 zip 包失败。'
  } finally {
    importingZipConfirm.value = false
  }
}

async function handleDirectoryImport() {
  if (importingDirectory.value) return

  const source = importForm.value.source.trim()
  if (!source) {
    importError.value = '请输入 skills/file 下的文件夹名。'
    return
  }

  importingDirectory.value = true
  importError.value = ''

  try {
    const result = await importSkillDirectory(source)
    skills.value = [result.skill, ...skills.value.filter((item) => item.name !== result.skill.name)]
    importForm.value.source = ''
    await loadSkills()
  } catch (e: any) {
    importError.value = e.message || '导入 Skill 文件夹失败。'
  } finally {
    importingDirectory.value = false
  }
}

async function selectSkill(skill: Skill) {
  if (selectedSkillName.value === skill.name && selectedSkill.value) return

  selectedSkillName.value = skill.name
  loadingSkillDetail.value = true

  try {
    selectedSkill.value = await getSkillDetail(skill.name)
  } catch (e) {
    console.error('加载 Skill 详情失败', e)
  } finally {
    loadingSkillDetail.value = false
  }
}

async function toggleSkillEnabled(skill: Skill) {
  if (skill.protected || skillBusyName.value) return

  skillBusyName.value = skill.name
  try {
    const updated = await setSkillEnabled(skill.name, !skill.enabled)
    skills.value = skills.value.map((item) => (item.name === updated.name ? updated : item))
    if (selectedSkill.value?.name === updated.name) {
      selectedSkill.value = await getSkillDetail(updated.name)
    }
  } catch (e: any) {
    skillError.value = e.message || '更新 Skill 状态失败。'
  } finally {
    skillBusyName.value = ''
  }
}

function openConfirmDialog(options: {
  title: string
  message: string
  confirmText: string
  onConfirm: () => Promise<void>
}) {
  confirmDialog.value = {
    open: true,
    title: options.title,
    message: options.message,
    confirmText: options.confirmText,
    loading: false,
    onConfirm: options.onConfirm,
  }
}

function closeConfirmDialog(force = false) {
  if (confirmDialog.value.loading && !force) return

  confirmDialog.value = {
    open: false,
    title: '',
    message: '',
    confirmText: 'Confirm',
    loading: false,
    onConfirm: null,
  }
}

function cancelConfirmDialog() {
  closeConfirmDialog()
}

async function confirmDialogAction() {
  if (!confirmDialog.value.onConfirm || confirmDialog.value.loading) return

  confirmDialog.value.loading = true
  try {
    await confirmDialog.value.onConfirm()
    closeConfirmDialog(true)
  } finally {
    confirmDialog.value.loading = false
  }
}

async function removeSkill(skill: Skill) {
  skillBusyName.value = skill.name
  try {
    await deleteSkill(skill.name)
    skills.value = skills.value.filter((item) => item.name !== skill.name)
    if (selectedSkillName.value === skill.name) {
      selectedSkill.value = null
      selectedSkillName.value = ''
    }
  } catch (e: any) {
    skillError.value = e.message || '删除 Skill 失败。'
  } finally {
    skillBusyName.value = ''
  }
}

function handleDeleteSkill(skill: Skill) {
  if (skill.protected || skillBusyName.value) return

  openConfirmDialog({
    title: '删除 Skill',
    message: `确认从 Skill 库中删除 "${skill.name}" 吗？此操作不可撤销。`,
    confirmText: '删除 Skill',
    onConfirm: () => removeSkill(skill),
  })
}

async function removeThread(threadId: string) {
  deletingThreadId.value = threadId
  try {
    const deleted = await deleteSession(threadId)
    if (deleted) {
      const nextSessions = sessions.value.filter((item) => item.thread_id !== threadId)
      sessions.value = nextSessions

      if (activeThreadId.value === threadId) {
        if (nextSessions.length > 0) {
          await selectSession(nextSessions[0].thread_id)
        } else {
          newSession()
        }
      }
    }
  } catch (e) {
    console.error('删除会话失败', e)
  } finally {
    deletingThreadId.value = ''
  }
}

function deleteThread(threadId: string) {
  if (deletingThreadId.value) return

  const session = sessions.value.find((item) => item.thread_id === threadId)
  openConfirmDialog({
    title: '删除会话',
    message: `确认删除 "${session?.title || '当前会话'}" 及其消息历史吗？`,
    confirmText: '删除',
    onConfirm: () => removeThread(threadId),
  })
}

async function selectSession(threadId: string) {
  if (activeThreadId.value === threadId) return

  activeThreadId.value = threadId
  loadingMessages.value = true

  try {
    messages.value = await getMessages(threadId)
    scrollToBottom()
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

  messages.value.push({ role: 'user', content: text })
  scrollToBottom()

  messages.value.push({ role: 'assistant', content: '' })
  const aiMessageIndex = messages.value.length - 1

  try {
    await sendStreamMessage(text, activeThreadId.value, (chunkText) => {
      const currentMessage = messages.value[aiMessageIndex]
      messages.value[aiMessageIndex] = {
        ...currentMessage,
        content: currentMessage.content + chunkText,
      }
      scrollToBottom()
    })

    if (messages.value.length === 2) {
      await loadSessions()
    }
  } catch (e: any) {
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

function copySkillMd() {
  if (!selectedSkill.value?.skill_md) return
  navigator.clipboard?.writeText(selectedSkill.value.skill_md).catch(() => {})
}

onMounted(async () => {
  await Promise.all([loadSessions(), loadSkills()])

  if (skills.value.length > 0) {
    await selectSkill(skills.value[0])
  }

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

    <aside class="nx-sidebar" :class="{ 'nx-closed': !sidebarOpen }">
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
          <div
            v-for="s in sessions"
            :key="s.thread_id"
            class="nx-session-item"
            :class="{ 'nx-active': s.thread_id === activeThreadId }"
            @click="selectSession(s.thread_id)"
          >
            <MessageSquare :size="16" class="nx-icon-muted" />
            <div class="nx-session-copy">
              <span class="nx-session-title">{{ s.title || '新会话' }}</span>
              <small class="nx-session-time">{{ formatTime(s.updated_at) }}</small>
            </div>
            <button
              class="nx-session-delete"
              type="button"
              title="删除会话"
              :disabled="deletingThreadId === s.thread_id"
              @click.stop="deleteThread(s.thread_id)"
            >
              <Trash2 :size="14" />
            </button>
          </div>
        </template>
      </div>

      <div class="nx-sidebar-bottom">
        <div class="nx-user">
          <div class="nx-avatar">{{ displayName.charAt(0).toUpperCase() }}</div>
          <span>{{ displayName }}</span>
        </div>

        <button class="nx-btn-logout" @click="emit('logout')" title="退出登录">
          <LogOut :size="18" />
        </button>
      </div>
    </aside>

    <div v-if="skillPanelOpen" class="nx-skill-backdrop" @click="closeSkillPanel"></div>
    <aside class="nx-skill-panel" :class="{ 'nx-open': skillPanelOpen }">
      <div class="nx-skill-head">
        <div>
          <div class="nx-skill-kicker">智能体技能</div>
          <h2>Skill 库</h2>
        </div>

        <div class="nx-skill-actions">
          <button class="nx-icon-btn" title="刷新 Skills" @click="refreshAllSkills">
            <RefreshCw :class="{ 'nx-spin': loadingSkills }" :size="18" />
          </button>
          <button class="nx-icon-btn" title="关闭" @click="closeSkillPanel">
            <X :size="18" />
          </button>
        </div>
      </div>

      <div class="nx-skill-body">
        <div class="nx-skill-left">
          <section class="nx-skill-list">
          <div class="nx-section-head">
            <h3>Skill 列表</h3>
            <button class="nx-ghost-btn" type="button" @click="refreshAllSkills">
              <RefreshCw :size="14" />
              <span>刷新</span>
            </button>
          </div>

          <div v-if="loadingSkills" class="nx-center-loader">
            <Loader2 class="nx-spin" :size="18" />
          </div>

          <div
            v-for="skill in skills"
            :key="skill.name"
            class="nx-skill-row"
            :class="{ active: isActiveSkill(skill), disabled: !skill.enabled }"
            @click="selectSkill(skill)"
          >
            <div class="nx-skill-row-top">
              <strong>{{ skill.name }}</strong>
              <span>{{ skill.tool_count }} 个工具</span>
            </div>
            <p>{{ skill.description }}</p>
            <div class="nx-skill-row-meta">
              <span v-if="skill.has_mcp">MCP</span>
              <span v-if="skill.degraded" class="warn">异常</span>
              <span v-if="!skill.enabled" class="warn">已禁用</span>
            </div>
          </div>
          </section>

          <section class="nx-import-panel">
            <div class="nx-section-head">
              <h3>导入 Skill</h3>
              <button class="nx-ghost-btn" type="button" @click="refreshAllSkills">
                <FolderOpen :size="14" />
                <span>重新加载</span>
              </button>
            </div>

            <div class="nx-import-grid">
              <label class="nx-upload-box">
                <input
                  ref="skillFileInput"
                  type="file"
                  accept=".zip"
                  @change="handleZipFileChange"
                />
                <Upload :size="18" />
                <span>上传 .zip Skill 包</span>
                <small v-if="zipFile">{{ zipFile.name }}</small>
              </label>

              <div class="nx-import-form">
                <label>
                  <span>skills/file 下的文件夹</span>
                  <input
                    v-model="importForm.source"
                    placeholder="my_skill"
                    autocomplete="off"
                  />
                </label>
                <button class="nx-btn-save secondary" type="button" :disabled="importingDirectory" @click="handleDirectoryImport">
                  <Loader2 v-if="importingDirectory" class="nx-spin" :size="17" />
                  <FolderOpen v-else :size="17" />
                  <span>导入文件夹</span>
                </button>
              </div>
            </div>

            <div v-if="zipPreview" class="nx-preview-card">
              <div class="nx-preview-top">
                <div>
                  <strong>{{ zipPreview.name }}</strong>
                  <p>{{ zipPreview.description }}</p>
                </div>
                <span>{{ zipPreview.tool_count }} 个工具</span>
              </div>
              <div class="nx-preview-meta">
                <span v-if="zipPreview.has_mcp">MCP</span>
                <span v-if="zipPreview.degraded" class="warn">异常</span>
                <span v-if="!zipPreview.enabled" class="warn">已禁用</span>
              </div>
              <button class="nx-btn-save" type="button" :disabled="importingZipConfirm" @click="confirmZipImport">
                <Loader2 v-if="importingZipConfirm" class="nx-spin" :size="17" />
                <Save v-else :size="17" />
                <span>确认导入</span>
              </button>
            </div>

            <div v-if="importingZip" class="nx-inline-status">
              <Loader2 class="nx-spin" :size="16" />
              <span>正在解析 zip 包...</span>
            </div>

            <div v-if="skillError || importError" class="nx-form-error">
              {{ skillError || importError }}
            </div>

            <form class="nx-prompt-form" @submit.prevent="handleCreateSkill">
              <div class="nx-section-head">
                <h3>从提示词创建</h3>
              </div>
              <label>
                <span>名称</span>
                <input v-model="skillForm.name" autocomplete="off" placeholder="product-support" />
              </label>
              <label>
                <span>描述</span>
                <input v-model="skillForm.description" autocomplete="off" placeholder="处理产品支持类问题" />
              </label>
              <label>
                <span>提示词</span>
                <textarea v-model="skillForm.content" rows="7" placeholder="# 目的&#10;描述这个 Skill 应该做什么。"></textarea>
              </label>
              <label class="nx-check-row">
                <input v-model="skillForm.needs_time_context" type="checkbox" />
                <span>需要当前时间上下文</span>
              </label>
              <button class="nx-btn-save" :disabled="creatingSkill" type="submit">
                <Loader2 v-if="creatingSkill" class="nx-spin" :size="17" />
                <Save v-else :size="17" />
                <span>创建 Skill</span>
              </button>
            </form>
          </section>
        </div>

        <section class="nx-skill-detail">
          <div class="nx-section-head">
            <h3>详情</h3>
            <button class="nx-ghost-btn" type="button" @click="copySkillMd">
              <Copy :size="14" />
              <span>复制 MD</span>
            </button>
          </div>

          <div v-if="loadingSkillDetail" class="nx-center-loader">
            <Loader2 class="nx-spin" :size="18" />
          </div>

          <template v-else-if="selectedSkill">
            <div class="nx-detail-grid">
              <div>
                <label>名称</label>
                <div>{{ selectedSkill.name }}</div>
              </div>
              <div>
                <label>描述</label>
                <div>{{ selectedSkill.description }}</div>
              </div>
              <div>
                <label>状态</label>
                <div>{{ selectedSkill.enabled ? '已启用' : '已禁用' }}</div>
              </div>
              <div>
                <label>工具数量</label>
                <div>{{ selectedSkill.tool_count }}</div>
              </div>
            </div>

            <div class="nx-detail-actions">
              <button class="nx-ghost-btn" type="button" @click="toggleSkillEnabled(selectedSkill)">
                <CircleSlash2 v-if="selectedSkill.enabled" :size="14" />
                <Check v-else :size="14" />
                <span>{{ selectedSkill.enabled ? '禁用' : '启用' }}</span>
              </button>
              <button class="nx-ghost-btn danger" type="button" @click="handleDeleteSkill(selectedSkill)">
                <Trash2 :size="14" />
                <span>删除</span>
              </button>
            </div>

            <div class="nx-md-block">
              <div class="nx-md-head">
                <h4>SKILL.md</h4>
                <button class="nx-icon-btn small" type="button" title="复制" @click="copySkillMd">
                  <Copy :size="14" />
                </button>
              </div>
              <pre>{{ selectedSkill.skill_md || '暂无 SKILL.md 内容。' }}</pre>
            </div>

            <div class="nx-md-block">
              <div class="nx-md-head">
                <h4>元数据</h4>
              </div>
              <pre>{{ JSON.stringify(selectedSkill.skill_json, null, 2) }}</pre>
            </div>

            <div class="nx-md-block">
              <div class="nx-md-head">
                <h4>工具列表</h4>
              </div>
              <div class="nx-tool-list">
                <div v-for="tool in currentSkillTools" :key="tool.name" class="nx-tool-row">
                  <strong>{{ tool.name }}</strong>
                  <span>{{ tool.description || '暂无描述' }}</span>
                </div>
              </div>
            </div>
          </template>

          <div v-else class="nx-empty-panel">
            选择一个 Skill 查看详情。
          </div>
        </section>
      </div>
    </aside>

    <div v-if="confirmDialog.open" class="nx-modal-backdrop" @click="cancelConfirmDialog">
      <div class="nx-confirm-modal" role="dialog" aria-modal="true" @click.stop>
        <button class="nx-confirm-close" type="button" :disabled="confirmDialog.loading" title="关闭" @click="cancelConfirmDialog">
          <X :size="16" />
        </button>
        <div class="nx-confirm-main">
          <div class="nx-confirm-icon">
            <AlertTriangle :size="22" />
          </div>
          <div class="nx-confirm-copy">
            <h3>{{ confirmDialog.title }}</h3>
            <p>{{ confirmDialog.message }}</p>
          </div>
        </div>
        <div class="nx-confirm-actions">
          <button class="nx-modal-btn" type="button" :disabled="confirmDialog.loading" @click="cancelConfirmDialog">
            取消
          </button>
          <button class="nx-modal-btn danger" type="button" :disabled="confirmDialog.loading" @click="confirmDialogAction">
            <Loader2 v-if="confirmDialog.loading" class="nx-spin" :size="16" />
            <Trash2 v-else :size="16" />
            <span>{{ confirmDialog.confirmText }}</span>
          </button>
        </div>
      </div>
    </div>

    <main class="nx-main-area">
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

        <div v-else class="nx-feed">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            class="nx-msg-row"
            :class="msg.role"
          >
            <div v-if="msg.role === 'assistant'" class="nx-msg-avatar ai-avatar">
              <Sparkles :size="16" />
            </div>

            <div class="nx-bubble" :class="{ 'nx-markdown': msg.role === 'assistant' }">
              <div v-if="msg.role === 'assistant' && !msg.content" class="nx-typing">
                <span></span><span></span><span></span>
              </div>
              <div v-else-if="msg.role === 'assistant' && msg.content" v-html="renderMarkdown(msg.content)"></div>
              <template v-else>{{ msg.content }}</template>
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

          <button class="nx-btn-send" :disabled="!inputText.trim() || sending" @click="handleSend">
            <Send :size="18" />
          </button>
        </div>

        <div class="nx-footer-text">
          Nexus OS Multi-Agent Collaboration Engine
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@600;700&display=swap');

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

.nx-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  background-color: #ffffff;
  font-family: 'Inter', -apple-system, sans-serif;
  overflow: hidden;
}

.nx-sidebar {
  width: 320px;
  flex-shrink: 0;
  background-color: #0b1120 !important;
  color: #f8fafc !important;
  border-right: 1px solid #1e293b;
  display: flex;
  flex-direction: column;
  transition: margin-left 0.3s ease;
  z-index: 20;
}

.nx-sidebar.nx-closed {
  margin-left: -320px;
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
  margin-bottom: 20px;
}

.nx-btn-new,
.nx-btn-skills,
.nx-btn-save,
.nx-btn-send,
.nx-ghost-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.nx-btn-new {
  width: 100%;
  padding: 12px 16px;
  background-color: #10b981 !important;
  color: #ffffff !important;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.nx-btn-skills {
  width: 100%;
  margin-top: 10px;
  padding: 11px 16px;
  background-color: transparent;
  color: #cbd5e1;
  border: 1px solid #334155;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.nx-session-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 10px 12px;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.42) transparent;
}

.nx-session-wrap::-webkit-scrollbar,
.nx-skill-body::-webkit-scrollbar,
.nx-skill-left::-webkit-scrollbar,
.nx-skill-list::-webkit-scrollbar,
.nx-skill-detail::-webkit-scrollbar,
.nx-md-block pre::-webkit-scrollbar,
.nx-messages::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.nx-session-wrap::-webkit-scrollbar-track,
.nx-skill-body::-webkit-scrollbar-track,
.nx-skill-left::-webkit-scrollbar-track,
.nx-skill-list::-webkit-scrollbar-track,
.nx-skill-detail::-webkit-scrollbar-track,
.nx-md-block pre::-webkit-scrollbar-track,
.nx-messages::-webkit-scrollbar-track {
  background: transparent;
}

.nx-session-wrap::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.32);
  border-radius: 999px;
}

.nx-skill-body::-webkit-scrollbar-thumb,
.nx-skill-left::-webkit-scrollbar-thumb,
.nx-skill-list::-webkit-scrollbar-thumb,
.nx-skill-detail::-webkit-scrollbar-thumb,
.nx-md-block pre::-webkit-scrollbar-thumb,
.nx-messages::-webkit-scrollbar-thumb {
  background: rgba(100, 116, 139, 0.24);
  border-radius: 999px;
}

.nx-session-wrap::-webkit-scrollbar-thumb:hover,
.nx-skill-body::-webkit-scrollbar-thumb:hover,
.nx-skill-left::-webkit-scrollbar-thumb:hover,
.nx-skill-list::-webkit-scrollbar-thumb:hover,
.nx-skill-detail::-webkit-scrollbar-thumb:hover,
.nx-md-block pre::-webkit-scrollbar-thumb:hover,
.nx-messages::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 116, 139, 0.46);
}

.nx-list-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  margin: 16px 8px 8px;
}

.nx-session-item {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) 28px;
  align-items: center;
  gap: 10px;
  width: 100%;
  margin-bottom: 8px;
  padding: 10px 12px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  color: #cbd5e1;
  font-size: 14px;
  cursor: pointer;
}

.nx-session-item:hover {
  background-color: #1e293b;
  color: #ffffff;
}

.nx-session-item.nx-active {
  background-color: rgba(16, 185, 129, 0.15);
  color: #34d399;
  font-weight: 500;
}

.nx-session-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nx-session-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.nx-session-time {
  color: rgba(203, 213, 225, 0.64);
  font-size: 12px;
  line-height: 1.2;
}

.nx-session-delete {
  width: 28px;
  height: 28px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
}

.nx-session-item:hover .nx-session-delete {
  opacity: 1;
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(148, 163, 184, 0.18);
}

.nx-session-delete:hover {
  color: #fecaca;
  background: rgba(239, 68, 68, 0.14) !important;
}

.nx-session-delete:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.nx-sidebar-bottom {
  padding: 16px 20px;
  border-top: 1px solid #1e293b;
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
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nx-btn-logout {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 6px;
}

.nx-btn-logout:hover {
  color: #ef4444;
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
  width: min(1060px, 72vw);
  min-width: min(100vw, 880px);
  height: 100vh;
  background: #f8fafc;
  border-left: 1px solid #e2e8f0;
  box-shadow: -24px 0 70px rgba(15, 23, 42, 0.2);
  transform: translateX(100%);
  transition: transform 0.24s ease;
  z-index: 30;
  display: flex;
  flex-direction: column;
  color: #0f172a;
}

.nx-skill-panel.nx-open {
  transform: translateX(0);
}

.nx-skill-head,
.nx-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.nx-skill-head {
  min-height: 78px;
  padding: 18px 24px;
  border-bottom: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
}

.nx-skill-kicker {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.nx-skill-head h2,
.nx-section-head h3 {
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
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  color: #475569;
  cursor: pointer;
}

.nx-icon-btn.small {
  width: 30px;
  height: 30px;
}

.nx-icon-btn:hover,
.nx-ghost-btn:hover {
  background: #f8fafc;
}

.nx-skill-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(330px, 0.92fr) minmax(460px, 1.28fr);
  gap: 16px;
  overflow: hidden;
  padding: 18px 20px 22px;
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 116, 139, 0.26) transparent;
}

.nx-skill-left {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 2px;
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 116, 139, 0.26) transparent;
}

.nx-skill-list,
.nx-skill-detail {
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  scrollbar-width: thin;
  scrollbar-color: rgba(100, 116, 139, 0.26) transparent;
}

.nx-skill-list {
  flex: 0 0 min(44vh, 430px);
}

.nx-skill-detail {
  height: 100%;
}

.nx-skill-row {
  margin-top: 10px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  background: #fff;
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;
}

.nx-skill-row:hover {
  border-color: #99f6e4;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.nx-skill-row.active {
  border-color: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.08);
}

.nx-skill-row.disabled {
  opacity: 0.72;
}

.nx-skill-row-top,
.nx-preview-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.nx-skill-row-top span,
.nx-preview-top span {
  flex-shrink: 0;
  color: #0f766e;
  background: #ccfbf1;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 700;
}

.nx-skill-row p,
.nx-preview-top p {
  margin-top: 6px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.nx-skill-row-meta,
.nx-preview-meta {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.nx-skill-row-meta span,
.nx-preview-meta span,
.warn {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
}

.warn {
  background: #fef3c7;
  color: #92400e;
}

.nx-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.nx-detail-grid label {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 4px;
}

.nx-detail-grid > div {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  word-break: break-word;
}

.nx-detail-actions {
  display: flex;
  gap: 8px;
  margin: 14px 0;
}

.nx-ghost-btn {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  padding: 9px 12px;
  cursor: pointer;
}

.nx-ghost-btn.danger {
  color: #b91c1c;
  border-color: #fecaca;
  background: #fff7f7;
}

.nx-md-block {
  margin-top: 14px;
}

.nx-md-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.nx-md-block pre {
  max-height: 150px;
  overflow: auto;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.nx-tool-list {
  display: grid;
  gap: 8px;
}

.nx-tool-row {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.nx-tool-row strong,
.nx-preview-top strong {
  display: block;
  margin-bottom: 4px;
}

.nx-empty-panel {
  margin-top: 16px;
  padding: 18px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  color: #64748b;
}

.nx-import-panel {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  display: grid;
  gap: 12px;
}

.nx-import-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.nx-upload-box {
  position: relative;
  min-height: 110px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  cursor: pointer;
  text-align: center;
  padding: 14px;
}

.nx-upload-box input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.nx-import-form {
  display: grid;
  gap: 10px;
}

.nx-prompt-form {
  display: grid;
  gap: 10px;
}

.nx-import-form label,
.nx-prompt-form label {
  display: grid;
  gap: 6px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.nx-import-form input,
.nx-prompt-form input,
.nx-prompt-form textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #0f172a;
  font: inherit;
  outline: none;
}

.nx-import-form input,
.nx-prompt-form input {
  height: 40px;
  padding: 0 12px;
}

.nx-prompt-form textarea {
  min-height: 106px;
  padding: 10px 12px;
  resize: vertical;
  line-height: 1.55;
}

.nx-check-row {
  display: flex !important;
  grid-template-columns: none !important;
  flex-direction: row;
  align-items: center;
  gap: 8px !important;
  color: #475569 !important;
  font-size: 13px;
}

.nx-check-row input {
  width: 16px !important;
  height: 16px !important;
  padding: 0 !important;
  accent-color: #0f766e;
}

.nx-btn-save {
  min-height: 42px;
  padding: 0 14px;
  border: 0;
  border-radius: 8px;
  background: #0f172a;
  color: #ffffff;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
}

.nx-btn-save.secondary {
  background: #0f766e;
}

.nx-btn-save:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.nx-inline-status,
.nx-center-loader {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.nx-inline-status {
  justify-content: flex-start;
  color: #475569;
  font-size: 13px;
}

.nx-form-error {
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 9px 10px;
  font-size: 13px;
}

.nx-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(8px);
}

.nx-confirm-modal {
  position: relative;
  width: min(460px, 100%);
  padding: 22px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  border-radius: 8px;
  background: #ffffff;
  box-shadow:
    0 28px 80px rgba(15, 23, 42, 0.28),
    0 0 0 1px rgba(255, 255, 255, 0.8) inset;
}

.nx-confirm-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
}

.nx-confirm-close:hover {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #334155;
}

.nx-confirm-main {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 14px;
  padding-right: 26px;
}

.nx-confirm-icon {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fef2f2;
  color: #dc2626;
}

.nx-confirm-copy h3 {
  margin: 0;
  color: #0f172a;
  font-size: 17px;
  font-weight: 800;
  line-height: 1.3;
}

.nx-confirm-copy p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.65;
}

.nx-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}

.nx-modal-btn {
  min-width: 86px;
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  border: 1px solid #d7e0ea;
  border-radius: 8px;
  background: #ffffff;
  color: #334155;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.nx-modal-btn.danger {
  border-color: #ef4444;
  background: #ef4444;
  color: #ffffff;
  box-shadow: 0 10px 22px rgba(239, 68, 68, 0.24);
}

.nx-modal-btn:not(.danger):hover {
  border-color: #94a3b8;
  background: #f8fafc;
}

.nx-modal-btn.danger:hover {
  border-color: #dc2626;
  background: #dc2626;
}

.nx-modal-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.nx-main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background-color: #ffffff !important;
  color: #0f172a;
  z-index: 10;
}

.nx-grid-bg {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, #f1f5f9 1px, transparent 1px),
    linear-gradient(to bottom, #f1f5f9 1px, transparent 1px);
  background-size: 32px 32px;
  z-index: 0;
  pointer-events: none;
}

.nx-topbar {
  position: relative;
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid #e2e8f0;
  background-color: #ffffff !important;
  z-index: 5;
}

.nx-btn-menu {
  background: transparent;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #0f172a;
  cursor: pointer;
  padding: 6px;
  margin-right: 16px;
}

.nx-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
}

.nx-dot {
  width: 8px;
  height: 8px;
  background-color: #10b981;
  border-radius: 50%;
}

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
  background-color: #ecfdf5;
  color: #10b981;
}

.user-avatar {
  background-color: #0f172a;
  color: #ffffff;
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
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #0f172a;
  border-radius: 4px 16px 16px 16px;
}

.user .nx-bubble {
  background-color: #10b981;
  color: #ffffff;
  border-radius: 16px 4px 16px 16px;
  box-shadow: 0 4px 10px rgba(16, 185, 129, 0.2);
}

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
  color: #0f172a;
}

.nx-markdown :deep(code) {
  background: #eef2f7;
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 13px;
  font-family: Consolas, Monaco, 'Courier New', monospace;
}

.nx-markdown :deep(pre) {
  background: #0f172a;
  color: #f8fafc;
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

.nx-input-zone {
  padding: 0 24px 24px;
  position: relative;
  z-index: 5;
  background: linear-gradient(to top, #ffffff 80%, transparent);
}

.nx-input-island {
  max-width: 860px;
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background-color: #ffffff;
  border: 1px solid #cbd5e1 !important;
  border-radius: 24px;
  padding: 8px 8px 8px 20px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}

.nx-input-island:focus-within {
  border-color: #10b981 !important;
  box-shadow: 0 8px 24px rgba(16, 185, 129, 0.1);
}

.nx-textarea {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px 0;
  font-family: 'Inter', sans-serif;
  font-size: 15px;
  color: #0f172a;
  resize: none;
  outline: none;
  max-height: 150px;
}

.nx-textarea::placeholder {
  color: #94a3b8;
}

.nx-btn-send {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #10b981 !important;
  color: #ffffff;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.nx-btn-send:disabled {
  background-color: #e2e8f0 !important;
  color: #94a3b8;
  cursor: not-allowed;
}

.nx-footer-text {
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 12px;
}

.nx-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748b;
}

.nx-empty-icon {
  width: 64px;
  height: 64px;
  background: #ecfdf5;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.nx-empty h2 {
  color: #0f172a;
  font-family: 'Space Grotesk', sans-serif;
  margin-bottom: 8px;
}

.nx-center-loader {
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

.nx-typing {
  display: flex;
  gap: 4px;
  align-items: center;
  height: 48px;
}

.nx-typing span {
  width: 6px;
  height: 6px;
  background-color: #94a3b8;
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

@media (max-width: 1024px) {
  .nx-skill-panel {
    width: min(920px, 100vw);
    min-width: 0;
  }

  .nx-skill-body {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }

  .nx-skill-list {
    flex-basis: auto;
    max-height: 260px;
  }

  .nx-skill-detail {
    min-height: 420px;
  }

  .nx-import-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .nx-sidebar {
    position: absolute;
    height: 100%;
    margin-left: -320px;
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
