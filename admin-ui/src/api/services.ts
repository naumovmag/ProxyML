import api from './client'

export interface ServiceGroup {
  id: string
  name: string
  description: string | null
  sort_order: number
  created_at: string
}

export interface ServiceGroupCreate {
  name: string
  description?: string | null
  sort_order?: number
}

export interface Service {
  group_id: string | null
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
  cache_enabled: boolean
  cache_ttl_seconds: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ServiceCreate {
  name: string
  slug: string
  group_id?: string | null
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
  cache_enabled?: boolean
  cache_ttl_seconds?: number
  is_active?: boolean
}

export interface HealthCheckResult {
  service_id: string
  service_name: string
  status: string
  detail: string | null
  response_time_ms: number | null
}

export interface HealthReportItem {
  service_id: string
  service_name: string
  slug: string
  is_active: boolean
  status: string
  detail: string | null
  response_time_ms: number | null
}

export interface HealthReport {
  items: HealthReportItem[]
  total: number
  healthy: number
  unhealthy: number
  unconfigured: number
}

export interface ImportResult {
  groups_created: number
  groups_updated: number
  created: number
  updated: number
  errors: string[]
  total_processed: number
}

export const fetchServiceGroups = () => api.get<ServiceGroup[]>('/admin/service-groups')
export const createServiceGroup = (data: ServiceGroupCreate) => api.post<ServiceGroup>('/admin/service-groups', data)
export const updateServiceGroup = (id: string, data: Partial<ServiceGroupCreate>) => api.put<ServiceGroup>(`/admin/service-groups/${id}`, data)
export const deleteServiceGroup = (id: string) => api.delete(`/admin/service-groups/${id}`)

export const fetchServices = () => api.get<Service[]>('/admin/services')
export const createService = (data: ServiceCreate) => api.post<Service>('/admin/services', data)
export const updateService = (id: string, data: Partial<ServiceCreate>) => api.put<Service>(`/admin/services/${id}`, data)
export const deleteService = (id: string) => api.delete(`/admin/services/${id}`)
export const checkServiceHealth = (id: string) => api.post<HealthCheckResult>(`/admin/services/${id}/check`)

export const checkAllServicesHealth = () => api.post<HealthReport>('/admin/services-check-all')

export const exportServices = () =>
  api.get('/admin/services-export', { responseType: 'blob' })

export const importServices = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post<ImportResult>('/admin/services-import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
