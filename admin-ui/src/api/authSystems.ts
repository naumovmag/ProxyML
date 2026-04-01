import api from './client'

export interface RegistrationField {
  name: string
  type: 'string' | 'number' | 'boolean' | 'email' | 'phone'
  required: boolean
  unique: boolean
}

export interface AuthSystem {
  id: string
  name: string
  slug: string
  access_token_ttl_minutes: number
  refresh_token_ttl_days: number
  registration_fields: RegistrationField[]
  users_active_by_default: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AuthSystemCreate {
  name: string
  slug: string
  access_token_ttl_minutes?: number
  refresh_token_ttl_days?: number
  registration_fields?: RegistrationField[]
  users_active_by_default?: boolean
}

export interface AuthSystemUpdate {
  name?: string
  access_token_ttl_minutes?: number
  refresh_token_ttl_days?: number
  registration_fields?: RegistrationField[]
  users_active_by_default?: boolean
  is_active?: boolean
}

export interface AuthSystemUser {
  id: string
  email: string
  custom_fields: Record<string, any>
  is_active: boolean
  created_at: string
}

export const fetchAuthSystems = () => api.get<AuthSystem[]>('/admin/auth-systems')
export const getAuthSystem = (id: string) => api.get<AuthSystem>(`/admin/auth-systems/${id}`)
export const createAuthSystem = (data: AuthSystemCreate) => api.post<AuthSystem>('/admin/auth-systems', data)
export const updateAuthSystem = (id: string, data: AuthSystemUpdate) => api.put<AuthSystem>(`/admin/auth-systems/${id}`, data)
export const deleteAuthSystem = (id: string) => api.delete(`/admin/auth-systems/${id}`)
export const fetchAuthSystemUsers = (id: string) => api.get<AuthSystemUser[]>(`/admin/auth-systems/${id}/users`)
export const toggleAuthUser = (systemId: string, userId: string) => api.patch(`/admin/auth-systems/${systemId}/users/${userId}/toggle`)
export const updateAuthUser = (systemId: string, userId: string, data: { email?: string; custom_fields?: Record<string, any>; is_active?: boolean }) =>
  api.put<AuthSystemUser>(`/admin/auth-systems/${systemId}/users/${userId}`, data)
export const resetAuthUserPassword = (systemId: string, userId: string, newPassword: string) =>
  api.post(`/admin/auth-systems/${systemId}/users/${userId}/reset-password`, { new_password: newPassword })

export interface AuthSystemStatsResponse {
  total_users: number
  active_users: number
  inactive_users: number
  new_users: number
  timeseries: { bucket: string; count: number }[]
}

export const fetchAuthSystemStats = (id: string, hours = 720) =>
  api.get<AuthSystemStatsResponse>(`/admin/auth-systems/${id}/stats?hours=${hours}`)
