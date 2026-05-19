// src/api/auth.ts

import { request, setToken, clearToken } from './http'
import type { LoginResponse, User } from '../types/auth'

export async function login(username: string, password: string): Promise<User> {
  const data = await request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({
      username,
      password,
    }),
  })

  setToken(data.access_token)

  return data.user
}

export async function register(
  username: string,
  password: string,
  nickname?: string
): Promise<User> {
  const data = await request<LoginResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      username,
      password,
      nickname,
    }),
  })

  setToken(data.access_token)

  return data.user
}

export async function getMe(): Promise<User> {
  return request<User>('/auth/me')
}

export function logout() {
  clearToken()
}