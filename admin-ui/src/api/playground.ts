import api from './client'

export interface PlaygroundRequest {
  service_id: string
  method: string
  path: string
  body?: unknown
  headers?: Record<string, string>
  stream?: boolean
}

export interface PlaygroundResponse {
  status_code: number
  headers: Record<string, string>
  body: string
  duration_ms: number
  response_size: number
}

export const executePlayground = (data: PlaygroundRequest) =>
  api.post<PlaygroundResponse>('/admin/playground/execute', data)

export interface QuickTestRequest {
  url: string
  method: string
  body?: unknown
  headers?: Record<string, string>
  auth_type?: string
  auth_token?: string
  auth_header_name?: string
}

export const executeQuickTest = (data: QuickTestRequest) =>
  api.post<PlaygroundResponse>('/admin/playground/quick-test', data, { timeout: 660_000 })

export async function executePlaygroundStream(
  data: PlaygroundRequest,
  onChunk: (text: string) => void,
  onDone: (meta: { duration_ms: number }) => void,
  onError: (error: string) => void,
) {
  const token = localStorage.getItem('token')
  const startTime = performance.now()
  try {
    const response = await fetch('/api/admin/playground/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ ...data, stream: true }),
    })
    if (!response.ok) {
      const err = await response.text()
      onError(`HTTP ${response.status}: ${err}`)
      return
    }
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()!
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') continue
          try {
            const json = JSON.parse(payload)
            const content = json.choices?.[0]?.delta?.content
            if (content) onChunk(content)
          } catch {
            /* skip */
          }
        }
      }
    }
    onDone({ duration_ms: Math.round(performance.now() - startTime) })
  } catch (err: unknown) {
    onError(err instanceof Error ? err.message : 'Stream error')
  }
}

export const executePlaygroundUpload = (
  serviceId: string,
  path: string,
  file: File,
  model?: string,
) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('service_id', serviceId)
  formData.append('path', path)
  if (model) formData.append('model', model)
  return api.post<PlaygroundResponse>('/admin/playground/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const executePlaygroundTts = (data: PlaygroundRequest) =>
  api.post('/admin/playground/execute', data, { responseType: 'blob' })

// ─── Presets ───

export interface Preset {
  id: string
  service_id: string | null
  service_type: string
  name: string
  params: Record<string, unknown>
  created_at: string
  updated_at: string
}

export const fetchPresets = (params?: { service_id?: string; service_type?: string }) =>
  api.get<Preset[]>('/admin/playground/presets', { params })

export const createPreset = (data: { service_id: string; service_type: string; name: string; params: Record<string, unknown> }) =>
  api.post<Preset>('/admin/playground/presets', data)

export const updatePreset = (id: string, data: { name?: string; params?: Record<string, unknown> }) =>
  api.put<Preset>(`/admin/playground/presets/${id}`, data)

export const deletePreset = (id: string) =>
  api.delete(`/admin/playground/presets/${id}`)

// ─── History ───

export interface HistoryEntry {
  id: string
  service_id: string | null
  service_name: string | null
  service_type: string | null
  params: Record<string, unknown> | null
  request_body: string | null
  response_body: string | null
  status_code: number | null
  duration_ms: number | null
  token_usage: Record<string, number> | null
  note: string | null
  is_favorite: boolean
  created_at: string
}

export const fetchHistory = (params?: { service_id?: string; favorites_only?: boolean; limit?: number; offset?: number }) =>
  api.get<HistoryEntry[]>('/admin/playground/history', { params })

export const saveHistory = (data: {
  service_id: string
  service_name: string
  service_type: string
  params?: Record<string, unknown>
  request_body?: string
  response_body?: string
  status_code?: number
  duration_ms?: number
  token_usage?: Record<string, number>
  note?: string
}) => api.post<HistoryEntry>('/admin/playground/history', data)

export const updateHistoryEntry = (id: string, data: { note?: string; is_favorite?: boolean }) =>
  api.put<HistoryEntry>(`/admin/playground/history/${id}`, data)

export const deleteHistoryEntry = (id: string) =>
  api.delete(`/admin/playground/history/${id}`)

export const clearHistory = () =>
  api.delete('/admin/playground/history')
