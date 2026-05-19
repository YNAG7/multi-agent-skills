// src/types/chat.ts

export interface ChatSession {
  thread_id: string
  title?: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at?: string
}

export interface ChatResponse {
  answer: string
  thread_id: string
  main_skill?: string | null
  current_agent?: string | null
}