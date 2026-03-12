import api from './client'

export interface Service {
  id: string
  name: string
  slug: string
  service_type: string
  base_url: string
  auth_type: string
  auth_token: string | null
  auth_header_name: string
  default_model: string | null
  timeout_seconds: number
  supports_streaming: boolean
  extra_headers: Record<string, string> | null
  health_check_path: string | null
  health_check_method: string
  description: string | null
  tags: string[]
  request_schema_hint: Record<string, unknown> | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ServiceCreate {
  name: string
  slug: string
  service_type: string
  base_url: string
  auth_type?: string
  auth_token?: string | null
  auth_header_name?: string
  default_model?: string | null
  timeout_seconds?: number
  supports_streaming?: boolean
  extra_headers?: Record<string, string> | null
  health_check_path?: string | null
  health_check_method?: string
  description?: string | null
  tags?: string[]
  request_schema_hint?: Record<string, unknown> | null
  is_active?: boolean
}

export interface HealthCheckResult {
  service_id: string
  service_name: string
  status: string
  detail: string | null
  response_time_ms: number | null
}

export const fetchServices = () => api.get<Service[]>('/admin/services')
export const createService = (data: ServiceCreate) => api.post<Service>('/admin/services', data)
export const updateService = (id: string, data: Partial<ServiceCreate>) => api.put<Service>(`/admin/services/${id}`, data)
export const deleteService = (id: string) => api.delete(`/admin/services/${id}`)
export const checkServiceHealth = (id: string) => api.post<HealthCheckResult>(`/admin/services/${id}/check`)
