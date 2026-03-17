import api from './client'

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  email?: string
  display_name?: string
}

export interface UserRead {
  id: string
  username: string
  email: string | null
  display_name: string | null
  is_superadmin: boolean
  is_approved: boolean
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserRead
}

export const login = (data: LoginRequest) => api.post<TokenResponse>('/admin/login', data)
export const register = (data: RegisterRequest) => api.post<UserRead>('/admin/register', data)
export const fetchMe = () => api.get<UserRead>('/admin/me')
