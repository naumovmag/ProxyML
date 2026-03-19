import api from './client'

export interface LoadTestTask {
  id: string
  service_id: string
  name: string
  interval_seconds: number
  service_type: string
  test_path: string
  test_method: string
  test_body: Record<string, unknown> | null
  test_headers: Record<string, string> | null
  status: string
  max_runs: number | null
  total_runs: number
  last_run_at: string | null
  created_at: string
  updated_at: string
}

export interface LoadTestTaskCreate {
  service_id: string
  name: string
  interval_seconds?: number
  test_path?: string | null
  test_method?: string
  test_body?: Record<string, unknown> | null
  test_headers?: Record<string, string> | null
  max_runs?: number | null
}

export interface LoadTestTaskUpdate {
  name?: string
  interval_seconds?: number
  test_path?: string
  test_method?: string
  test_body?: Record<string, unknown> | null
  test_headers?: Record<string, string> | null
  max_runs?: number | null
}

export interface LoadTestResult {
  id: string
  task_id: string
  status_code: number
  duration_ms: number
  request_size: number
  response_size: number
  error: string | null
  response_body: string | null
  created_at: string
}

export interface LoadTestStats {
  total: number
  avg_duration_ms: number | null
  min_duration_ms: number | null
  max_duration_ms: number | null
  p95_duration_ms: number | null
  error_count: number
  error_rate: number | null
}

export const fetchLoadTests = () =>
  api.get<LoadTestTask[]>('/admin/load-tests')

export const createLoadTest = (data: LoadTestTaskCreate) =>
  api.post<LoadTestTask>('/admin/load-tests', data)

export const getLoadTest = (id: string) =>
  api.get<LoadTestTask>(`/admin/load-tests/${id}`)

export const updateLoadTest = (id: string, data: LoadTestTaskUpdate) =>
  api.put<LoadTestTask>(`/admin/load-tests/${id}`, data)

export const deleteLoadTest = (id: string) =>
  api.delete(`/admin/load-tests/${id}`)

export const startLoadTest = (id: string) =>
  api.post(`/admin/load-tests/${id}/start`)

export const stopLoadTest = (id: string) =>
  api.post(`/admin/load-tests/${id}/stop`)

export const fetchLoadTestResults = (id: string, limit = 50, offset = 0) =>
  api.get<LoadTestResult[]>(`/admin/load-tests/${id}/results`, { params: { limit, offset } })

export const fetchLoadTestStats = (id: string) =>
  api.get<LoadTestStats>(`/admin/load-tests/${id}/stats`)

export const clearLoadTestResults = (id: string) =>
  api.delete(`/admin/load-tests/${id}/results`)
