import api from './client'

export interface StatsOverview {
  period_hours: number
  total_requests: number
  total_errors: number
  avg_duration_ms: number
  total_request_bytes: number
  total_response_bytes: number
}

export interface ServiceStats {
  service_slug: string
  request_count: number
  error_count: number
  avg_duration_ms: number
}

export interface KeyStats {
  api_key_name: string
  request_count: number
}

export interface RecentLog {
  id: string
  service_slug: string
  api_key_name: string | null
  method: string
  path: string
  status_code: number
  duration_ms: number
  request_size: number
  response_size: number
  is_streaming: boolean
  is_cached: boolean
  error: string | null
  created_at: string
}

export const fetchStatsOverview = (hours = 24) =>
  api.get<StatsOverview>(`/admin/stats/overview?hours=${hours}`)

export const fetchStatsByService = (hours = 24) =>
  api.get<ServiceStats[]>(`/admin/stats/by-service?hours=${hours}`)

export const fetchStatsByKey = (hours = 24) =>
  api.get<KeyStats[]>(`/admin/stats/by-key?hours=${hours}`)

export interface LogFilters {
  service_slug?: string
  method?: string
  status?: string
  source?: string
  api_key_name?: string
}

export const fetchRecentLogs = (limit = 50, filters?: LogFilters) => {
  const params = new URLSearchParams({ limit: String(limit) })
  if (filters?.service_slug) params.set('service_slug', filters.service_slug)
  if (filters?.method) params.set('method', filters.method)
  if (filters?.status) params.set('status', filters.status)
  if (filters?.source) params.set('source', filters.source)
  if (filters?.api_key_name) params.set('api_key_name', filters.api_key_name)
  return api.get<RecentLog[]>(`/admin/stats/recent?${params}`)
}
