import { API_BASE_URL, getToken, request } from './http'
import type {
  Skill,
  SkillCreatePayload,
  SkillDetail,
  SkillImportPreview,
} from '../types/skill'

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

async function sendSkillZip(path: string, file: File): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  const token = getToken()
  const headers: Record<string, string> = {}

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Import failed: ${response.status}`)
  }

  return response.json()
}

export async function previewSkillZip(file: File): Promise<SkillImportPreview> {
  const data = await sendSkillZip('/skills/import/zip/preview', file) as { preview: SkillImportPreview }
  return data.preview
}

export async function importSkillZip(file: File): Promise<{ preview: SkillImportPreview; skill: Skill }> {
  return sendSkillZip('/skills/import/zip', file)
}

export async function importSkillDirectory(source: string): Promise<{ preview: SkillImportPreview; skill: Skill }> {
  const data = await request<{ preview: SkillImportPreview; skill: Skill }>('/skills/import/directory', {
    method: 'POST',
    body: JSON.stringify({ source }),
  })

  return data
}

export async function getSkillDetail(skillName: string): Promise<SkillDetail> {
  const data = await request<{ skill: SkillDetail }>(`/skills/${encodeURIComponent(skillName)}`)
  return data.skill
}

export async function setSkillEnabled(skillName: string, enabled: boolean): Promise<Skill> {
  const data = await request<{ skill: Skill }>(`/skills/${encodeURIComponent(skillName)}/enabled`, {
    method: 'PATCH',
    body: JSON.stringify({ enabled }),
  })

  return data.skill
}

export async function deleteSkill(skillName: string): Promise<void> {
  await request(`/skills/${encodeURIComponent(skillName)}`, {
    method: 'DELETE',
  })
}

export async function reloadSkills(): Promise<Skill[]> {
  const data = await request<{ skills: Skill[] }>('/skills/reload', {
    method: 'POST',
  })
  return data.skills
}
