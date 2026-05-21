import { request } from './http'
import type { AgentRun, AgentRunDetail, MonitorSummary } from '../types/monitor'

export async function getMonitorSummary(): Promise<MonitorSummary> {
  return request<MonitorSummary>('/monitor/summary')
}

export async function getMonitorRuns(limit = 50): Promise<AgentRun[]> {
  const data = await request<{ runs: AgentRun[] }>(`/monitor/runs?limit=${limit}`)
  return data.runs
}

export async function getMonitorRunDetail(runId: string): Promise<AgentRunDetail> {
  return request<AgentRunDetail>(`/monitor/runs/${encodeURIComponent(runId)}`)
}
