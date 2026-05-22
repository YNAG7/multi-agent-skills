export interface Skill {
  name: string
  description: string
  tool_count: number
  needs_time_context: boolean
  skill_path?: string | null
  skill_dir?: string | null
  has_mcp?: boolean
  enabled: boolean
  degraded?: boolean
  load_errors?: string[]
  protected?: boolean
}

export interface SkillCreatePayload {
  name: string
  description: string
  content: string
  needs_time_context: boolean
  skill_json?: Record<string, any>
}

export interface SkillUpdatePayload {
  skill_md: string
  skill_json: Record<string, any>
}

export interface SkillDetail extends Skill {
  skill_md: string
  skill_json: Record<string, any>
  tools: Array<{ name: string; description: string }>
  mcp_servers: Record<string, any>
  mcp_tool_allowlist: string[]
}

export interface SkillImportPreview {
  name: string
  description: string
  tool_count: number
  has_mcp: boolean
  enabled: boolean
  degraded: boolean
  load_errors: string[]
}
