// src/types/auth.ts

export interface User {
  id: number
  username: string
  nickname?: string | null
  disabled?: boolean
  is_admin?: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}
