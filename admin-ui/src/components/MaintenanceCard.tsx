import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Trash2, Loader2, AlertTriangle } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  fetchCleanupPreview,
  fetchCleanupStatus,
  runCleanup,
  CleanupPreview,
  CleanupStatus,
} from '@/api/maintenance'

const TABLES = ['request_logs', 'load_test_results']

const PRESETS: { label: string; hours: number }[] = [
  { label: 'Last 24 hours', hours: 24 },
  { label: 'Last 7 days', hours: 24 * 7 },
  { label: 'Last 30 days', hours: 24 * 30 },
]

const POLL_INTERVAL_MS = 2000

export function MaintenanceCard() {
  const [presetIdx, setPresetIdx] = useState<string>('0')
  const [customHours, setCustomHours] = useState<number>(24)
  const [preview, setPreview] = useState<CleanupPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [cleanupStatus, setCleanupStatus] = useState<CleanupStatus | null>(null)
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  const isCustom = presetIdx === 'custom'
  const retentionHours = isCustom ? customHours : PRESETS[Number(presetIdx)].hours
  const running = cleanupStatus?.status === 'running'
  const totalToDelete = preview
    ? TABLES.reduce((acc, t) => acc + (preview.counts[t] || 0), 0)
    : 0
  const hasApproximate = preview
    ? TABLES.some((t) => preview.approximate?.[t])
    : false
  const totalDeleted = cleanupStatus?.deleted
    ? TABLES.reduce((acc, t) => acc + (cleanupStatus.deleted?.[t] || 0), 0)
    : 0

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current)
      pollTimer.current = null
    }
  }, [])

  const startPolling = useCallback(() => {
    stopPolling()
    pollTimer.current = setInterval(async () => {
      try {
        const { data } = await fetchCleanupStatus()
        setCleanupStatus(data)
        if (data.status !== 'running') {
          stopPolling()
          if (data.status === 'done') {
            const total = TABLES.reduce((acc, t) => acc + (data.deleted?.[t] || 0), 0)
            const partitions = data.dropped_partitions?.length || 0
            toast.success(
              `Cleanup finished: ${total.toLocaleString()} rows deleted` +
                (partitions ? `, ${partitions} partition(s) dropped` : ''),
            )
            setPreview(null)
          } else if (data.status === 'error') {
            toast.error(`Cleanup failed: ${data.error || 'unknown error'}`)
          }
        }
      } catch {
        // transient polling error — keep trying
      }
    }, POLL_INTERVAL_MS)
  }, [stopPolling])

  // Pick up an already-running cleanup after a page reload
  useEffect(() => {
    fetchCleanupStatus()
      .then(({ data }) => {
        setCleanupStatus(data)
        if (data.status === 'running') startPolling()
      })
      .catch(() => {})
    return stopPolling
  }, [startPolling, stopPolling])

  const loadPreview = async () => {
    if (retentionHours < 1) {
      toast.error('Retention must be at least 1 hour')
      return
    }
    setPreviewLoading(true)
    try {
      const { data } = await fetchCleanupPreview(retentionHours)
      setPreview(data)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to load preview')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleConfirmDelete = async () => {
    try {
      await runCleanup(retentionHours, TABLES)
      setConfirmOpen(false)
      setCleanupStatus({ status: 'running', deleted: {} })
      startPolling()
      toast.info('Cleanup started in background')
    } catch (err: any) {
      if (err.response?.status === 409) {
        setConfirmOpen(false)
        startPolling()
        toast.info('Cleanup is already running')
      } else {
        toast.error(err.response?.data?.detail || 'Cleanup failed to start')
      }
    }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Trash2 className="h-4 w-4" />
            Maintenance
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Permanently delete request logs and load test results older than the
            selected retention window. Stats covering the kept window remain intact.
            Old request-log partitions are dropped instantly; the rest is deleted in
            background chunks.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={presetIdx} onValueChange={(v) => { setPresetIdx(v); setPreview(null) }}>
              <SelectTrigger className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PRESETS.map((p, i) => (
                  <SelectItem key={i} value={String(i)}>Keep {p.label.toLowerCase()}</SelectItem>
                ))}
                <SelectItem value="custom">Custom hours</SelectItem>
              </SelectContent>
            </Select>
            {isCustom && (
              <Input
                type="number"
                min={1}
                max={8760}
                value={customHours}
                onChange={(e) => { setCustomHours(Number(e.target.value)); setPreview(null) }}
                placeholder="Hours"
                className="w-32"
              />
            )}
            <Button variant="outline" onClick={loadPreview} disabled={previewLoading}>
              {previewLoading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
              Preview
            </Button>
            <Button
              variant="destructive"
              onClick={() => setConfirmOpen(true)}
              disabled={!preview || totalToDelete === 0 || running}
            >
              {running ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Trash2 className="h-4 w-4 mr-1" />}
              {running ? 'Cleaning...' : 'Delete now'}
            </Button>
          </div>
          {running && (
            <div className="text-sm border rounded p-3 bg-muted/40 space-y-1">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                Cleanup running — {totalDeleted.toLocaleString()} rows deleted so far
                {cleanupStatus?.dropped_partitions?.length
                  ? `, ${cleanupStatus.dropped_partitions.length} partition(s) dropped`
                  : ''}
              </div>
            </div>
          )}
          {preview && !running && (
            <div className="text-sm border rounded p-3 bg-muted/40 space-y-1">
              <div className="text-muted-foreground">
                Cutoff: <span className="font-mono">{new Date(preview.cutoff).toLocaleString()}</span>
              </div>
              {TABLES.map((t) => (
                <div key={t} className="flex justify-between">
                  <span>{t}</span>
                  <span className="font-mono">
                    {preview.approximate?.[t] ? '~' : ''}
                    {(preview.counts[t] || 0).toLocaleString()}
                  </span>
                </div>
              ))}
              <div className="flex justify-between border-t pt-1 mt-1 font-medium">
                <span>Total</span>
                <span className="font-mono">
                  {hasApproximate ? '~' : ''}
                  {totalToDelete.toLocaleString()}
                </span>
              </div>
              {hasApproximate && (
                <div className="text-xs text-muted-foreground">
                  ~ — approximate (table too large for an exact count)
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Confirm deletion
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-2 text-sm">
            <p>
              This will permanently delete{' '}
              <span className="font-mono font-semibold">
                {hasApproximate ? '~' : ''}
                {totalToDelete.toLocaleString()}
              </span>{' '}
              row(s) from all listed tables. The cleanup runs in the background.
              This action cannot be undone.
            </p>
            <p className="text-muted-foreground">
              Cutoff: {preview ? new Date(preview.cutoff).toLocaleString() : '—'}
            </p>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleConfirmDelete}>
              <Trash2 className="h-4 w-4 mr-1" />
              Start cleanup
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
