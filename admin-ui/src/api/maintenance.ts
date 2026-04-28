import api from './client'

export interface CleanupCounts {
  request_logs: number
  load_test_results: number
  [key: string]: number
}

export interface CleanupPreview {
  retention_hours: number
  cutoff: string
  counts: CleanupCounts
}

export interface CleanupResult {
  retention_hours: number
  cutoff: string
  deleted: CleanupCounts
}

export const fetchCleanupPreview = (retention_hours: number) =>
  api.get<CleanupPreview>('/admin/maintenance/cleanup-preview', {
    params: { retention_hours },
  })

export const runCleanup = (retention_hours: number, tables: string[]) =>
  api.post<CleanupResult>('/admin/maintenance/cleanup', {
    retention_hours,
    tables,
  })
