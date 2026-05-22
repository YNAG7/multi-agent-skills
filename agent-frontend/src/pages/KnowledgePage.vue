<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  ArrowLeft,
  BarChart3,
  Database,
  FileText,
  FolderSync,
  Loader2,
  LogOut,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
  Upload,
  X,
} from 'lucide-vue-next'
import {
  deleteKnowledgeDocument,
  evaluateKnowledge,
  getKnowledgeDocuments,
  reindexKnowledgeDocument,
  syncKnowledgeDirectory,
  uploadKnowledgeFile,
} from '../api/knowledge'
import type { User } from '../types/auth'
import type { KnowledgeDocument, KnowledgeEvalResult, KnowledgeSyncStats } from '../types/knowledge'

const props = defineProps<{
  user: User
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'logout'): void
}>()

const documents = ref<KnowledgeDocument[]>([])
const selectedId = ref<number | null>(null)
const searchText = ref('')
const loading = ref(false)
const uploading = ref(false)
const syncing = ref(false)
const evaluating = ref(false)
const busyDocumentId = ref<number | null>(null)
const error = ref('')
const evalError = ref('')
const notice = ref('')
const syncStats = ref<KnowledgeSyncStats | null>(null)
const evalResult = ref<KnowledgeEvalResult | null>(null)
const evalJsonl = ref('{"question":"如何维护机器人？","reference":"机器人维护应包括定期清洁、检查电源和传感器、更新软件、记录异常。"}\n{"question":"客户服务 skill 适合处理什么问题？","reference":"客户服务 skill 适合处理售后咨询、投诉处理、服务流程说明等客户相关问题。"}')
const evalSync = ref(false)
const showEvalDialog = ref(false)
// Keep the active sample here so the user can inspect retrieved chunks in a second modal.
const contextPreview = ref<{ sample: KnowledgeEvalResult['samples'][number]; index: number } | null>(null)
const uploadFileInput = ref<HTMLInputElement | null>(null)
const pendingDelete = ref<KnowledgeDocument | null>(null)

const displayName = computed(() => props.user.nickname || props.user.username)

const filteredDocuments = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return documents.value

  return documents.value.filter((document) => (
    document.filename.toLowerCase().includes(keyword) ||
    document.path.toLowerCase().includes(keyword) ||
    document.status.toLowerCase().includes(keyword)
  ))
})

const selectedDocument = computed(() => {
  if (selectedId.value === null) return filteredDocuments.value[0] || null
  return documents.value.find((document) => document.id === selectedId.value) || filteredDocuments.value[0] || null
})

const totalChunks = computed(() => documents.value.reduce((sum, document) => sum + document.chunk_count, 0))
const indexedCount = computed(() => documents.value.filter((document) => document.status === 'indexed').length)
const failedCount = computed(() => documents.value.filter((document) => document.status === 'failed').length)

function formatTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 19).replace('T', ' ')
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatBytes(value?: number | null) {
  const size = value || 0
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function statusText(status: string) {
  const map: Record<string, string> = {
    indexed: '已索引',
    indexing: '索引中',
    pending: '待处理',
    failed: '失败',
  }
  return map[status] || status
}

function statusClass(status: string) {
  if (status === 'indexed') return 'ok'
  if (status === 'failed') return 'bad'
  return 'pending'
}

function shortHash(value?: string | null) {
  return value ? value.slice(0, 12) : '-'
}

function clearMessages() {
  error.value = ''
  notice.value = ''
}

function formatMetric(value: number) {
  if (!Number.isFinite(value)) return '-'
  return value.toFixed(3)
}

function openEvalDialog() {
  showEvalDialog.value = true
  evalError.value = ''
}

function closeEvalDialog() {
  if (evaluating.value) return
  showEvalDialog.value = false
}

function openContextPreview(sample: KnowledgeEvalResult['samples'][number], index: number) {
  contextPreview.value = { sample, index }
}

async function loadDocuments() {
  loading.value = true
  clearMessages()
  try {
    documents.value = await getKnowledgeDocuments()
    if (selectedId.value && !documents.value.some((document) => document.id === selectedId.value)) {
      selectedId.value = null
    }
  } catch (e: any) {
    error.value = e.message || '知识库列表加载失败。'
  } finally {
    loading.value = false
  }
}

function selectDocument(document: KnowledgeDocument) {
  selectedId.value = document.id
}

async function handleUploadChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || uploading.value) return

  uploading.value = true
  clearMessages()
  try {
    const document = await uploadKnowledgeFile(file)
    documents.value = [document, ...documents.value.filter((item) => item.id !== document.id)]
    selectedId.value = document.id
    notice.value = `已上传并索引 ${document.filename}。`
  } catch (e: any) {
    error.value = e.message || '上传知识库文件失败。'
  } finally {
    uploading.value = false
    if (uploadFileInput.value) uploadFileInput.value.value = ''
  }
}

async function handleSync() {
  if (syncing.value) return

  syncing.value = true
  clearMessages()
  try {
    syncStats.value = await syncKnowledgeDirectory()
    await loadDocuments()
    notice.value = '已同步 data/ 目录。'
  } catch (e: any) {
    error.value = e.message || '同步 data/ 目录失败。'
  } finally {
    syncing.value = false
  }
}

async function handleEvaluate() {
  if (evaluating.value) return

  evaluating.value = true
  evalError.value = ''
  // Refresh the same report in place so the modal stays the single source of truth.
  try {
    evalResult.value = await evaluateKnowledge(evalJsonl.value, evalSync.value)
  } catch (e: any) {
    evalError.value = e.message || 'RAG 测评失败。'
  } finally {
    evaluating.value = false
  }
}

async function handleReindex(document: KnowledgeDocument) {
  if (busyDocumentId.value) return

  busyDocumentId.value = document.id
  clearMessages()
  try {
    const updated = await reindexKnowledgeDocument(document.id)
    documents.value = documents.value.map((item) => item.id === updated.id ? updated : item)
    selectedId.value = updated.id
    notice.value = `已重建 ${updated.filename}。`
  } catch (e: any) {
    error.value = e.message || '重建索引失败。'
  } finally {
    busyDocumentId.value = null
  }
}

function requestDelete(document: KnowledgeDocument) {
  pendingDelete.value = document
}

async function confirmDelete() {
  if (!pendingDelete.value || busyDocumentId.value) return

  const target = pendingDelete.value
  busyDocumentId.value = target.id
  clearMessages()
  try {
    await deleteKnowledgeDocument(target.id)
    documents.value = documents.value.filter((document) => document.id !== target.id)
    if (selectedId.value === target.id) selectedId.value = null
    pendingDelete.value = null
    notice.value = `已删除 ${target.filename}。`
  } catch (e: any) {
    error.value = e.message || '删除知识库文件失败。'
  } finally {
    busyDocumentId.value = null
  }
}

onMounted(loadDocuments)
</script>

<template>
  <div class="knowledge-layout">
    <aside class="knowledge-sidebar">
      <div class="knowledge-brand">
        <button class="knowledge-icon-btn" title="返回聊天" @click="emit('back')">
          <ArrowLeft :size="17" />
        </button>
        <div>
          <strong>Knowledge</strong>
          <span>RAG 文件索引</span>
        </div>
      </div>

      <button class="knowledge-upload-btn" :disabled="uploading">
        <Upload :size="17" />
        <span>{{ uploading ? '上传中' : '上传文件' }}</span>
        <input
          ref="uploadFileInput"
          type="file"
          accept=".txt,.pdf"
          :disabled="uploading"
          @change="handleUploadChange"
        >
      </button>

      <button class="knowledge-side-btn" :disabled="syncing" @click="handleSync">
        <FolderSync :size="17" :class="{ 'knowledge-spin': syncing }" />
        <span>同步 data/</span>
      </button>

      <div class="knowledge-search">
        <Search :size="16" />
        <input v-model="searchText" placeholder="搜索文件、路径、状态">
      </div>

      <div class="knowledge-list">
        <button
          v-for="document in filteredDocuments"
          :key="document.id"
          class="knowledge-row"
          :class="{ active: selectedDocument?.id === document.id }"
          @click="selectDocument(document)"
        >
          <span class="knowledge-row-icon"><FileText :size="17" /></span>
          <span class="knowledge-row-main">
            <strong>{{ document.filename }}</strong>
            <small>{{ document.path }}</small>
          </span>
          <span class="knowledge-status" :class="statusClass(document.status)">
            {{ statusText(document.status) }}
          </span>
        </button>

        <div v-if="!loading && filteredDocuments.length === 0" class="knowledge-empty">
          暂无知识库文件
        </div>
      </div>

      <div class="knowledge-user">
        <div>
          <span>{{ displayName }}</span>
          <small>{{ props.user.is_admin ? 'admin' : 'user' }}</small>
        </div>
        <button class="knowledge-icon-btn" title="退出登录" @click="emit('logout')">
          <LogOut :size="17" />
        </button>
      </div>
    </aside>

    <main class="knowledge-main">
      <header class="knowledge-topbar">
        <div>
          <p>RAG Knowledge Base</p>
          <h1>知识库文件</h1>
        </div>
        <div class="knowledge-actions">
          <button class="knowledge-ghost-btn" type="button" @click="openEvalDialog">
            <BarChart3 :size="16" />
            RAG 测评
          </button>
          <button class="knowledge-ghost-btn" :disabled="loading" @click="loadDocuments">
            <RefreshCw :size="16" :class="{ 'knowledge-spin': loading }" />
            刷新
          </button>
        </div>
      </header>

      <section class="knowledge-content">
        <div class="knowledge-stats">
          <div>
            <label>文件</label>
            <strong>{{ documents.length }}</strong>
          </div>
          <div>
            <label>已索引</label>
            <strong>{{ indexedCount }}</strong>
          </div>
          <div>
            <label>Chunk</label>
            <strong>{{ totalChunks }}</strong>
          </div>
          <div>
            <label>失败</label>
            <strong>{{ failedCount }}</strong>
          </div>
        </div>

        <div v-if="error" class="knowledge-message error">{{ error }}</div>
        <div v-if="notice" class="knowledge-message success">{{ notice }}</div>
        <div v-if="syncStats" class="knowledge-message">
          扫描 {{ syncStats.scanned }}，新增/更新 {{ syncStats.indexed }}，跳过 {{ syncStats.skipped }}，删除 {{ syncStats.deleted }}，失败 {{ syncStats.failed }}
        </div>

        <div v-if="loading" class="knowledge-loader">
          <Loader2 :size="18" class="knowledge-spin" />
          正在加载知识库
        </div>

        <div v-else-if="selectedDocument" class="knowledge-detail">
          <div class="knowledge-detail-head">
            <div>
              <span class="knowledge-kicker">{{ selectedDocument.source }}</span>
              <h2>{{ selectedDocument.filename }}</h2>
              <p>{{ selectedDocument.path }}</p>
            </div>
            <div class="knowledge-detail-actions">
              <button
                class="knowledge-ghost-btn"
                :disabled="Boolean(busyDocumentId)"
                @click="handleReindex(selectedDocument)"
              >
                <RotateCcw :size="16" :class="{ 'knowledge-spin': busyDocumentId === selectedDocument.id }" />
                重建
              </button>
              <button
                class="knowledge-ghost-btn danger"
                :disabled="Boolean(busyDocumentId)"
                @click="requestDelete(selectedDocument)"
              >
                <Trash2 :size="16" />
                删除
              </button>
            </div>
          </div>

          <div class="knowledge-meta-grid">
            <div>
              <label>状态</label>
              <strong>
                <span class="knowledge-status" :class="statusClass(selectedDocument.status)">
                  {{ statusText(selectedDocument.status) }}
                </span>
              </strong>
            </div>
            <div>
              <label>文件大小</label>
              <strong>{{ formatBytes(selectedDocument.size_bytes) }}</strong>
            </div>
            <div>
              <label>Chunk 数</label>
              <strong>{{ selectedDocument.chunk_count }}</strong>
            </div>
            <div>
              <label>SHA-256</label>
              <strong>{{ shortHash(selectedDocument.content_hash) }}</strong>
            </div>
            <div>
              <label>索引时间</label>
              <strong>{{ formatTime(selectedDocument.indexed_at) }}</strong>
            </div>
            <div>
              <label>更新时间</label>
              <strong>{{ formatTime(selectedDocument.updated_at) }}</strong>
            </div>
          </div>

          <div v-if="selectedDocument.error" class="knowledge-error-block">
            <label>错误</label>
            <pre>{{ selectedDocument.error }}</pre>
          </div>
        </div>

        <div v-else class="knowledge-empty large">
          <Database :size="34" />
          <strong>还没有知识库文件</strong>
          <span>上传 txt/pdf，或同步 data/ 目录后会显示在这里。</span>
        </div>

      </section>
    </main>

    <div
      v-if="showEvalDialog"
      class="knowledge-eval-overlay"
      @click.self="closeEvalDialog"
    >
      <section class="knowledge-eval-dialog">
        <button class="knowledge-delete-close" :disabled="evaluating" @click="closeEvalDialog">
          <X :size="17" />
        </button>
        <div class="knowledge-detail-head">
          <div>
            <span class="knowledge-kicker">RAGAS</span>
            <h2>RAG 测评</h2>
            <p>每行一个 JSON，字段为 question/reference。一次最多 20 条。</p>
          </div>
          <div class="knowledge-detail-actions">
            <label class="knowledge-eval-check">
              <input v-model="evalSync" type="checkbox">
              先同步 data/
            </label>
            <button class="knowledge-ghost-btn" :disabled="evaluating" @click="handleEvaluate">
              <Loader2 v-if="evaluating" :size="16" class="knowledge-spin" />
              <RefreshCw v-else :size="16" />
              开始测评
            </button>
          </div>
        </div>

        <textarea
          v-model="evalJsonl"
          class="knowledge-eval-input"
          spellcheck="false"
        ></textarea>

        <div v-if="evalError" class="knowledge-message error">{{ evalError }}</div>

        <div v-if="evalResult" class="knowledge-eval-result">
          <div class="knowledge-eval-metrics">
            <div v-for="(value, key) in evalResult.averages" :key="key">
              <label>{{ key }}</label>
              <strong>{{ formatMetric(value) }}</strong>
            </div>
          </div>

          <div class="knowledge-eval-samples">
            <article
              v-for="(sample, index) in evalResult.samples"
              :key="`${sample.user_input}-${index}`"
              class="knowledge-eval-sample"
            >
              <div>
                <label>问题</label>
                <strong>{{ sample.user_input }}</strong>
              </div>
              <div>
                <label>回答</label>
                <p>{{ sample.response }}</p>
              </div>
              <div>
                <label>标准答案</label>
                <p>{{ sample.reference }}</p>
              </div>
              <button
                class="knowledge-context-link"
                type="button"
                @click="openContextPreview(sample, index)"
              >
                召回上下文 {{ sample.retrieved_contexts.length }} 条
              </button>
            </article>
          </div>
        </div>
      </section>
    </div>

    <div
      v-if="pendingDelete"
      class="knowledge-delete-overlay"
      @click.self="pendingDelete = null"
    >
      <section class="knowledge-delete-dialog">
        <button
          class="knowledge-delete-close"
          :disabled="busyDocumentId === pendingDelete.id"
          @click="pendingDelete = null"
        >
          <X :size="17" />
        </button>
        <div class="knowledge-delete-icon">
          <Trash2 :size="20" />
        </div>
        <div class="knowledge-delete-copy">
          <p class="knowledge-kicker">删除知识库文件</p>
          <h3>删除这份资料？</h3>
          <p>会同时删除数据库记录、chunk 和向量记录；上传文件本体也会从 data/uploads 删除。</p>
          <div class="knowledge-delete-preview">
            <label>文件</label>
            <strong>{{ pendingDelete.filename }}</strong>
            <span>{{ pendingDelete.path }}</span>
          </div>
        </div>
        <div class="knowledge-delete-actions">
          <button
            class="knowledge-delete-cancel"
            :disabled="busyDocumentId === pendingDelete.id"
            @click="pendingDelete = null"
          >
            取消
          </button>
          <button
            class="knowledge-delete-confirm"
            :disabled="busyDocumentId === pendingDelete.id"
            @click="confirmDelete"
          >
            <Loader2 v-if="busyDocumentId === pendingDelete.id" :size="16" class="knowledge-spin" />
            <Trash2 v-else :size="16" />
            删除
          </button>
        </div>
      </section>
    </div>

    <div
      v-if="contextPreview"
      class="knowledge-context-overlay"
      @click.self="contextPreview = null"
    >
      <section class="knowledge-context-dialog">
        <button class="knowledge-delete-close" @click="contextPreview = null">
          <X :size="17" />
        </button>
        <div class="knowledge-detail-head">
          <div>
            <span class="knowledge-kicker">召回上下文</span>
            <h3>第 {{ contextPreview.index + 1 }} 条样本</h3>
            <p>{{ contextPreview.sample.user_input }}</p>
          </div>
        </div>

        <div v-if="contextPreview.sample.retrieved_contexts.length" class="knowledge-context-list">
          <article
            v-for="(context, index) in contextPreview.sample.retrieved_contexts"
            :key="`${context}-${index}`"
            class="knowledge-context-item"
          >
            <label>片段 {{ index + 1 }}</label>
            <pre>{{ context }}</pre>
          </article>
        </div>
        <div v-else class="knowledge-empty">
          没有召回到上下文。
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.knowledge-layout {
  width: 100vw;
  height: 100vh;
  display: flex;
  overflow: hidden;
  color: #0f172a;
  background: #f8fafc;
}

.knowledge-sidebar {
  width: 330px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: #0f172a;
  color: #e2e8f0;
}

.knowledge-brand,
.knowledge-user,
.knowledge-detail-head,
.knowledge-actions,
.knowledge-detail-actions,
.knowledge-delete-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.knowledge-brand {
  margin-bottom: 16px;
}

.knowledge-brand strong {
  display: block;
  color: #ffffff;
  font-size: 18px;
}

.knowledge-brand span,
.knowledge-user small,
.knowledge-row small {
  display: block;
  color: #94a3b8;
  font-size: 12px;
}

.knowledge-icon-btn,
.knowledge-upload-btn,
.knowledge-side-btn,
.knowledge-ghost-btn,
.knowledge-row,
.knowledge-delete-close,
.knowledge-delete-cancel,
.knowledge-delete-confirm {
  border-radius: 8px;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.knowledge-icon-btn {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #334155;
  background: transparent;
  color: #cbd5e1;
}

.knowledge-upload-btn {
  position: relative;
  width: 100%;
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 0;
  background: #10b981;
  color: #ffffff;
  font-weight: 700;
  overflow: hidden;
}

.knowledge-upload-btn input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.knowledge-side-btn {
  width: 100%;
  min-height: 40px;
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid #334155;
  background: transparent;
  color: #cbd5e1;
  font-weight: 650;
}

.knowledge-search {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  margin: 16px 0 12px;
  padding: 0 10px;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #94a3b8;
  background: rgba(15, 23, 42, 0.52);
}

.knowledge-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #ffffff;
}

.knowledge-list {
  flex: 1;
  overflow-y: auto;
}

.knowledge-row {
  width: 100%;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  padding: 10px;
  border: 1px solid transparent;
  background: transparent;
  color: #e2e8f0;
  text-align: left;
}

.knowledge-row:hover,
.knowledge-row.active {
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.14);
}

.knowledge-row-main {
  min-width: 0;
}

.knowledge-row-main strong,
.knowledge-row-main small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.knowledge-row-icon {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.7);
  color: #34d399;
}

.knowledge-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}

.knowledge-status.ok {
  background: #dcfce7;
  color: #15803d;
}

.knowledge-status.bad {
  background: #fee2e2;
  color: #b91c1c;
}

.knowledge-status.pending {
  background: #fef3c7;
  color: #92400e;
}

.knowledge-user {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #334155;
}

.knowledge-user span {
  display: block;
  color: #ffffff;
  font-weight: 700;
}

.knowledge-main {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.knowledge-topbar {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 24px;
  border-bottom: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.92);
}

.knowledge-topbar p,
.knowledge-kicker {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.knowledge-topbar h1,
.knowledge-detail h2,
.knowledge-delete-copy h3 {
  margin: 0;
  color: #0f172a;
  line-height: 1.2;
}

.knowledge-topbar h1 {
  font-size: 22px;
}

.knowledge-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.knowledge-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.knowledge-stats > div,
.knowledge-detail,
.knowledge-eval-dialog,
.knowledge-eval-metrics > div,
.knowledge-eval-sample,
.knowledge-meta-grid > div,
.knowledge-error-block,
.knowledge-empty,
.knowledge-context-dialog {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.knowledge-stats > div {
  padding: 14px;
}

.knowledge-stats label,
.knowledge-meta-grid label,
.knowledge-error-block label,
.knowledge-delete-preview label {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.knowledge-stats strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
}

.knowledge-message {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #475569;
}

.knowledge-message.error {
  border-color: #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.knowledge-message.success {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #15803d;
}

.knowledge-loader {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  color: #64748b;
}

.knowledge-detail {
  padding: 18px;
}

.knowledge-eval-dialog {
  position: relative;
  width: min(1080px, calc(100vw - 32px));
  max-height: min(88vh, 980px);
  margin: 20px;
  padding: 18px;
  overflow-y: auto;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.22);
}

.knowledge-eval-dialog > .knowledge-detail-head,
.knowledge-context-dialog > .knowledge-detail-head {
  padding-right: 44px;
}

.knowledge-eval-dialog .knowledge-detail-actions {
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.knowledge-eval-dialog .knowledge-eval-check,
.knowledge-eval-dialog .knowledge-ghost-btn,
.knowledge-eval-dialog > .knowledge-delete-close {
  height: 36px;
  min-height: 36px;
  box-sizing: border-box;
}

.knowledge-eval-dialog > .knowledge-delete-close {
  top: 18px;
  width: 36px;
  line-height: 1;
}

.knowledge-eval-dialog .knowledge-eval-check {
  line-height: 1;
}

.knowledge-eval-dialog .knowledge-ghost-btn {
  line-height: 1;
}

.knowledge-detail-head {
  align-items: flex-start;
}

.knowledge-detail-head p {
  margin: 6px 0 0;
  color: #64748b;
  word-break: break-all;
}

.knowledge-eval-check {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #475569;
  font-weight: 700;
  white-space: nowrap;
}

.knowledge-eval-check input {
  width: 16px;
  height: 16px;
  accent-color: #10b981;
}

.knowledge-eval-input {
  width: 100%;
  min-height: 140px;
  margin: 16px 0 12px;
  padding: 12px;
  resize: vertical;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  font-size: 13px;
  line-height: 1.55;
}

.knowledge-eval-result {
  display: grid;
  gap: 14px;
}

.knowledge-eval-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.knowledge-eval-metrics > div,
.knowledge-eval-sample {
  padding: 12px;
}

.knowledge-eval-metrics label,
.knowledge-eval-sample label {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.knowledge-eval-metrics strong {
  display: block;
  margin-top: 4px;
  font-size: 20px;
}

.knowledge-eval-samples {
  display: grid;
  gap: 10px;
}

.knowledge-eval-sample {
  display: grid;
  gap: 8px;
}

.knowledge-eval-sample strong,
.knowledge-eval-sample p {
  margin: 3px 0 0;
  color: #0f172a;
}

.knowledge-eval-sample small {
  color: #64748b;
}

.knowledge-context-link {
  width: fit-content;
  padding: 0;
  border: 0;
  background: transparent;
  color: #2563eb;
  font-weight: 800;
  cursor: pointer;
}

.knowledge-context-link:hover {
  color: #1d4ed8;
  text-decoration: underline;
}

.knowledge-ghost-btn {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 13px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #334155;
  font-weight: 700;
}

.knowledge-ghost-btn:hover {
  border-color: #10b981;
  color: #047857;
}

.knowledge-ghost-btn.danger {
  border-color: #fecaca;
  background: #fff7f7;
  color: #dc2626;
}

.knowledge-ghost-btn:disabled,
.knowledge-side-btn:disabled,
.knowledge-upload-btn:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.knowledge-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.knowledge-meta-grid > div {
  padding: 12px;
  min-width: 0;
}

.knowledge-meta-grid strong {
  display: block;
  margin-top: 5px;
  overflow-wrap: anywhere;
}

.knowledge-error-block {
  margin-top: 14px;
  padding: 12px;
}

.knowledge-error-block pre {
  margin: 8px 0 0;
  padding: 12px;
  max-height: 260px;
  overflow: auto;
  border-radius: 8px;
  background: #0f172a;
  color: #f8fafc;
  white-space: pre-wrap;
}

.knowledge-empty {
  padding: 18px;
  color: #64748b;
}

.knowledge-empty.large {
  min-height: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-style: dashed;
}

.knowledge-empty.large strong {
  color: #0f172a;
}

.knowledge-eval-overlay,
.knowledge-delete-overlay {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.48);
}

.knowledge-eval-overlay {
  z-index: 82;
}

.knowledge-delete-dialog {
  position: relative;
  width: min(480px, calc(100vw - 32px));
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 14px;
  padding: 18px;
  border: 1px solid #fee2e2;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.22);
}

.knowledge-context-overlay {
  position: fixed;
  inset: 0;
  z-index: 83;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.56);
}

.knowledge-context-dialog {
  position: relative;
  width: min(880px, calc(100vw - 32px));
  max-height: min(84vh, 900px);
  padding: 18px;
  overflow-y: auto;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.22);
}

.knowledge-context-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.knowledge-context-item {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.knowledge-context-item label {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.knowledge-context-item pre {
  margin: 8px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: #0f172a;
  line-height: 1.6;
}

.knowledge-delete-close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 30px;
  height: 30px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #64748b;
}

.knowledge-delete-icon {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #fee2e2;
  color: #dc2626;
}

.knowledge-delete-copy {
  min-width: 0;
  padding-right: 28px;
}

.knowledge-delete-copy p:not(.knowledge-kicker) {
  margin: 6px 0 0;
  color: #64748b;
}

.knowledge-delete-preview {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid #fee2e2;
  border-radius: 8px;
  background: #fff7f7;
}

.knowledge-delete-preview strong,
.knowledge-delete-preview span {
  display: block;
  margin-top: 4px;
  overflow-wrap: anywhere;
}

.knowledge-delete-actions {
  grid-column: 1 / -1;
  justify-content: flex-end;
}

.knowledge-delete-cancel,
.knowledge-delete-confirm {
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 14px;
  font-weight: 800;
}

.knowledge-delete-cancel {
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #334155;
}

.knowledge-delete-confirm {
  border: 1px solid #dc2626;
  background: #dc2626;
  color: #ffffff;
}

.knowledge-spin {
  animation: knowledge-spin 0.8s linear infinite;
}

@keyframes knowledge-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 980px) {
  .knowledge-layout {
    flex-direction: column;
    overflow: auto;
  }

  .knowledge-sidebar {
    width: 100%;
    max-height: 48vh;
  }

  .knowledge-main,
  .knowledge-content {
    overflow: visible;
  }

  .knowledge-stats,
  .knowledge-eval-metrics,
  .knowledge-meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .knowledge-topbar,
  .knowledge-detail-head {
    height: auto;
    align-items: flex-start;
    flex-direction: column;
    padding: 16px;
  }

  .knowledge-content {
    padding: 16px;
  }

  .knowledge-stats,
  .knowledge-eval-metrics,
  .knowledge-meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
