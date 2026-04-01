import api from './client'

// --- Types ---

export interface ProviderConfigField {
  name: string
  type: string
  required: boolean
  label: string
  placeholder: string
  secret: boolean
}

export interface ProviderSchema {
  label: string
  config_schema: ProviderConfigField[]
}

export interface ChannelTypeSchema {
  label: string
  icon: string
  description: string
  providers: Record<string, ProviderSchema>
}

export interface VerificationChannel {
  id: string
  auth_system_id: string
  channel_type: string
  provider_type: string
  provider_config: Record<string, any>
  is_enabled: boolean
  is_required: boolean
  priority: number
  settings: Record<string, any>
  created_at: string
  updated_at: string
}

export interface VerificationChannelCreate {
  channel_type: string
  provider_type: string
  provider_config: Record<string, any>
  is_enabled?: boolean
  is_required?: boolean
  priority?: number
  settings?: Record<string, any>
}

export interface VerificationChannelUpdate {
  provider_type?: string
  provider_config?: Record<string, any>
  is_enabled?: boolean
  is_required?: boolean
  priority?: number
  settings?: Record<string, any>
}

// --- API Functions ---

export async function fetchVerificationProviders(): Promise<Record<string, ChannelTypeSchema>> {
  const { data } = await api.get('/admin/verification-providers')
  return data.providers
}

export async function fetchChannels(systemId: string): Promise<VerificationChannel[]> {
  const { data } = await api.get(`/admin/auth-systems/${systemId}/channels`)
  return data
}

export async function createChannel(systemId: string, payload: VerificationChannelCreate): Promise<VerificationChannel> {
  const { data } = await api.post(`/admin/auth-systems/${systemId}/channels`, payload)
  return data
}

export async function updateChannel(systemId: string, channelId: string, payload: VerificationChannelUpdate): Promise<VerificationChannel> {
  const { data } = await api.put(`/admin/auth-systems/${systemId}/channels/${channelId}`, payload)
  return data
}

export async function deleteChannel(systemId: string, channelId: string): Promise<void> {
  await api.delete(`/admin/auth-systems/${systemId}/channels/${channelId}`)
}

export async function testChannel(systemId: string, channelId: string, to: string): Promise<{ ok: boolean; message: string }> {
  const { data } = await api.post(`/admin/auth-systems/${systemId}/channels/${channelId}/test`, { to })
  return data
}

export async function validateChannel(systemId: string, channelId: string): Promise<{ ok: boolean }> {
  const { data } = await api.post(`/admin/auth-systems/${systemId}/channels/${channelId}/validate`)
  return data
}
