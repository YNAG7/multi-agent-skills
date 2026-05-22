<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  ArrowLeft,
  Check,
  CircleSlash2,
  Copy,
  FileJson,
  FolderOpen,
  Loader2,
  LogOut,
  Plus,
  RefreshCw,
  Save,
  Search,
  TerminalSquare,
  Trash2,
  Upload,
  X,
} from 'lucide-vue-next'
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
  updateSkill,
} from '../api/skills'
import type { User } from '../types/auth'
import type { Skill, SkillDetail, SkillImportPreview } from '../types/skill'

type CreateMode = 'online' | 'zip'

const DEFAULT_SKILL_JSON = {
  enabled: true,
  can_be_main: true,
  needs_time_context: false,
  is_workflow: false,
  mcp_servers: {},
  mcp_tool_allowlist: [],
}

function defaultSkillJsonText() {
  return JSON.stringify(DEFAULT_SKILL_JSON, null, 2)
}

const props = defineProps<{
  user: User
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'logout'): void
}>()

const skills = ref<Skill[]>([])
const selectedSkill = ref<SkillDetail | null>(null)
const selectedSkillName = ref('')
const searchText = ref('')
const loadingSkills = ref(false)
const loadingSkillDetail = ref(false)
const savingSkill = ref(false)
const creatingSkill = ref(false)
const skillBusyName = ref('')
const deletingSkillName = ref('')
const pendingDeleteSkill = ref<Skill | null>(null)
const showCreatePanel = ref(false)
const createMode = ref<CreateMode>('online')
const skillError = ref('')
const createError = ref('')
const importError = ref('')
const savedNotice = ref('')
const skillFileInput = ref<HTMLInputElement | null>(null)

const editor = ref({
  skillMd: '',
  skillJsonText: '{}',
})

const skillForm = ref({
  name: '',
  description: '',
  content: '',
  needs_time_context: false,
  skillJsonText: defaultSkillJsonText(),
})

const importForm = ref({
  source: '',
})

const zipFile = ref<File | null>(null)
const zipPreview = ref<SkillImportPreview | null>(null)
const importingZip = ref(false)
const importingDirectory = ref(false)
const importingZipConfirm = ref(false)

const displayName = computed(() => props.user.nickname || props.user.username)
const currentSkillTools = computed(() => selectedSkill.value?.tools || [])
const selectedSkillJsonPretty = computed(() => {
  if (!selectedSkill.value) return '{}'
  return JSON.stringify(selectedSkill.value.skill_json || {}, null, 2)
})

const filteredSkills = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return skills.value

  return skills.value.filter((skill) => (
    skill.name.toLowerCase().includes(keyword) ||
    skill.description.toLowerCase().includes(keyword)
  ))
})

const hasEditorChanges = computed(() => {
  if (!selectedSkill.value) return false
  return (
    editor.value.skillMd !== (selectedSkill.value.skill_md || '') ||
    editor.value.skillJsonText !== selectedSkillJsonPretty.value
  )
})

function normalizeSkillNameInput(value: string) {
  return value.trim().replace(/\s+/g, '-').toLowerCase()
}

function previewText(value?: string | null, max = 92) {
  if (!value) return ''
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length > max ? `${text.slice(0, max)}...` : text
}

function setError(message: string, scope: 'skill' | 'create' | 'import' = 'skill') {
  if (scope === 'skill') skillError.value = message
  if (scope === 'create') createError.value = message
  if (scope === 'import') importError.value = message
}

function clearMessages() {
  skillError.value = ''
  createError.value = ''
  importError.value = ''
  savedNotice.value = ''
}

function parseJsonText(text: string, label: string) {
  try {
    const parsed = JSON.parse(text || '{}')
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error(`${label} 必须是 JSON object`)
    }
    return parsed as Record<string, any>
  } catch (e: any) {
    throw new Error(e.message || `${label} 不是合法 JSON`)
  }
}

function applyEditor(skill: SkillDetail) {
  editor.value = {
    skillMd: skill.skill_md || '',
    skillJsonText: JSON.stringify(skill.skill_json || {}, null, 2),
  }
}

function resetSkillForm() {
  skillForm.value = {
    name: '',
    description: '',
    content: '',
    needs_time_context: false,
    skillJsonText: defaultSkillJsonText(),
  }
}

function resetZipImport() {
  zipFile.value = null
  zipPreview.value = null
  importError.value = ''
  if (skillFileInput.value) skillFileInput.value.value = ''
}

function openCreatePanel(mode: CreateMode = createMode.value) {
  createMode.value = mode
  showCreatePanel.value = true
  createError.value = ''
  importError.value = ''
}

function closeCreatePanel() {
  if (creatingSkill.value || importingZip.value || importingZipConfirm.value || importingDirectory.value) return
  showCreatePanel.value = false
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
  clearMessages()
  try {
    skills.value = await reloadSkills()
    if (selectedSkillName.value) {
      const stillExists = skills.value.some((skill) => skill.name === selectedSkillName.value)
      if (stillExists) {
        selectedSkill.value = await getSkillDetail(selectedSkillName.value)
        applyEditor(selectedSkill.value)
      } else {
        selectedSkill.value = null
        selectedSkillName.value = ''
      }
    }
  } catch (e: any) {
    skillError.value = e.message || '重新加载 Skill 失败。'
  } finally {
    loadingSkills.value = false
  }
}

async function selectSkill(skill: Skill) {
  if (loadingSkillDetail.value) return
  selectedSkillName.value = skill.name
  loadingSkillDetail.value = true
  clearMessages()

  try {
    const detail = await getSkillDetail(skill.name)
    selectedSkill.value = detail
    applyEditor(detail)
  } catch (e: any) {
    skillError.value = e.message || '加载 Skill 详情失败。'
  } finally {
    loadingSkillDetail.value = false
  }
}

async function saveSelectedSkill() {
  if (!selectedSkill.value || savingSkill.value || selectedSkill.value.protected) return

  let skillJson: Record<string, any>
  try {
    skillJson = parseJsonText(editor.value.skillJsonText, 'skill.json')
  } catch (e: any) {
    setError(e.message, 'skill')
    return
  }

  savingSkill.value = true
  clearMessages()

  try {
    const updated = await updateSkill(selectedSkill.value.name, {
      skill_md: editor.value.skillMd,
      skill_json: skillJson,
    })
    selectedSkill.value = updated
    selectedSkillName.value = updated.name
    applyEditor(updated)
    skills.value = skills.value.map((item) => (
      item.name === updated.name
        ? {
            ...item,
            description: updated.description,
            tool_count: updated.tool_count,
            needs_time_context: updated.needs_time_context,
            has_mcp: updated.has_mcp,
            enabled: updated.enabled,
            degraded: updated.degraded,
            load_errors: updated.load_errors,
          }
        : item
    ))
    savedNotice.value = '已保存并重新加载 Skill。'
  } catch (e: any) {
    skillError.value = e.message || '保存 Skill 失败。'
  } finally {
    savingSkill.value = false
  }
}

async function handleCreateSkill() {
  if (creatingSkill.value) return

  const payload = {
    name: normalizeSkillNameInput(skillForm.value.name),
    description: skillForm.value.description.trim(),
    content: skillForm.value.content.trim(),
    needs_time_context: skillForm.value.needs_time_context,
    skill_json: {} as Record<string, any>,
  }

  if (!payload.name || !payload.description || !payload.content) {
    createError.value = '请填写名称、描述和 SKILL.md 内容。'
    return
  }

  try {
    payload.skill_json = parseJsonText(skillForm.value.skillJsonText, 'skill.json')
  } catch (e: any) {
    setError(e.message, 'create')
    return
  }

  creatingSkill.value = true
  clearMessages()

  try {
    const skill = await createSkill(payload)
    skills.value = [skill, ...skills.value.filter((item) => item.name !== skill.name)]
    resetSkillForm()
    showCreatePanel.value = false
    await selectSkill(skill)
  } catch (e: any) {
    createError.value = e.message || '创建 Skill 失败。'
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
    await loadSkills()
    resetZipImport()
    showCreatePanel.value = false
    await selectSkill(result.skill)
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
    showCreatePanel.value = false
    await selectSkill(result.skill)
  } catch (e: any) {
    importError.value = e.message || '导入 Skill 文件夹失败。'
  } finally {
    importingDirectory.value = false
  }
}

async function toggleSkillEnabled(skill: Skill) {
  if (skill.protected || skillBusyName.value) return

  skillBusyName.value = skill.name
  clearMessages()

  try {
    const updated = await setSkillEnabled(skill.name, !skill.enabled)
    skills.value = skills.value.map((item) => (item.name === updated.name ? updated : item))
    if (selectedSkill.value?.name === updated.name) {
      selectedSkill.value = await getSkillDetail(updated.name)
      applyEditor(selectedSkill.value)
    }
  } catch (e: any) {
    skillError.value = e.message || '更新 Skill 状态失败。'
  } finally {
    skillBusyName.value = ''
  }
}

function requestDeleteSkill(skill: Skill) {
  if (skill.protected || deletingSkillName.value) return
  pendingDeleteSkill.value = skill
}

function closeDeleteDialog() {
  if (deletingSkillName.value) return
  pendingDeleteSkill.value = null
}

async function confirmDeleteSkill() {
  const skill = pendingDeleteSkill.value
  if (!skill || skill.protected || deletingSkillName.value) return

  deletingSkillName.value = skill.name
  clearMessages()

  try {
    await deleteSkill(skill.name)
    pendingDeleteSkill.value = null
    skills.value = skills.value.filter((item) => item.name !== skill.name)
    if (selectedSkillName.value === skill.name) {
      selectedSkill.value = null
      selectedSkillName.value = ''
    }
  } catch (e: any) {
    skillError.value = e.message || '删除 Skill 失败。'
  } finally {
    deletingSkillName.value = ''
  }
}

function copySkillMd() {
  const text = editor.value.skillMd || selectedSkill.value?.skill_md || ''
  if (!text) return
  navigator.clipboard?.writeText(text).catch(() => {})
}

onMounted(async () => {
  await loadSkills()
  if (skills.value.length > 0) {
    await selectSkill(skills.value[0])
  }
})
</script>

<template>
  <div class="skill-layout">
    <aside class="skill-sidebar">
      <div class="skill-sidebar-top">
        <div class="skill-brand">
          <TerminalSquare color="#10B981" :size="24" />
          <span>Nexus OS</span>
        </div>

        <button class="skill-primary-btn" type="button" @click="openCreatePanel('online')">
          <Plus :size="18" />
          <span>新增 Skill</span>
        </button>

        <button class="skill-secondary-btn" type="button" @click="emit('back')">
          <ArrowLeft :size="18" />
          <span>返回聊天</span>
        </button>
      </div>

      <div class="skill-search">
        <Search :size="16" />
        <input v-model="searchText" placeholder="搜索 Skill" />
      </div>

      <div class="skill-list-head">
        <span>{{ filteredSkills.length }} skills</span>
        <button class="skill-icon-btn" type="button" title="重新加载" @click="refreshAllSkills">
          <RefreshCw :class="{ 'skill-spin': loadingSkills }" :size="17" />
        </button>
      </div>

      <div class="skill-list">
        <div v-if="loadingSkills" class="skill-center-loader">
          <Loader2 class="skill-spin" :size="18" />
        </div>

        <button
          v-for="skill in filteredSkills"
          v-else
          :key="skill.name"
          class="skill-row"
          :class="{ active: selectedSkillName === skill.name, disabled: !skill.enabled }"
          type="button"
          @click="selectSkill(skill)"
        >
          <div class="skill-row-top">
            <strong>{{ skill.name }}</strong>
            <span>{{ skill.tool_count }}</span>
          </div>
          <p>{{ skill.description }}</p>
          <div class="skill-row-meta">
            <span v-if="skill.has_mcp">MCP</span>
            <span v-if="skill.needs_time_context">Time</span>
            <span v-if="skill.degraded" class="warn">异常</span>
            <span v-if="!skill.enabled" class="warn">禁用</span>
          </div>
        </button>
      </div>

      <div class="skill-sidebar-bottom">
        <div class="skill-user">
          <div class="skill-avatar">{{ displayName.charAt(0).toUpperCase() }}</div>
          <span>{{ displayName }}</span>
        </div>
        <button class="skill-icon-btn" type="button" title="退出登录" @click="emit('logout')">
          <LogOut :size="18" />
        </button>
      </div>
    </aside>

    <main class="skill-main">
      <div class="skill-grid-bg"></div>

      <div class="skill-topbar">
        <div>
          <div class="skill-kicker">Skill Library</div>
          <h1>技能管理</h1>
        </div>
        <div class="skill-topbar-actions">
          <button class="skill-ghost-btn" type="button" @click="refreshAllSkills">
            <RefreshCw :class="{ 'skill-spin': loadingSkills }" :size="16" />
            <span>重新加载</span>
          </button>
          <button class="skill-dark-btn" type="button" @click="saveSelectedSkill" :disabled="!selectedSkill || !hasEditorChanges || savingSkill || selectedSkill?.protected">
            <Loader2 v-if="savingSkill" class="skill-spin" :size="16" />
            <Save v-else :size="16" />
            <span>{{ savingSkill ? '保存中' : '保存修改' }}</span>
          </button>
        </div>
      </div>

      <div class="skill-content">
        <div v-if="skillError" class="skill-form-error">{{ skillError }}</div>
        <div v-if="savedNotice" class="skill-form-success">{{ savedNotice }}</div>

        <div v-if="loadingSkillDetail" class="skill-center-loader detail">
          <Loader2 class="skill-spin" :size="26" />
        </div>

        <section v-else-if="selectedSkill" class="skill-detail-panel">
          <div class="skill-detail-head">
            <div>
              <div class="skill-kicker">{{ selectedSkill.skill_dir || selectedSkill.skill_path }}</div>
              <h2>{{ selectedSkill.name }}</h2>
              <p>{{ selectedSkill.description }}</p>
            </div>
            <div class="skill-detail-actions">
              <span class="skill-status-pill" :class="{ disabled: !selectedSkill.enabled }">
                {{ selectedSkill.enabled ? '已启用' : '已禁用' }}
              </span>
              <button class="skill-ghost-btn" type="button" :disabled="selectedSkill.protected || !!skillBusyName" @click="toggleSkillEnabled(selectedSkill)">
                <CircleSlash2 v-if="selectedSkill.enabled" :size="15" />
                <Check v-else :size="15" />
                <span>{{ selectedSkill.enabled ? '禁用' : '启用' }}</span>
              </button>
              <button class="skill-ghost-btn danger" type="button" :disabled="selectedSkill.protected || !!deletingSkillName" @click="requestDeleteSkill(selectedSkill)">
                <Loader2 v-if="deletingSkillName === selectedSkill.name" class="skill-spin" :size="15" />
                <Trash2 v-else :size="15" />
                <span>删除</span>
              </button>
            </div>
          </div>

          <div class="skill-stats">
            <div>
              <label>工具</label>
              <strong>{{ selectedSkill.tool_count }}</strong>
            </div>
            <div>
              <label>MCP</label>
              <strong>{{ selectedSkill.has_mcp ? '已配置' : '无' }}</strong>
            </div>
            <div>
              <label>时间上下文</label>
              <strong>{{ selectedSkill.needs_time_context ? '需要' : '不需要' }}</strong>
            </div>
          </div>

          <div v-if="selectedSkill.protected" class="skill-inline-status warn">
            <span>受保护 Skill 只能查看，不能在线修改。</span>
          </div>

          <div class="skill-editor-toolbar">
            <h3>在线编辑</h3>
            <button class="skill-ghost-btn" type="button" @click="copySkillMd">
              <Copy :size="15" />
              <span>复制 MD</span>
            </button>
          </div>

          <div class="skill-editor-grid">
            <label>
              <span>SKILL.md</span>
              <textarea v-model="editor.skillMd" :disabled="selectedSkill.protected" spellcheck="false"></textarea>
            </label>
            <label>
              <span>skill.json</span>
              <textarea v-model="editor.skillJsonText" :disabled="selectedSkill.protected" spellcheck="false"></textarea>
            </label>
          </div>

          <section class="skill-tools-panel">
            <div class="skill-section-head">
              <h3>工具列表</h3>
              <span>{{ currentSkillTools.length }}</span>
            </div>
            <div v-if="currentSkillTools.length === 0" class="skill-empty-panel">
              暂无工具。
            </div>
            <div v-else class="skill-tool-list">
              <div v-for="tool in currentSkillTools" :key="tool.name" class="skill-tool-row">
                <strong>{{ tool.name }}</strong>
                <span>{{ previewText(tool.description, 140) || '暂无描述' }}</span>
              </div>
            </div>
          </section>
        </section>

        <section v-else class="skill-empty-panel large">
          选择一个 Skill 查看详情，或点击左侧新增按钮创建。
        </section>
      </div>
    </main>

    <div v-if="showCreatePanel" class="skill-create-overlay" @click.self="closeCreatePanel">
      <section class="skill-create-panel skill-create-modal" role="dialog" aria-modal="true" aria-labelledby="skill-create-title">
        <div class="skill-section-head">
          <div>
            <div class="skill-kicker">Create</div>
            <h2 id="skill-create-title">新增 Skill</h2>
          </div>
          <div class="skill-panel-actions">
            <div class="skill-mode-switch">
              <button type="button" :class="{ active: createMode === 'online' }" @click="createMode = 'online'">
                <FileJson :size="15" />
                <span>在线输入</span>
              </button>
              <button type="button" :class="{ active: createMode === 'zip' }" @click="createMode = 'zip'">
                <Upload :size="15" />
                <span>zip</span>
              </button>
            </div>
            <button class="skill-icon-btn light" type="button" title="关闭" @click="closeCreatePanel">
              <X :size="17" />
            </button>
          </div>
        </div>

        <form v-if="createMode === 'online'" class="skill-create-form" @submit.prevent="handleCreateSkill">
          <div class="skill-form-grid">
            <label>
              <span>名称</span>
              <input v-model="skillForm.name" autocomplete="off" placeholder="product-support" />
            </label>
            <label>
              <span>描述</span>
              <input v-model="skillForm.description" autocomplete="off" placeholder="处理产品支持类问题" />
            </label>
          </div>
          <label class="skill-check-row">
            <input v-model="skillForm.needs_time_context" type="checkbox" />
            <span>需要当前时间上下文</span>
          </label>
          <div class="skill-editor-grid create">
            <label>
              <span>SKILL.md</span>
              <textarea v-model="skillForm.content" spellcheck="false" placeholder="# Purpose&#10;描述这个 Skill 应该做什么。"></textarea>
            </label>
            <label>
              <span>skill.json</span>
              <small>常用字段：enabled、can_be_main、needs_time_context、is_workflow、mcp_servers、mcp_tool_allowlist</small>
              <textarea v-model="skillForm.skillJsonText" spellcheck="false"></textarea>
            </label>
          </div>
          <div v-if="createError" class="skill-form-error">{{ createError }}</div>
          <button class="skill-dark-btn wide" type="submit" :disabled="creatingSkill">
            <Loader2 v-if="creatingSkill" class="skill-spin" :size="17" />
            <Save v-else :size="17" />
            <span>创建 Skill</span>
          </button>
        </form>

        <div v-else class="skill-import-panel">
          <div class="skill-import-grid">
            <label class="skill-upload-box">
              <input ref="skillFileInput" type="file" accept=".zip" @change="handleZipFileChange" />
              <Upload :size="20" />
              <span>上传 .zip Skill 包</span>
              <small v-if="zipFile">{{ zipFile.name }}</small>
            </label>

            <div class="skill-import-form">
              <label>
                <span>skills/file 下的文件夹</span>
                <input v-model="importForm.source" placeholder="my_skill" autocomplete="off" />
              </label>
              <button class="skill-ghost-btn" type="button" :disabled="importingDirectory" @click="handleDirectoryImport">
                <Loader2 v-if="importingDirectory" class="skill-spin" :size="16" />
                <FolderOpen v-else :size="16" />
                <span>导入文件夹</span>
              </button>
            </div>
          </div>

          <div v-if="zipPreview" class="skill-preview-card">
            <div>
              <strong>{{ zipPreview.name }}</strong>
              <p>{{ zipPreview.description }}</p>
            </div>
            <span>{{ zipPreview.tool_count }} tools</span>
            <button class="skill-dark-btn" type="button" :disabled="importingZipConfirm" @click="confirmZipImport">
              <Loader2 v-if="importingZipConfirm" class="skill-spin" :size="16" />
              <Save v-else :size="16" />
              <span>确认导入</span>
            </button>
          </div>

          <div v-if="importingZip" class="skill-inline-status">
            <Loader2 class="skill-spin" :size="16" />
            <span>正在解析 zip 包...</span>
          </div>
          <div v-if="importError" class="skill-form-error">{{ importError }}</div>
        </div>
      </section>
    </div>

    <div v-if="pendingDeleteSkill" class="skill-delete-overlay" @click.self="closeDeleteDialog">
      <section class="skill-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="skill-delete-title">
        <div class="skill-delete-icon">
          <Trash2 :size="22" />
        </div>
        <div class="skill-delete-copy">
          <p class="skill-kicker">Delete skill</p>
          <h3 id="skill-delete-title">删除这个 Skill？</h3>
          <p>会从 Skill 库中移除目录和配置，重新加载后路由不会再选择它。</p>
          <div class="skill-delete-preview">
            <label>{{ pendingDeleteSkill.name }}</label>
            <strong>{{ pendingDeleteSkill.description }}</strong>
          </div>
        </div>
        <div class="skill-delete-actions">
          <button class="skill-delete-cancel" type="button" :disabled="!!deletingSkillName" @click="closeDeleteDialog">
            取消
          </button>
          <button class="skill-delete-confirm" type="button" :disabled="!!deletingSkillName" @click="confirmDeleteSkill">
            <Loader2 v-if="deletingSkillName" class="skill-spin" :size="16" />
            <Trash2 v-else :size="16" />
            <span>{{ deletingSkillName ? '删除中' : '删除 Skill' }}</span>
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@600;700&display=swap');

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

.skill-layout {
  width: 100vw;
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: #ffffff;
  color: #0f172a;
  font-family: 'Inter', -apple-system, sans-serif;
}

.skill-sidebar {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #0b1120;
  color: #f8fafc;
  border-right: 1px solid #1e293b;
}

.skill-sidebar-top {
  padding: 20px;
}

.skill-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 20px;
  font-weight: 700;
}

.skill-primary-btn,
.skill-secondary-btn,
.skill-dark-btn,
.skill-ghost-btn,
.skill-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 8px;
  font-weight: 700;
  cursor: pointer;
}

.skill-primary-btn,
.skill-secondary-btn {
  width: 100%;
  min-height: 42px;
  border: 1px solid transparent;
  font-size: 14px;
}

.skill-primary-btn {
  background: #10b981;
  color: #ffffff;
}

.skill-secondary-btn {
  margin-top: 10px;
  background: transparent;
  color: #cbd5e1;
  border-color: #334155;
}

.skill-search {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 0 20px 14px;
  padding: 0 11px;
  height: 38px;
  border: 1px solid #243244;
  border-radius: 8px;
  color: #64748b;
  background: rgba(15, 23, 42, 0.58);
}

.skill-search input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: none;
  background: transparent;
  color: #f8fafc;
}

.skill-list-head,
.skill-row-top,
.skill-sidebar-bottom,
.skill-topbar,
.skill-topbar-actions,
.skill-section-head,
.skill-panel-actions,
.skill-detail-head,
.skill-detail-actions,
.skill-editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.skill-list-head {
  padding: 0 20px 10px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.skill-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 12px 16px;
}

.skill-row {
  width: 100%;
  margin-bottom: 8px;
  padding: 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #cbd5e1;
  text-align: left;
  cursor: pointer;
}

.skill-row:hover {
  background: #1e293b;
  color: #ffffff;
}

.skill-row.active {
  border-color: rgba(16, 185, 129, 0.34);
  background: rgba(16, 185, 129, 0.15);
  color: #5eead4;
}

.skill-row.disabled {
  opacity: 0.68;
}

.skill-row-top span {
  flex-shrink: 0;
  min-width: 26px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.14);
  color: #5eead4;
  font-size: 12px;
  font-weight: 800;
  text-align: center;
}

.skill-row p {
  margin: 8px 0;
  color: #cbd5e1;
  font-size: 13px;
  line-height: 1.45;
}

.skill-row-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.skill-row-meta span,
.skill-status-pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.skill-row-meta .warn,
.skill-inline-status.warn {
  background: #fef3c7;
  color: #92400e;
}

.skill-sidebar-bottom {
  padding: 16px 20px;
  border-top: 1px solid #1e293b;
}

.skill-user {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.skill-user span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skill-avatar {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #10b981;
  color: #ffffff;
  font-weight: 800;
}

.skill-main {
  position: relative;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  background: #ffffff;
}

.skill-grid-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-image:
    linear-gradient(to right, #f1f5f9 1px, transparent 1px),
    linear-gradient(to bottom, #f1f5f9 1px, transparent 1px);
  background-size: 32px 32px;
}

.skill-topbar {
  position: relative;
  z-index: 1;
  height: 70px;
  padding: 0 24px;
  border-bottom: 1px solid #e2e8f0;
  background: #ffffff;
}

.skill-topbar h1,
.skill-detail-head h2,
.skill-create-panel h2 {
  margin: 2px 0 0;
  font-size: 24px;
  line-height: 1.2;
}

.skill-kicker {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.skill-content {
  position: relative;
  z-index: 1;
  height: calc(100vh - 70px);
  overflow-y: auto;
  padding: 24px;
}

.skill-create-panel,
.skill-detail-panel,
.skill-tools-panel {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
}

.skill-create-panel {
  margin-bottom: 16px;
  padding: 18px;
}

.skill-mode-switch {
  display: inline-flex;
  padding: 3px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.skill-mode-switch button {
  height: 30px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 11px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}

.skill-mode-switch button.active {
  background: #0f172a;
  color: #ffffff;
}

.skill-create-form,
.skill-import-panel {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.skill-form-grid,
.skill-import-grid,
.skill-editor-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.skill-create-form label,
.skill-import-form label,
.skill-editor-grid label {
  display: grid;
  gap: 7px;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
}

.skill-create-form input,
.skill-import-form input,
.skill-editor-grid textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #0f172a;
  font: inherit;
  outline: none;
}

.skill-create-form input,
.skill-import-form input {
  height: 40px;
  padding: 0 12px;
}

.skill-editor-grid textarea {
  min-height: 420px;
  padding: 12px;
  resize: vertical;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.55;
}

.skill-editor-grid.create textarea {
  min-height: 260px;
}

.skill-check-row {
  display: flex !important;
  grid-template-columns: none !important;
  flex-direction: row;
  align-items: center;
  gap: 9px !important;
}

.skill-check-row input {
  width: 16px;
  height: 16px;
  accent-color: #0f766e;
}

.skill-upload-box {
  position: relative;
  min-height: 128px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  text-align: center;
  cursor: pointer;
}

.skill-upload-box input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.skill-import-form {
  display: grid;
  gap: 10px;
}

.skill-preview-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.skill-preview-card p {
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
}

.skill-detail-panel {
  padding: 18px;
}

.skill-detail-head {
  align-items: flex-start;
}

.skill-detail-head p {
  margin-top: 6px;
  color: #64748b;
  line-height: 1.55;
}

.skill-detail-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.skill-status-pill.disabled {
  background: #fef3c7;
  color: #92400e;
}

.skill-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 18px 0;
}

.skill-stats > div {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.skill-stats label {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.skill-stats strong {
  display: block;
  margin-top: 4px;
  font-size: 18px;
}

.skill-editor-toolbar {
  margin: 16px 0 10px;
}

.skill-tools-panel {
  margin-top: 16px;
  padding: 16px;
}

.skill-tool-list {
  display: grid;
  gap: 9px;
  margin-top: 12px;
}

.skill-tool-row {
  padding: 11px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.skill-tool-row strong {
  display: block;
  margin-bottom: 4px;
}

.skill-tool-row span {
  color: #64748b;
  font-size: 13px;
  line-height: 1.45;
}

.skill-dark-btn,
.skill-ghost-btn {
  min-height: 36px;
  padding: 0 13px;
  border: 1px solid #e2e8f0;
  font-size: 13px;
}

.skill-dark-btn {
  border-color: #0f172a;
  background: #0f172a;
  color: #ffffff;
}

.skill-dark-btn.wide {
  width: max-content;
}

.skill-ghost-btn {
  background: #ffffff;
  color: #334155;
}

.skill-ghost-btn:hover {
  border-color: #10b981;
  color: #047857;
  background: #ecfdf5;
}

.skill-ghost-btn.danger {
  border-color: #fecaca;
  background: #fff7f7;
  color: #b91c1c;
}

.skill-icon-btn {
  width: 32px;
  height: 32px;
  border: 1px solid transparent;
  background: transparent;
  color: #94a3b8;
}

.skill-icon-btn.light {
  border-color: #e2e8f0;
  color: #64748b;
  background: #ffffff;
}

.skill-icon-btn:hover {
  color: #10b981;
}

.skill-dark-btn:disabled,
.skill-ghost-btn:disabled,
.skill-icon-btn:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.skill-form-error,
.skill-form-success,
.skill-inline-status,
.skill-empty-panel {
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
}

.skill-form-error {
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.skill-form-success {
  margin-bottom: 12px;
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
  color: #047857;
}

.skill-inline-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475569;
}

.skill-empty-panel {
  border: 1px dashed #cbd5e1;
  background: #ffffff;
  color: #64748b;
}

.skill-empty-panel.large {
  min-height: calc(100vh - 150px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.skill-delete-overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.48);
  backdrop-filter: blur(3px);
}

.skill-create-overlay {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.48);
  backdrop-filter: blur(3px);
}

.skill-create-modal {
  width: min(980px, calc(100vw - 32px));
  max-height: min(88vh, 920px);
  overflow: auto;
  padding: 18px;
}

.skill-delete-dialog {
  width: min(460px, calc(100vw - 32px));
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 14px;
  padding: 18px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.24);
}

.skill-delete-icon {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #fef2f2;
  color: #dc2626;
}

.skill-delete-copy {
  min-width: 0;
}

.skill-delete-copy .skill-kicker {
  color: #dc2626;
}

.skill-delete-copy h3 {
  margin: 2px 0 6px;
  color: #0f172a;
  font-size: 20px;
  line-height: 1.25;
}

.skill-delete-copy p:not(.skill-kicker) {
  margin: 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.55;
}

.skill-delete-preview {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.skill-delete-preview label {
  display: block;
  margin-bottom: 6px;
  color: #b91c1c;
  font-size: 12px;
  font-weight: 800;
}

.skill-delete-preview strong {
  display: block;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.skill-delete-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.skill-delete-cancel,
.skill-delete-confirm {
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.skill-delete-cancel {
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #334155;
}

.skill-delete-confirm {
  border: 1px solid #dc2626;
  background: #dc2626;
  color: #ffffff;
}

.skill-delete-confirm:hover {
  border-color: #b91c1c;
  background: #b91c1c;
}

.skill-delete-cancel:disabled,
.skill-delete-confirm:disabled {
  cursor: progress;
  opacity: 0.72;
}

.skill-center-loader {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.skill-center-loader.detail {
  min-height: calc(100vh - 150px);
}

.skill-spin {
  animation: skill-spin 0.8s linear infinite;
}

@keyframes skill-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1100px) {
  .skill-sidebar {
    width: 290px;
  }

  .skill-form-grid,
  .skill-import-grid,
  .skill-editor-grid,
  .skill-stats {
    grid-template-columns: 1fr;
  }

  .skill-detail-head {
    flex-direction: column;
  }
}

@media (max-width: 760px) {
  .skill-layout {
    flex-direction: column;
    height: auto;
    min-height: 100vh;
    overflow: auto;
  }

  .skill-sidebar {
    width: 100%;
    max-height: 48vh;
  }

  .skill-main,
  .skill-content {
    height: auto;
    overflow: visible;
  }

  .skill-topbar {
    height: auto;
    align-items: flex-start;
    flex-direction: column;
    padding: 16px;
  }

  .skill-topbar-actions,
  .skill-panel-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .skill-content {
    padding: 16px;
  }
}
</style>
