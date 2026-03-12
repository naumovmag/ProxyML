import api from './client'

export interface ApiKey {
  id: string
  name: string
  key_prefix: string
  allowed_services: string[] | null
  rate_limit_rpm: number | null
  is_active: boolean
  expires_at: string | null
  last_used_at: string | null
  created_at: string
}

export interface ApiKeyCreated extends ApiKey {
  raw_key: string
}

export interface ApiKeyCreate {
  name: string
  allowed_services?: string[] | null
  rate_limit_rpm?: number | null
  expires_at?: string | null
}

export const fetchApiKeys = () => api.get<ApiKey[]>('/admin/api-keys')
export const createApiKey = (data: ApiKeyCreate) => api.post<ApiKeyCreated>('/admin/api-keys', data)
export const deleteApiKey = (id: string) => api.delete(`/admin/api-keys/${id}`)
export const toggleApiKey = (id: string) => api.patch<ApiKey>(`/admin/api-keys/${id}/toggle`)
