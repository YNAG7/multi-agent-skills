import { API_BASE_URL, getToken, request } from './http'
import type { KnowledgeDocument, KnowledgeEvalResult, KnowledgeSyncStats } from '../types/knowledge'

export async function getKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
  const data = await request<{ documents: KnowledgeDocument[] }>('/knowledge')
  return data.documents
}

export async function uploadKnowledgeFile(file: File): Promise<KnowledgeDocument> {
  const formData = new FormData()
  formData.append('file', file)

  const token = getToken()
  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}/knowledge/upload`, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Upload failed: ${response.status}`)
  }

  const data = await response.json() as { document: KnowledgeDocument }
  return data.document
}

export async function syncKnowledgeDirectory(): Promise<KnowledgeSyncStats> {
  const data = await request<{ stats: KnowledgeSyncStats }>('/knowledge/sync', {
    method: 'POST',
  })
  return data.stats
}

export async function reindexKnowledgeDocument(documentId: number): Promise<KnowledgeDocument> {
  const data = await request<{ document: KnowledgeDocument }>(`/knowledge/${documentId}/reindex`, {
    method: 'POST',
  })
  return data.document
}

export async function deleteKnowledgeDocument(documentId: number): Promise<void> {
  await request(`/knowledge/${documentId}`, {
    method: 'DELETE',
  })
}

export async function evaluateKnowledge(jsonl: string, sync = false): Promise<KnowledgeEvalResult> {
  return request<KnowledgeEvalResult>('/knowledge/evaluate', {
    method: 'POST',
    body: JSON.stringify({ jsonl, sync }),
  })
}
