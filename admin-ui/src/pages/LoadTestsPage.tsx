import { useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { Plus, Play, Square, Trash2, Edit, BarChart3, Loader2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import {
  fetchLoadTests,
  createLoadTest,
  updateLoadTest,
  deleteLoadTest,
  startLoadTest,
  stopLoadTest,
  fetchLoadTestResults,
  fetchLoadTestStats,
  clearLoadTestResults,
  type LoadTestTask,
  type LoadTestTaskCreate,
  type LoadTestTaskUpdate,
  type LoadTestResult,
  type LoadTestStats,
} from '@/api/loadTests'
import { fetchServices, type Service } from '@/api/services'

const INTERVAL_OPTIONS = [
  { value: '5', label: '5s' },
  { value: '10', label: '10s' },
  { value: '30', label: '30s' },
  { value: '60', label: '1m' },
  { value: '120', label: '2m' },
  { value: '300', label: '5m' },
  { value: '600', label: '10m' },
]

const DEFAULT_PAYLOADS: Record<string, { path: string; body: string }> = {
  llm_chat: {
    path: 'v1/chat/completions',
    body: JSON.stringify({ messages: [{ role: 'user', content: 'Say ok' }], max_tokens: 800 }, null, 2),
  },
  embedding: {
    path: 'v1/embeddings',
    body: JSON.stringify({ input: 'test' }, null, 2),
  },
}

export default function LoadTestsPage() {
  const [tasks, setTasks] = useState<LoadTestTask[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [loading, setLoading] = useState(true)

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingTask, setEditingTask] = useState<LoadTestTask | null>(null)
  const [formServiceId, setFormServiceId] = useState('')
  const [formName, setFormName] = useState('')
  const [formInterval, setFormInterval] = useState('60')
  const [formMaxRuns, setFormMaxRuns] = useState('')
  const [formPath, setFormPath] = useState('')
  const [formBody, setFormBody] = useState('')
  const [formMaxTokens, setFormMaxTokens] = useState('800')
  const [formSaving, setFormSaving] = useState(false)

  // Results dialog
  const [resultsTaskId, setResultsTaskId] = useState<string | null>(null)
  const [results, setResults] = useState<LoadTestResult[]>([])
  const [stats, setStats] = useState<LoadTestStats | null>(null)
  const [expandedResultId, setExpandedResultId] = useState<string | null>(null)
  const [resultsLoading, setResultsLoading] = useState(false)

  // Confirm dialog
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmAction, setConfirmAction] = useState<(() => Promise<void>) | null>(null)
  const [confirmMessage, setConfirmMessage] = useState('')

  const loadTasks = useCallback(async () => {
    try {
      const res = await fetchLoadTests()
      setTasks(res.data)
    } catch {
      toast.error('Failed to load tasks')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadServices = useCallback(async () => {
    try {
      const res = await fetchServices()
      setServices(res.data)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    loadTasks()
    loadServices()
  }, [loadTasks, loadServices])

  // Auto-refresh running tasks
  useEffect(() => {
    const hasRunning = tasks.some((t) => t.status === 'running')
    if (!hasRunning) return
    const interval = setInterval(loadTasks, 5000)
    return () => clearInterval(interval)
  }, [tasks, loadTasks])

  const openCreate = () => {
    setEditingTask(null)
    setFormServiceId('')
    setFormName('')
    setFormInterval('60')
    setFormMaxRuns('')
    setFormPath('')
    setFormBody('')
    setFormMaxTokens('800')
    setDialogOpen(true)
  }

  const openEdit = (task: LoadTestTask) => {
    setEditingTask(task)
    setFormServiceId(task.service_id)
    setFormName(task.name)
    setFormInterval(String(task.interval_seconds))
    setFormMaxRuns(task.max_runs ? String(task.max_runs) : '')
    setFormPath(task.test_path)
    const body = task.test_body ? { ...task.test_body } : null
    const maxTokens = body?.max_tokens
    if (body) delete body.max_tokens
    setFormBody(body && Object.keys(body).length > 0 ? JSON.stringify(body, null, 2) : '')
    setFormMaxTokens(maxTokens ? String(maxTokens) : '800')
    setDialogOpen(true)
  }

  const handleServiceChange = (serviceId: string) => {
    setFormServiceId(serviceId)
    const svc = services.find((s) => s.id === serviceId)
    if (svc && !editingTask) {
      const defaults = DEFAULT_PAYLOADS[svc.service_type]
      if (defaults) {
        setFormPath(defaults.path)
        setFormBody(defaults.body)
      } else {
        setFormPath('')
        setFormBody('')
      }
    }
  }

  const handleSave = async () => {
    if (!formServiceId || !formName) {
      toast.error('Service and name are required')
      return
    }
    setFormSaving(true)
    try {
      let parsedBody: Record<string, unknown> | null = null
      if (formBody.trim()) {
        try {
          parsedBody = JSON.parse(formBody)
        } catch {
          toast.error('Invalid JSON body')
          setFormSaving(false)
          return
        }
      }
      if (formMaxTokens && Number(formMaxTokens) > 0) {
        parsedBody = { ...(parsedBody || {}), max_tokens: Number(formMaxTokens) }
      }

      if (editingTask) {
        const data: LoadTestTaskUpdate = {
          name: formName,
          interval_seconds: Number(formInterval),
          test_path: formPath,
          test_body: parsedBody,
          max_runs: formMaxRuns ? Number(formMaxRuns) : undefined,
        }
        await updateLoadTest(editingTask.id, data)
        toast.success('Task updated')
      } else {
        const data: LoadTestTaskCreate = {
          service_id: formServiceId,
          name: formName,
          interval_seconds: Number(formInterval),
          test_path: formPath || undefined,
          test_body: parsedBody,
          max_runs: formMaxRuns ? Number(formMaxRuns) : undefined,
        }
        await createLoadTest(data)
        toast.success('Task created')
      }
      setDialogOpen(false)
      loadTasks()
    } catch (e: any) {
      const detail = e.response?.data?.detail
      const msg = Array.isArray(detail) ? detail.map((d: any) => d.msg).join(', ') : detail || 'Failed to save'
      toast.error(msg)
    } finally {
      setFormSaving(false)
    }
  }

  const handleStart = async (id: string) => {
    try {
      await startLoadTest(id)
      toast.success('Task started')
      loadTasks()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Failed to start')
    }
  }

  const handleStop = async (id: string) => {
    try {
      await stopLoadTest(id)
      toast.success('Task stopped')
      loadTasks()
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Failed to stop')
    }
  }

  const handleDelete = (id: string) => {
    setConfirmMessage('Delete this load test task and all its results?')
    setConfirmAction(() => async () => {
      try {
        await deleteLoadTest(id)
        toast.success('Task deleted')
        loadTasks()
      } catch (e: any) {
        toast.error(e.response?.data?.detail || 'Failed to delete')
      }
    })
    setConfirmOpen(true)
  }

  const openResults = async (taskId: string) => {
    setResultsTaskId(taskId)
    setResultsLoading(true)
    try {
      const [resResults, resStats] = await Promise.all([
        fetchLoadTestResults(taskId, 100),
        fetchLoadTestStats(taskId),
      ])
      setResults(resResults.data)
      setStats(resStats.data)
    } catch {
      toast.error('Failed to load results')
    } finally {
      setResultsLoading(false)
    }
  }

  const handleClearResults = (taskId: string) => {
    setConfirmMessage('Clear all results for this task?')
    setConfirmAction(() => async () => {
      try {
        await clearLoadTestResults(taskId)
        toast.success('Results cleared')
        setResults([])
        setStats(null)
        loadTasks()
      } catch {
        toast.error('Failed to clear results')
      }
    })
    setConfirmOpen(true)
  }

  const getServiceName = (serviceId: string) => {
    return services.find((s) => s.id === serviceId)?.name || serviceId.slice(0, 8)
  }

  const formatInterval = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`
    return `${Math.floor(seconds / 60)}m`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Load Tests</h1>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" /> Create
        </Button>
      </div>

      {tasks.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No load test tasks yet. Create one to start testing your services.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {tasks.map((task) => (
            <Card key={task.id}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-lg">{task.name}</span>
                      <Badge variant={task.status === 'running' ? 'default' : 'secondary'}>
                        {task.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <span>Service: {getServiceName(task.service_id)}</span>
                      <span>Interval: {formatInterval(task.interval_seconds)}</span>
                      <span>Runs: {task.total_runs}{task.max_runs ? ` / ${task.max_runs}` : ''}</span>
                      {task.last_run_at && (
                        <span>Last: {new Date(task.last_run_at).toLocaleTimeString()}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {task.status === 'running' ? (
                      <Button variant="outline" size="sm" onClick={() => handleStop(task.id)}>
                        <Square className="h-4 w-4 mr-1" /> Stop
                      </Button>
                    ) : (
                      <Button variant="outline" size="sm" onClick={() => handleStart(task.id)}>
                        <Play className="h-4 w-4 mr-1" /> Start
                      </Button>
                    )}
                    <Button variant="outline" size="sm" onClick={() => openResults(task.id)}>
                      <BarChart3 className="h-4 w-4 mr-1" /> Results
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEdit(task)}
                      disabled={task.status === 'running'}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => handleDelete(task.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingTask ? 'Edit Load Test' : 'Create Load Test'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {editingTask ? (
              <div className="space-y-2">
                <Label>Service</Label>
                <Input value={`${getServiceName(editingTask.service_id)} (${editingTask.service_type})`} disabled />
              </div>
            ) : (
              <div className="space-y-2">
                <Label>Service</Label>
                <Select value={formServiceId} onValueChange={handleServiceChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select service" />
                  </SelectTrigger>
                  <SelectContent>
                    {services.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name} ({s.service_type})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="e.g. GPT-4 latency test" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Interval</Label>
                <Select value={formInterval} onValueChange={setFormInterval}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {INTERVAL_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Max runs (optional)</Label>
                <Input
                  type="number"
                  value={formMaxRuns}
                  onChange={(e) => setFormMaxRuns(e.target.value)}
                  placeholder="Unlimited"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Test path</Label>
              <Input value={formPath} onChange={(e) => setFormPath(e.target.value)} placeholder="v1/chat/completions" />
              </div>
              <div className="space-y-2">
                <Label>Max tokens</Label>
                <Input
                  type="number"
                  value={formMaxTokens}
                  onChange={(e) => setFormMaxTokens(e.target.value)}
                  placeholder="800"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Test body (JSON)</Label>
              <Textarea
                value={formBody}
                onChange={(e) => setFormBody(e.target.value)}
                placeholder="{}"
                rows={6}
                className="font-mono text-sm"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={formSaving}>
                {formSaving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {editingTask ? 'Save' : 'Create'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Results Dialog */}
      <Dialog open={!!resultsTaskId} onOpenChange={(open) => !open && setResultsTaskId(null)}>
        <DialogContent className="sm:max-w-3xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between">
              <span>Results</span>
              {resultsTaskId && (
                <Button variant="outline" size="sm" onClick={() => handleClearResults(resultsTaskId)}>
                  <Trash2 className="h-4 w-4 mr-1" /> Clear
                </Button>
              )}
            </DialogTitle>
          </DialogHeader>

          {resultsLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : (
            <div className="space-y-4">
              {stats && stats.total > 0 && (
                <div className="grid grid-cols-4 gap-3">
                  <Card>
                    <CardContent className="py-3 text-center">
                      <div className="text-2xl font-bold">{stats.avg_duration_ms ?? '-'}ms</div>
                      <div className="text-xs text-muted-foreground">Avg latency</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="py-3 text-center">
                      <div className="text-2xl font-bold">{stats.p95_duration_ms ?? '-'}ms</div>
                      <div className="text-xs text-muted-foreground">p95 latency</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="py-3 text-center">
                      <div className="text-2xl font-bold">{stats.min_duration_ms ?? '-'} / {stats.max_duration_ms ?? '-'}ms</div>
                      <div className="text-xs text-muted-foreground">Min / Max</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="py-3 text-center">
                      <div className="text-2xl font-bold">{stats.error_rate ?? 0}%</div>
                      <div className="text-xs text-muted-foreground">Error rate ({stats.error_count}/{stats.total})</div>
                    </CardContent>
                  </Card>
                </div>
              )}

              {results.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No results yet</p>
              ) : (
                <div className="border rounded-md overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted">
                      <tr>
                        <th className="px-3 py-2 text-left">Time</th>
                        <th className="px-3 py-2 text-left">Status</th>
                        <th className="px-3 py-2 text-left">Duration</th>
                        <th className="px-3 py-2 text-left">Size</th>
                        <th className="px-3 py-2 text-left">Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.map((r) => (
                        <>
                          <tr
                            key={r.id}
                            className="border-t cursor-pointer hover:bg-muted/50"
                            onClick={() => setExpandedResultId(expandedResultId === r.id ? null : r.id)}
                          >
                            <td className="px-3 py-2 whitespace-nowrap">{new Date(r.created_at).toLocaleTimeString()}</td>
                            <td className="px-3 py-2">
                              <Badge variant={r.status_code >= 200 && r.status_code < 300 ? 'default' : 'destructive'}>
                                {r.status_code}
                              </Badge>
                            </td>
                            <td className="px-3 py-2">{r.duration_ms}ms</td>
                            <td className="px-3 py-2">{r.response_size}B</td>
                            <td className="px-3 py-2 text-destructive truncate max-w-[200px]">{r.error || '-'}</td>
                          </tr>
                          {expandedResultId === r.id && r.response_body && (
                            <tr key={`${r.id}-body`} className="border-t">
                              <td colSpan={5} className="px-3 py-2">
                                <pre className="text-xs bg-muted p-3 rounded-md overflow-auto max-h-[300px] whitespace-pre-wrap">
                                  {(() => {
                                    try { return JSON.stringify(JSON.parse(r.response_body), null, 2) } catch { return r.response_body }
                                  })()}
                                </pre>
                              </td>
                            </tr>
                          )}
                        </>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Confirm dialog */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Confirm"
        description={confirmMessage}
        onConfirm={async () => {
          if (confirmAction) await confirmAction()
          setConfirmOpen(false)
        }}
      />
    </div>
  )
}
