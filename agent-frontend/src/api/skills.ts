import { request } from './http'
import type { Skill, SkillCreatePayload } from '../types/skill'

export async function getSkills(): Promise<Skill[]> {
  const data = await request<{ skills: Skill[] }>('/skills')
  return data.skills
}

export async function createSkill(payload: SkillCreatePayload): Promise<Skill> {
  const data = await request<{ skill: Skill }>('/skills', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

  return data.skill
}
