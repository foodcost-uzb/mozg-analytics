import { apiClient } from './client'
import type { User, TokenResponse, LoginRequest } from '@/types'

export const authApi = {
  async login(credentials: LoginRequest): Promise<TokenResponse> {
    return apiClient.post<TokenResponse>('/auth/login', credentials)
  },

  async register(data: {
    organization_name: string
    organization_slug: string
    email: string
    password: string
    first_name: string
    last_name?: string
  }): Promise<TokenResponse> {
    return apiClient.post<TokenResponse>('/auth/register', data)
  },

  async refreshToken(refreshToken: string): Promise<TokenResponse> {
    return apiClient.post<TokenResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    })
  },

  async getCurrentUser(): Promise<User> {
    return apiClient.get<User>('/auth/me')
  },

  async telegramAuth(data: {
    id: number
    first_name: string
    last_name?: string
    username?: string
    photo_url?: string
    auth_date: number
    hash: string
  }): Promise<TokenResponse> {
    return apiClient.post<TokenResponse>('/auth/telegram', data)
  },
}
