import api from './client'

export interface SystemSettings {
  ai_enabled: boolean
  llm_service_slug: string | null
  llm_model: string | null
  updated_at: string | null
}

export interface SystemSettingsUpdate {
  ai_enabled?: boolean
  llm_service_slug?: string | null
  llm_model?: string | null
}

export const fetchSettings = () => api.get<SystemSettings>('/admin/settings')
export const updateSettings = (data: SystemSettingsUpdate) => api.put<SystemSettings>('/admin/settings', data)
