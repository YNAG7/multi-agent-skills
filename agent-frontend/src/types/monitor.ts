export interface MonitorSummary {
  total_runs: number
  success_runs: number
  failed_runs: number
  running_runs: number
  success_rate: number
  avg_latency_ms: number
}

export interface AgentRun {
  run_id: string
  thread_id: string
  user_id: number
  username?: string | null
  user_label?: string | null
  message_id?: number | null
  input: string
  output?: string | null
  status: string
  main_skill?: string | null
  started_at: string
  finished_at?: string | null
  latency_ms?: number | null
}

export interface AgentRunStep {
  id: number
  run_id: string
  step_index: number
  node_name?: string | null
  event_type: string
  input_json?: string | null
  output_json?: string | null
  error?: string | null
  created_at: string
}

export interface AgentToolCall {
  id: number
  run_id: string
  step_index: number
  tool_name: string
  skill?: string | null
  tool_input_json?: string | null
  tool_output_json?: string | null
  status: string
  latency_ms?: number | null
  created_at: string
}

export interface AgentRunDetail {
  run: AgentRun
  steps: AgentRunStep[]
  tool_calls: AgentToolCall[]
  trace?: MonitorTraceItem[]
}

export interface MonitorToolTrace {
  id: number
  step_index: number
  tool_name: string
  skill?: string | null
  status: string
  latency_ms?: number | null
  input?: unknown
  output?: unknown
}

export interface MonitorTraceItem {
  id: string
  type: 'user_input' | 'router' | 'worker' | 'tool' | 'summarizer' | string
  title: string
  status?: string | null
  skill?: string | null
  step_index?: number | null
  end_step_index?: number | null
  input?: unknown
  output?: unknown
  tools?: MonitorToolTrace[]
  error?: string | null
}
