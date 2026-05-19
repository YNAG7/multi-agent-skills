export interface Skill {
  name: string
  description: string
  tool_count: number
  needs_time_context: boolean
  skill_path?: string | null
}

export interface SkillCreatePayload {
  name: string
  description: string
  content: string
  needs_time_context: boolean
}
