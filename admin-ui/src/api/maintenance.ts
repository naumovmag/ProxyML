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
  approximate: Record<string, boolean>
}

export interface CleanupStatus {
  status: 'idle' | 'running' | 'done' | 'error'
  retention_hours?: number
  cutoff?: string
  tables?: string[]
  deleted?: Partial<CleanupCounts>
  dropped_partitions?: string[]
  error?: string
  started_at?: string
  finished_at?: string
}

export interface CleanupStarted {
  status: string
  cutoff: string
  tables: string[]
}

export const fetchCleanupPreview = (retention_hours: number) =>
  api.get<CleanupPreview>('/admin/maintenance/cleanup-preview', {
    params: { retention_hours },
  })

export const runCleanup = (retention_hours: number, tables: string[]) =>
  api.post<CleanupStarted>('/admin/maintenance/cleanup', {
    retention_hours,
    tables,
  })

export const fetchCleanupStatus = () =>
  api.get<CleanupStatus>('/admin/maintenance/cleanup-status')
