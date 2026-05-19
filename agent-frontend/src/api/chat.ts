// src/api/chat.ts

import { request, getToken, API_BASE_URL } from './http'
import type { ChatMessage, ChatResponse, ChatSession } from '../types/chat'
export async function sendMessage(
  message: string,
  threadId: string
): Promise<ChatResponse> {
  return request<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      thread_id: threadId,
    }),
  })
}

export async function getSessions(): Promise<ChatSession[]> {
  const data = await request<{ sessions: ChatSession[] }>('/chat/sessions')
  return data.sessions
}

export async function getMessages(threadId: string): Promise<ChatMessage[]> {
  const data = await request<{ messages: ChatMessage[] }>(
    `/chat/sessions/${encodeURIComponent(threadId)}/messages`
  )

  return data.messages
}


function normalizeStreamText(data: string): string {
  if (!data || data.trim() === '[DONE]') return ''

  const decodeEscaped = (text: string) =>
    text
      .replace(/\\r\\n/g, '\n')
      .replace(/\\n/g, '\n')
      .replace(/\\t/g, '\t')

  try {
    const payload = JSON.parse(data)

    const pickText = (value: any): string => {
      if (typeof value === 'string') return decodeEscaped(value)
      if (!value || typeof value !== 'object') return ''

      const textKeys = ['content', 'answer', 'text', 'token', 'delta', 'output']
      for (const key of textKeys) {
        if (typeof value[key] === 'string') return decodeEscaped(value[key])
      }

      const nestedKeys = ['data', 'message', 'chunk', 'delta', 'choices', 'payload']
      for (const key of nestedKeys) {
        const text = pickText(value[key])
        if (text) return text
      }

      if (Array.isArray(value)) {
        for (const item of value) {
          const text = pickText(item)
          if (text) return text
        }
      }

      return ''
    }

    return pickText(payload)
  } catch {
    return decodeEscaped(data)
  }
}

export async function sendStreamMessage(
  message: string,
  threadId: string,
  onChunk: (text: string) => void
): Promise<void> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      message,
      thread_id: threadId,
    }),
  })

  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`)
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式读取')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')

  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()

    if (done) {
      buffer += decoder.decode()
      break
    }

    buffer += decoder.decode(value, { stream: true })

    const events = buffer.split(/\r?\n\r?\n/)
    buffer = events.pop() ?? ''

    for (const event of events) {
      const data = event
        .split(/\r?\n/)
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.replace(/^data:\s?/, ''))
        .join('\n')

      if (data.trim() === '[DONE]') return

      const text = normalizeStreamText(data)
      if (text) onChunk(text)
    }
  }

  if (buffer.trim()) {
    const data = buffer
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.replace(/^data:\s?/, ''))
      .join('\n')

    const text = normalizeStreamText(data)
    if (text) onChunk(text)
  }
}
