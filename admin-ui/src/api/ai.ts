import api from './client'

export interface AITextResponse {
  text: string
}

export const aiParseCurl = (curl_command: string) =>
  api.post<Record<string, unknown>>('/admin/ai/parse-curl', { curl_command })

export const aiAnalyzeError = (data: {
  service_slug: string
  method: string
  path: string
  status_code: number
  duration_ms: number
  error?: string | null
  is_streaming?: boolean
  is_fallback?: boolean
}) => api.post<AITextResponse>('/admin/ai/analyze-error', data)

export const aiDiagnoseHealth = (data: {
  name: string
  service_type: string
  base_url: string
  health_check_path?: string | null
  health_check_method?: string
  status: string
  detail?: string | null
  response_time_ms?: number | null
}) => api.post<AITextResponse>('/admin/ai/diagnose-health', data)

export const aiSummarizeDashboard = (data: {
  period_hours: number
  total_requests: number
  total_errors: number
  error_rate: number
  avg_duration_ms: number
  total_request_bytes: number
  total_response_bytes: number
  by_service?: unknown[]
  by_key?: unknown[]
}) => api.post<AITextResponse>('/admin/ai/summarize-dashboard', data)

export const aiGenerateDescription = (data: {
  name: string
  service_type: string
  base_url: string
  default_model?: string | null
  supports_streaming?: boolean
}) => api.post<AITextResponse>('/admin/ai/generate-description', data)
