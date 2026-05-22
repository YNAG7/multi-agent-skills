export interface KnowledgeDocument {
  id: number
  path: string
  filename: string
  source: string
  content_type?: string | null
  size_bytes: number
  mtime: number
  content_hash?: string | null
  status: string
  chunk_count: number
  error?: string | null
  uploaded_by?: number | null
  created_at?: string | null
  updated_at?: string | null
  indexed_at?: string | null
}

export interface KnowledgeSyncStats {
  scanned: number
  indexed: number
  skipped: number
  deleted: number
  failed: number
}

export interface KnowledgeEvalResult {
  case_count: number
  averages: Record<string, number>
  scores: Array<Record<string, any>>
  samples: Array<{
    user_input: string
    retrieved_contexts: string[]
    response: string
    reference: string
    question: string
    contexts: string[]
    answer: string
    ground_truth: string
  }>
}
