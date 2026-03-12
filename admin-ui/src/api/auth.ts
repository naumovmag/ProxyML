import api from './client'

export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export const login = (data: LoginRequest) => api.post<TokenResponse>('/admin/login', data)
