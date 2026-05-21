<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Activity,
  ArrowLeft,
  Bot,
  CheckCircle2,
  Database,
  Layers,
  Loader2,
  LogOut,
  RefreshCw,
  Route,
  ScrollText,
  Search,
  TerminalSquare,
  Wrench,
} from 'lucide-vue-next'
import {
  getMonitorRunDetail,
  getMonitorRuns,
  getMonitorSummary,
} from '../api/monitor'
import type { User } from '../types/auth'
import type {
  AgentRun,
  AgentRunDetail,
  MonitorSummary,
  MonitorTraceItem,
  MonitorToolTrace,
} from '../types/monitor'

const props = defineProps<{
  user: User
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'logout'): void
}>()

const loading = ref(false)
const detailLoading = ref(false)
const error = ref('')
const summary = ref<MonitorSummary | null>(null)
const runs = ref<AgentRun[]>([])
const selectedRunId = ref('')
const detail = ref<AgentRunDetail | null>(null)
const searchText = ref('')
const selectedNodeId = ref('')
const activeTab = ref<'io' | 'meta'>('io')

const displayName = computed(() => props.user.nickname || props.user.username)

const filteredRuns = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return runs.value

  return runs.value.filter((run) => {
    return [
      run.input,
      run.output || '',
      run.main_skill || '',
      run.run_id,
      run.thread_id,
      run.username || '',
      run.user_label || '',
    ].some((value) => value.toLowerCase().includes(keyword))
  })
})

const traceItems = computed(() => {
  const items: MonitorTraceItem[] = []

  for (const item of detail.value?.trace || []) {
    if (item.type === 'tool') {
      const toolEntries: MonitorToolTrace[] = item.tools?.length
        ? item.tools
        : [{
            id: Number(String(item.id).split(':').pop() || 0),
            step_index: item.step_index || 0,
            tool_name: item.title.replace(/^工具调用:\s*/, ''),
            status: item.status || 'success',
            latency_ms: undefined,
            input: item.input,
            output: item.output,
          }]

      for (let index = items.length - 1; index >= 0; index -= 1) {
        const target = items[index]
        if (target.type !== 'worker') continue

        target.tools = [...(target.tools || []), ...toolEntries]
        target.tools.sort((left: MonitorToolTrace, right: MonitorToolTrace) => {
          const leftStep = left.step_index || 0
          const rightStep = right.step_index || 0
          if (leftStep !== rightStep) return leftStep - rightStep
          return left.id - right.id
        })
        break
      }
      continue
    }

    items.push({
      ...item,
      tools: item.tools ? [...item.tools] : [],
    })
  }

  return items
})

const activeNode = computed(() => {
  if (!selectedNodeId.value) return traceItems.value[0] || null
  return traceItems.value.find((item) => item.id === selectedNodeId.value) || traceItems.value[0] || null
})

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

function formatLatency(value?: number | null) {
  if (value === null || value === undefined) return '-'
  if (value < 1000) return `${value} ms`
  return `${(value / 1000).toFixed(1)} s`
}

function formatPercent(value?: number) {
  return `${Math.round((value || 0) * 100)}%`
}

function statusText(value?: string | null) {
  const map: Record<string, string> = {
    success: '成功',
    failed: '失败',
    running: '运行中',
    observed: '已捕获',
  }
  return map[value || ''] || value || '-'
}

function previewText(value?: string | null, max = 64) {
  if (!value) return ''
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length > max ? `${text.slice(0, max)}...` : text
}

function jsonBlock(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function displayBlock(value: unknown) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const payload = value as Record<string, unknown>
    if ('content' in payload && Object.keys(payload).every((key) => (
      ['type', 'content', 'name', 'tool_call_id'].includes(key)
    ))) {
      return jsonBlock(payload.content)
    }
  }

  if (typeof value !== 'string') return jsonBlock(value)

  const match = value.match(/content=(['"])([\s\S]*?)\1(?=\s+(additional_kwargs|response_metadata|id|tool_calls|invalid_tool_calls|name|tool_call_id)=|\)|$)/)
  if (!match) return value || '-'

  const raw = match[2]
    .replace(/\\n/g, '\n')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
  return raw || '-'
}

function hasPayload(value: unknown) {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim() !== ''
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length > 0
  return true
}

function itemIcon(type: string) {
  if (type === 'user_input') return ScrollText
  if (type === 'router') return Route
  if (type === 'worker') return Bot
  if (type === 'summarizer') return CheckCircle2
  return Wrench
}

async function refreshMonitor() {
  if (loading.value) return

  loading.value = true
  error.value = ''

  try {
    const [summaryData, runData] = await Promise.all([
      getMonitorSummary(),
      getMonitorRuns(100),
    ])
    summary.value = summaryData
    runs.value = runData

    const nextRunId = selectedRunId.value && runData.some((run) => run.run_id === selectedRunId.value)
      ? selectedRunId.value
      : runData[0]?.run_id || ''

    if (nextRunId) {
      await selectRun(nextRunId)
    } else {
      selectedRunId.value = ''
      detail.value = null
      selectedNodeId.value = ''
    }
  } catch (e: any) {
    error.value = e.message || '监控数据加载失败。'
  } finally {
    loading.value = false
  }
}

async function selectRun(runId: string) {
  if (!runId || detailLoading.value) return

  selectedRunId.value = runId
  detailLoading.value = true
  error.value = ''

  try {
    detail.value = await getMonitorRunDetail(runId)
    selectedNodeId.value = traceItems.value[0]?.id || ''
    activeTab.value = 'io'
  } catch (e: any) {
    error.value = e.message || '运行详情加载失败。'
  } finally {
    detailLoading.value = false
  }
}

onMounted(refreshMonitor)
</script>

<template>
  <div class="nx-layout monitor-layout">
    <aside class="nx-sidebar monitor-sidebar">
      <div class="nx-sidebar-top">
        <div class="nx-brand">
          <TerminalSquare color="#10B981" :size="24" />
          <span>Nexus OS</span>
        </div>

        <button class="nx-btn-new" type="button" @click="emit('back')">
          <ArrowLeft :size="18" />
          <span>返回聊天</span>
        </button>

        <button class="nx-btn-skills" type="button" @click="refreshMonitor">
          <RefreshCw :class="{ 'nx-spin': loading }" :size="18" />
          <span>刷新监控</span>
        </button>
      </div>

      <div class="nx-session-wrap">
        <div class="nx-list-title">运行记录</div>

        <label class="nx-side-search">
          <Search :size="15" />
          <input v-model="searchText" placeholder="搜索输入、技能、用户或 run id" />
        </label>

        <div v-if="summary" class="monitor-mini-stats">
          <div>
            <label>总数</label>
            <strong>{{ summary.total_runs }}</strong>
          </div>
          <div>
            <label>成功率</label>
            <strong>{{ formatPercent(summary.success_rate) }}</strong>
          </div>
          <div>
            <label>平均耗时</label>
            <strong>{{ formatLatency(summary.avg_latency_ms) }}</strong>
          </div>
        </div>

        <div v-if="error" class="nx-side-error">{{ error }}</div>

        <div v-if="loading && runs.length === 0" class="nx-center-loader">
          <Loader2 class="nx-spin" :size="18" />
        </div>

        <template v-else>
          <button
            v-for="run in filteredRuns"
            :key="run.run_id"
            class="monitor-run-item"
            :class="{ 'nx-active': selectedRunId === run.run_id, failed: run.status === 'failed' }"
            type="button"
            @click="selectRun(run.run_id)"
          >
            <div class="monitor-run-top">
              <span>{{ statusText(run.status) }}</span>
              <small>{{ formatLatency(run.latency_ms) }}</small>
            </div>
            <p>{{ previewText(run.input, 42) }}</p>
            <div class="monitor-run-meta">
              <span>{{ run.user_label || run.username || `用户 ${run.user_id}` }}</span>
              <small>{{ formatTime(run.started_at) }}</small>
            </div>
            <div class="monitor-run-meta">
              <span>{{ run.main_skill || '未识别技能' }}</span>
              <small>{{ run.run_id.slice(0, 8) }}</small>
            </div>
          </button>
        </template>
      </div>

      <div class="nx-sidebar-bottom">
        <div class="nx-user">
          <div class="nx-avatar">{{ displayName.charAt(0).toUpperCase() }}</div>
          <span>{{ displayName }}</span>
        </div>

        <button class="nx-btn-logout" type="button" title="退出登录" @click="emit('logout')">
          <LogOut :size="18" />
        </button>
      </div>
    </aside>

    <main class="nx-main-area monitor-main">
      <div class="nx-grid-bg"></div>

      <div class="nx-topbar monitor-topbar">
        <div class="nx-badge">
          <span class="nx-dot"></span>
          {{ detail ? `Run: ${detail.run.run_id.slice(0, 10)}` : 'Monitor' }}
        </div>

        <div class="monitor-top-actions">
          <span v-if="detail" class="monitor-status-pill" :class="detail.run.status">
            {{ statusText(detail.run.status) }}
          </span>
          <button class="nx-icon-btn" type="button" title="刷新" @click="refreshMonitor">
            <RefreshCw :class="{ 'nx-spin': loading }" :size="18" />
          </button>
        </div>
      </div>

      <div class="monitor-content">
        <div v-if="detailLoading" class="nx-center-loader full">
          <Loader2 class="nx-spin" color="#10B981" :size="32" />
        </div>

        <div v-else-if="!detail" class="monitor-empty">
          <div class="nx-empty-icon">
            <Activity color="#10B981" :size="32" />
          </div>
          <h2>选择一条运行记录</h2>
          <p>查看用户输入、Router、子 Agent、工具调用和 Summarizer 输出。</p>
        </div>

        <template v-else>
          <section class="monitor-overview">
            <div class="monitor-overview-head">
              <div>
                <div class="nx-skill-kicker">管理员观测</div>
                <h1>{{ detail.run.main_skill || '运行监控' }}</h1>
              </div>
              <span class="monitor-status-pill" :class="detail.run.status">
                {{ statusText(detail.run.status) }}
              </span>
            </div>

            <div class="nx-detail-grid monitor-detail-grid">
              <div>
                <label>用户</label>
                <div>{{ detail.run.user_label || detail.run.username || `用户 ${detail.run.user_id}` }}</div>
              </div>
              <div>
                <label>会话</label>
                <div>{{ detail.run.thread_id }}</div>
              </div>
              <div>
                <label>开始时间</label>
                <div>{{ formatTime(detail.run.started_at) }}</div>
              </div>
              <div>
                <label>耗时</label>
                <div>{{ formatLatency(detail.run.latency_ms) }}</div>
              </div>
            </div>
          </section>

          <section class="monitor-workbench">
            <div class="monitor-trace-panel">
              <div class="nx-section-head">
                <h3>执行链路</h3>
                <span>{{ traceItems.length }}</span>
              </div>

              <div class="monitor-trace-list">
                <button
                  v-for="item in traceItems"
                  :key="item.id"
                  class="monitor-trace-node"
                  :class="{ active: selectedNodeId === item.id, failed: item.status === 'failed' }"
                  type="button"
                  @click="selectedNodeId = item.id"
                >
                  <span class="trace-node-icon" :class="item.type">
                    <component :is="itemIcon(item.type)" :size="15" />
                  </span>
                  <span class="trace-node-copy">
                    <small>{{ item.type }}</small>
                    <strong>{{ item.title }}</strong>
                  </span>
                  <span v-if="item.tools && item.tools.length" class="trace-tool-count">
                    <Wrench :size="12" />
                    {{ item.tools.length }}
                  </span>
                </button>
              </div>
            </div>

            <div class="monitor-inspector">
              <div class="monitor-inspector-head">
                <div>
                  <div class="nx-skill-kicker">Payload</div>
                  <h3>{{ activeNode?.title || '节点详情' }}</h3>
                </div>
                <div class="monitor-tabs">
                  <button :class="{ active: activeTab === 'io' }" type="button" @click="activeTab = 'io'">
                    <Layers :size="14" />
                    <span>输入输出</span>
                  </button>
                  <button :class="{ active: activeTab === 'meta' }" type="button" @click="activeTab = 'meta'">
                    <Database :size="14" />
                    <span>元数据</span>
                  </button>
                </div>
              </div>

              <div v-if="activeNode && activeTab === 'io'" class="monitor-inspector-body">
                <div v-if="hasPayload(activeNode.input)" class="nx-md-block monitor-code-block">
                  <div class="nx-md-head">
                    <h4>INPUT</h4>
                  </div>
                  <pre>{{ displayBlock(activeNode.input) }}</pre>
                </div>

                <div v-if="activeNode.tools && activeNode.tools.length" class="monitor-tool-stack">
                  <div class="nx-section-head">
                    <h3>工具调用</h3>
                    <span>{{ activeNode.tools.length }}</span>
                  </div>

                  <div
                    v-for="tool in activeNode.tools as MonitorToolTrace[]"
                    :key="tool.id"
                    class="monitor-tool-card"
                    :class="{ failed: tool.status === 'failed' }"
                  >
                    <div class="monitor-tool-head">
                      <strong>{{ tool.tool_name }}</strong>
                      <span>{{ statusText(tool.status) }} / {{ formatLatency(tool.latency_ms) }}</span>
                    </div>
                    <div class="monitor-tool-flow">
                      <div v-if="hasPayload(tool.input)" class="nx-md-block monitor-tool-input">
                        <div class="nx-md-head">
                          <h4>INPUT</h4>
                        </div>
                        <pre>{{ displayBlock(tool.input) }}</pre>
                      </div>
                      <div v-if="hasPayload(tool.output)" class="nx-md-block monitor-tool-output">
                        <div class="nx-md-head">
                          <h4>OUTPUT</h4>
                        </div>
                        <pre>{{ displayBlock(tool.output) }}</pre>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="hasPayload(activeNode.output)" class="nx-md-block monitor-code-block">
                  <div class="nx-md-head">
                    <h4>OUTPUT</h4>
                  </div>
                  <pre>{{ displayBlock(activeNode.output) }}</pre>
                </div>

                <div v-if="activeNode.error" class="nx-form-error">
                  {{ activeNode.error }}
                </div>
              </div>

              <div v-else-if="detail" class="monitor-meta-grid">
                <div>
                  <label>Run ID</label>
                  <p>{{ detail.run.run_id }}</p>
                </div>
                <div>
                  <label>Thread ID</label>
                  <p>{{ detail.run.thread_id }}</p>
                </div>
                <div>
                  <label>主技能</label>
                  <p>{{ detail.run.main_skill || '未识别技能' }}</p>
                </div>
                <div>
                  <label>最终状态</label>
                  <p>{{ statusText(detail.run.status) }}</p>
                </div>
              </div>
            </div>
          </section>
        </template>
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
  z-index: 20;
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
.nx-btn-skills {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.nx-btn-new {
  padding: 12px 16px;
  background-color: #10b981 !important;
  color: #ffffff !important;
  border: none;
}

.nx-btn-skills {
  margin-top: 10px;
  padding: 11px 16px;
  background-color: transparent;
  color: #cbd5e1;
  border: 1px solid #334155;
}

.nx-session-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 10px 12px;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.42) transparent;
}

.nx-list-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  margin: 16px 8px 8px;
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

.nx-main-area {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #ffffff;
}

.nx-grid-bg {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(#e2e8f0 1px, transparent 1px),
    linear-gradient(90deg, #e2e8f0 1px, transparent 1px);
  background-size: 32px 32px;
  opacity: 0.7;
  pointer-events: none;
}

.nx-topbar {
  position: relative;
  height: 60px;
  border-bottom: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  z-index: 2;
}

.nx-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  background: #ffffff;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
}

.nx-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #10b981;
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

.nx-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.nx-section-head h3 {
  font-size: 20px;
  line-height: 1.2;
}

.nx-section-head span {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.nx-skill-kicker {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.nx-detail-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.nx-detail-grid > div {
  min-width: 0;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.nx-detail-grid label,
.monitor-meta-grid label {
  display: block;
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.nx-detail-grid div,
.monitor-meta-grid p {
  overflow-wrap: anywhere;
  font-weight: 700;
}

.nx-md-block {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  overflow: hidden;
}

.nx-md-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  background: #ffffff;
}

.nx-md-head h4 {
  font-size: 12px;
  color: #64748b;
  text-transform: uppercase;
}

.nx-md-block pre {
  margin: 0;
  max-height: 280px;
  overflow: auto;
  padding: 12px;
  background: #f8fafc;
  color: #0f172a;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.nx-center-loader {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nx-center-loader.full {
  min-height: calc(100vh - 60px);
}

.nx-empty-icon {
  width: 64px;
  height: 64px;
  background: #ecfdf5;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.nx-form-error,
.nx-side-error {
  padding: 10px 12px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fff1f2;
  color: #991b1b;
  font-size: 13px;
}

.nx-spin,
.spin {
  animation: spin 0.8s linear infinite;
}

.nx-side-search {
  height: 36px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 8px 12px;
  padding: 0 10px;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #94a3b8;
  background: rgba(15, 23, 42, 0.62);
}

.nx-side-search input {
  min-width: 0;
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: #f8fafc;
}

.monitor-mini-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  margin: 0 8px 12px;
}

.monitor-mini-stats > div {
  padding: 8px;
  border: 1px solid #1e293b;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.52);
}

.monitor-mini-stats label {
  display: block;
  color: #64748b;
  font-size: 10px;
  font-weight: 800;
}

.monitor-mini-stats strong {
  display: block;
  margin-top: 4px;
  color: #f8fafc;
  font-size: 16px;
}

.monitor-run-item {
  width: 100%;
  margin-bottom: 8px;
  padding: 11px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: #cbd5e1;
  text-align: left;
  cursor: pointer;
}

.monitor-run-item:hover {
  background-color: #1e293b;
  color: #ffffff;
}

.monitor-run-item.nx-active {
  background-color: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.34);
  color: #34d399;
}

.monitor-run-item.failed {
  border-color: rgba(239, 68, 68, 0.28);
}

.monitor-run-top,
.monitor-run-meta,
.monitor-top-actions,
.monitor-overview-head,
.monitor-tool-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.monitor-run-top span,
.monitor-run-meta span {
  display: inline-flex;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.14);
  color: #5eead4;
  font-size: 12px;
  font-weight: 800;
}

.monitor-run-top small,
.monitor-run-meta small {
  color: rgba(203, 213, 225, 0.64);
  font-size: 12px;
}

.monitor-run-item p {
  margin: 9px 0;
  color: #cbd5e1;
  font-size: 13px;
  line-height: 1.45;
}

.monitor-content {
  position: relative;
  height: calc(100vh - 60px);
  overflow-y: auto;
  padding: 24px;
  z-index: 1;
}

.monitor-empty {
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748b;
  text-align: center;
}

.monitor-empty h2 {
  color: #0f172a;
  margin-bottom: 8px;
}

.monitor-overview,
.monitor-trace-panel,
.monitor-inspector {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
}

.monitor-overview {
  padding: 18px;
  margin-bottom: 16px;
}

.monitor-overview h1 {
  margin-top: 2px;
  font-size: 24px;
}

.monitor-status-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 900;
}

.monitor-status-pill.failed {
  background: #fee2e2;
  color: #991b1b;
}

.monitor-status-pill.running {
  background: #fef3c7;
  color: #92400e;
}

.monitor-detail-grid {
  margin-top: 14px;
}

.monitor-workbench {
  display: grid;
  grid-template-columns: minmax(300px, 0.9fr) minmax(0, 1.5fr);
  gap: 16px;
  align-items: start;
}

.monitor-trace-panel {
  padding: 16px;
}

.monitor-trace-list {
  position: relative;
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.monitor-trace-node {
  width: 100%;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  color: #0f172a;
  text-align: left;
  cursor: pointer;
}

.monitor-trace-node:hover,
.monitor-trace-node.active {
  border-color: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.08);
}

.monitor-trace-node.failed {
  border-color: #fecaca;
}

.trace-node-icon {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #d1fae5;
  color: #047857;
}

.trace-node-icon.router {
  background: #e0e7ff;
  color: #4338ca;
}

.trace-node-icon.worker {
  background: #ccfbf1;
  color: #0f766e;
}

.trace-node-icon.summarizer {
  background: #ecfdf5;
  color: #15803d;
}

.trace-node-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trace-node-copy small {
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.trace-node-copy strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.trace-tool-count {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.monitor-inspector {
  min-width: 0;
  overflow: hidden;
}

.monitor-inspector-head {
  min-height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid #e2e8f0;
}

.monitor-inspector-head h3 {
  margin-top: 2px;
  font-size: 20px;
}

.monitor-tabs {
  display: inline-flex;
  padding: 3px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.monitor-tabs button {
  height: 30px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.monitor-tabs button.active {
  background: #ffffff;
  color: #0f766e;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.monitor-inspector-body {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.monitor-tool-stack {
  display: grid;
  gap: 12px;
}

.monitor-tool-card {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.monitor-tool-card.failed {
  border-color: #fecaca;
}

.monitor-tool-head {
  margin-bottom: 10px;
}

.monitor-tool-head span {
  display: inline-flex;
  padding: 3px 8px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.monitor-tool-flow {
  display: grid;
  gap: 10px;
}

.monitor-tool-input pre {
  max-height: 120px;
}

.monitor-tool-output pre {
  max-height: 340px;
}

.monitor-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
}

.monitor-meta-grid > div {
  min-width: 0;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.monitor-meta-grid p {
  margin: 0;
}

.monitor-content::-webkit-scrollbar,
.nx-session-wrap::-webkit-scrollbar,
.nx-md-block pre::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.monitor-content::-webkit-scrollbar-track,
.nx-session-wrap::-webkit-scrollbar-track,
.nx-md-block pre::-webkit-scrollbar-track {
  background: transparent;
}

.monitor-content::-webkit-scrollbar-thumb,
.nx-md-block pre::-webkit-scrollbar-thumb {
  background: rgba(100, 116, 139, 0.24);
  border-radius: 999px;
}

.nx-session-wrap::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.32);
  border-radius: 999px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1180px) {
  .monitor-workbench {
    grid-template-columns: 1fr;
  }

  .nx-detail-grid,
  .monitor-meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .monitor-layout {
    flex-direction: column;
    overflow: auto;
  }

  .nx-sidebar {
    width: 100%;
    min-height: 420px;
  }

  .monitor-content {
    height: auto;
  }

  .nx-detail-grid,
  .monitor-meta-grid {
    grid-template-columns: 1fr;
  }

  .monitor-inspector-head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>

<style>
.monitor-layout {
  width: 100vw;
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: #ffffff;
  color: #0f172a;
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.monitor-sidebar {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #1e293b;
  background: #0b1120;
  color: #f8fafc;
}

.monitor-main {
  position: relative;
  flex: 1;
  overflow: hidden;
  background: #ffffff;
}

.monitor-layout .nx-sidebar-top {
  display: block;
}

.monitor-layout .nx-sidebar-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.monitor-layout .nx-brand,
.monitor-layout .nx-btn-new,
.monitor-layout .nx-btn-skills,
.monitor-layout .nx-side-search,
.monitor-layout .monitor-run-item,
.monitor-layout .nx-icon-btn,
.monitor-layout .monitor-trace-node,
.monitor-layout .monitor-tool-card,
.monitor-layout .monitor-overview,
.monitor-layout .monitor-trace-panel,
.monitor-layout .monitor-inspector,
.monitor-layout .nx-md-block {
  border-radius: 8px;
}

.monitor-layout .nx-btn-new,
.monitor-layout .nx-btn-skills,
.monitor-layout .monitor-run-item,
.monitor-layout .nx-icon-btn,
.monitor-layout .monitor-trace-node,
.monitor-layout .monitor-tabs button {
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.monitor-layout .nx-btn-new {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  border: none;
  background: #10b981;
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
}

.monitor-layout .nx-btn-skills {
  width: 100%;
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 11px 16px;
  border: 1px solid #334155;
  background: transparent;
  color: #cbd5e1;
  font-size: 14px;
  font-weight: 600;
}

.monitor-layout .nx-session-wrap {
  flex: 1;
  overflow-y: auto;
}

.monitor-layout .nx-side-search {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  margin: 0 8px 12px;
  padding: 0 10px;
  border: 1px solid #334155;
  background: rgba(15, 23, 42, 0.62);
  color: #94a3b8;
}

.monitor-layout .nx-side-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #f8fafc;
}

.monitor-layout .monitor-mini-stats > div {
  padding: 8px;
  border: 1px solid #1e293b;
  background: rgba(15, 23, 42, 0.52);
}

.monitor-layout .monitor-run-item {
  width: 100%;
  margin-bottom: 8px;
  padding: 11px 12px;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  color: #cbd5e1;
}

.monitor-layout .monitor-run-item:hover {
  background: #1e293b;
  color: #ffffff;
}

.monitor-layout .monitor-run-item.nx-active {
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.monitor-layout .nx-topbar {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 24px;
  border-bottom: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
}

.monitor-layout .nx-grid-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(90deg, #f1f5f9 1px, transparent 1px),
    linear-gradient(#f1f5f9 1px, transparent 1px);
  background-size: 32px 32px;
}

.monitor-layout .monitor-content {
  position: relative;
  z-index: 1;
  height: calc(100vh - 60px);
  overflow-y: auto;
  padding: 24px;
}

.monitor-layout .monitor-overview,
.monitor-layout .monitor-trace-panel,
.monitor-layout .monitor-inspector,
.monitor-layout .nx-md-block,
.monitor-layout .monitor-tool-card {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e2e8f0;
}

.monitor-layout .monitor-workbench {
  display: grid;
  grid-template-columns: minmax(300px, 0.9fr) minmax(0, 1.5fr);
  gap: 16px;
  align-items: start;
}

.monitor-layout .monitor-trace-node {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  width: 100%;
  padding: 12px;
  text-align: left;
  border: 1px solid #e2e8f0;
  background: #ffffff;
}

.monitor-layout .monitor-tool-flow {
  display: grid;
  gap: 10px;
}

.monitor-layout .monitor-tool-input pre {
  max-height: 120px;
}

.monitor-layout .monitor-tool-output pre {
  max-height: 340px;
}

@media (max-width: 760px) {
  .monitor-layout {
    flex-direction: column;
    overflow: auto;
  }

  .monitor-sidebar {
    width: 100%;
    min-height: 420px;
  }

  .monitor-layout .monitor-content {
    height: auto;
  }

  .monitor-layout .monitor-workbench {
    grid-template-columns: 1fr;
  }
}
</style>
