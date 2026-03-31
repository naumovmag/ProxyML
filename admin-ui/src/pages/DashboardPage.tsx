import { useEffect, useState } from 'react'
import { fetchServices, Service } from '@/api/services'
import { fetchApiKeys, ApiKey } from '@/api/apiKeys'
import { fetchStatsOverview, fetchStatsByService, fetchStatsByKey, fetchRecentLogs, fetchTimeseries, fetchStatusBreakdown, StatsOverview, ServiceStats, KeyStats, RecentLog, LogFilters, TimeseriesPoint, StatusBreakdown } from '@/api/stats'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Server, Key, Zap, BarChart3, Clock, AlertTriangle, ArrowUpDown, X, Sparkles, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { RequestsOverTimeChart, LatencyOverTimeChart, StatusCodeDonut, ServiceBarChart, KeyUsageBarChart } from '@/components/charts'
import { fetchSettings, SystemSettings } from '@/api/settings'
import { aiSummarizeDashboard, aiAnalyzeError } from '@/api/ai'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

export default function DashboardPage() {
  const [services, setServices] = useState<Service[]>([])
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [overview, setOverview] = useState<StatsOverview | null>(null)
  const [byService, setByService] = useState<ServiceStats[]>([])
  const [byKey, setByKey] = useState<KeyStats[]>([])
  const [recentLogs, setRecentLogs] = useState<RecentLog[]>([])
  const [hours, setHours] = useState(24)
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([])
  const [statusBreakdown, setStatusBreakdown] = useState<StatusBreakdown[]>([])
  const [filters, setFilters] = useState<LogFilters>({})
  const [logsLimit, setLogsLimit] = useState(50)

  const loadLogs = () => {
    fetchRecentLogs(logsLimit, filters).then((r) => setRecentLogs(r.data)).catch(() => {})
  }

  const load = () => {
    fetchServices().then((r) => setServices(r.data))
    fetchApiKeys().then((r) => setApiKeys(r.data))
    fetchStatsOverview(hours).then((r) => setOverview(r.data)).catch(() => {})
    fetchStatsByService(hours).then((r) => setByService(r.data)).catch(() => {})
    fetchStatsByKey(hours).then((r) => setByKey(r.data)).catch(() => {})
    fetchTimeseries(hours).then((r) => setTimeseries(r.data)).catch(() => {})
    fetchStatusBreakdown(hours).then((r) => setStatusBreakdown(r.data)).catch(() => {})
    loadLogs()
  }

  useEffect(() => { load() }, [hours])
  useEffect(() => { loadLogs() }, [filters, logsLimit])

  const [selectedLog, setSelectedLog] = useState<RecentLog | null>(null)

  // AI
  const [aiSettings, setAiSettings] = useState<SystemSettings | null>(null)
  const [aiSummary, setAiSummary] = useState<string | null>(null)
  const [aiSummaryLoading, setAiSummaryLoading] = useState(false)
  const [aiErrorAnalysis, setAiErrorAnalysis] = useState<string | null>(null)
  const [aiErrorLoading, setAiErrorLoading] = useState(false)

  useEffect(() => {
    fetchSettings().then((r) => setAiSettings(r.data)).catch(() => {})
  }, [])

  const handleAiSummary = async () => {
    if (!overview) return
    setAiSummaryLoading(true)
    setAiSummary(null)
    try {
      const { data } = await aiSummarizeDashboard({
        period_hours: hours,
        total_requests: overview.total_requests,
        total_errors: overview.total_errors,
        error_rate: overview.total_requests > 0 ? (overview.total_errors / overview.total_requests) * 100 : 0,
        avg_duration_ms: overview.avg_duration_ms,
        total_request_bytes: overview.total_request_bytes,
        total_response_bytes: overview.total_response_bytes,
        by_service: byService,
        by_key: [],
      })
      setAiSummary(data.text)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'AI summary failed')
    } finally {
      setAiSummaryLoading(false)
    }
  }

  const handleAiAnalyzeError = async (log: RecentLog) => {
    setAiErrorLoading(true)
    setAiErrorAnalysis(null)
    try {
      const { data } = await aiAnalyzeError({
        service_slug: log.service_slug,
        method: log.method,
        path: log.path,
        status_code: log.status_code,
        duration_ms: log.duration_ms,
        error: log.error,
        is_streaming: log.is_streaming,
        is_fallback: log.is_fallback,
      })
      setAiErrorAnalysis(data.text)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'AI analysis failed')
    } finally {
      setAiErrorLoading(false)
    }
  }

  const activeServices = services.filter((s) => s.is_active).length
  const activeKeys = apiKeys.filter((k) => k.is_active).length

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <Select value={String(hours)} onValueChange={(v) => setHours(Number(v))}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="1">Last 1 hour</SelectItem>
            <SelectItem value="6">Last 6 hours</SelectItem>
            <SelectItem value="24">Last 24 hours</SelectItem>
            <SelectItem value="168">Last 7 days</SelectItem>
            <SelectItem value="720">Last 30 days</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Request Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Requests</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{overview?.total_requests ?? '-'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Errors</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{overview?.total_errors ?? '-'}</div>
            {overview && overview.total_requests > 0 && (
              <p className="text-xs text-muted-foreground">
                {((overview.total_errors / overview.total_requests) * 100).toFixed(1)}% error rate
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Avg Latency</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{overview ? `${overview.avg_duration_ms}ms` : '-'}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Traffic</CardTitle>
            <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              {overview ? formatBytes(overview.total_request_bytes + overview.total_response_bytes) : '-'}
            </div>
            {overview && (
              <p className="text-xs text-muted-foreground">
                {formatBytes(overview.total_request_bytes)} in / {formatBytes(overview.total_response_bytes)} out
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Infrastructure */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Services</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeServices}<span className="text-sm text-muted-foreground font-normal"> / {services.length}</span></div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">API Keys</CardTitle>
            <Key className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeKeys}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Streaming</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{services.filter((s) => s.supports_streaming).length}</div>
          </CardContent>
        </Card>
      </div>

      {/* AI Summary */}
      {aiSettings?.ai_enabled && overview && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              AI Insights
            </CardTitle>
            <Button variant="outline" size="sm" onClick={handleAiSummary} disabled={aiSummaryLoading}>
              {aiSummaryLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Sparkles className="h-4 w-4 mr-1" />}
              {aiSummary ? 'Refresh' : 'Analyze'}
            </Button>
          </CardHeader>
          {aiSummary && (
            <CardContent>
              <div className="text-sm whitespace-pre-wrap">{aiSummary}</div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Charts */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Requests Over Time</CardTitle>
        </CardHeader>
        <CardContent>
          <RequestsOverTimeChart data={timeseries} hours={hours} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Latency Over Time</CardTitle>
          </CardHeader>
          <CardContent>
            <LatencyOverTimeChart data={timeseries} hours={hours} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Status Codes</CardTitle>
          </CardHeader>
          <CardContent>
            <StatusCodeDonut data={statusBreakdown} />
          </CardContent>
        </Card>
      </div>

      {/* Requests by Service & Key Usage */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Requests by Service</CardTitle>
          </CardHeader>
          <CardContent>
            <ServiceBarChart data={byService} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Usage by API Key</CardTitle>
          </CardHeader>
          <CardContent>
            <KeyUsageBarChart data={byKey} />
          </CardContent>
        </Card>
      </div>

      {/* Recent Logs */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Recent Requests</CardTitle>
              <Select value={String(logsLimit)} onValueChange={(v) => setLogsLimit(Number(v))}>
                <SelectTrigger className="w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="30">30</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                  <SelectItem value="200">200</SelectItem>
                  <SelectItem value="500">500</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <Select value={filters.service_slug || '_all'} onValueChange={(v) => setFilters((f) => ({ ...f, service_slug: v === '_all' ? undefined : v }))}>
                <SelectTrigger className="w-44">
                  <SelectValue placeholder="All services" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">All services</SelectItem>
                  {services.map((s) => <SelectItem key={s.slug} value={s.slug}>{s.name}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={filters.method || '_all'} onValueChange={(v) => setFilters((f) => ({ ...f, method: v === '_all' ? undefined : v }))}>
                <SelectTrigger className="w-28">
                  <SelectValue placeholder="Method" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">All methods</SelectItem>
                  <SelectItem value="GET">GET</SelectItem>
                  <SelectItem value="POST">POST</SelectItem>
                  <SelectItem value="PUT">PUT</SelectItem>
                  <SelectItem value="DELETE">DELETE</SelectItem>
                  <SelectItem value="PATCH">PATCH</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filters.status || '_all'} onValueChange={(v) => setFilters((f) => ({ ...f, status: v === '_all' ? undefined : v }))}>
                <SelectTrigger className="w-28">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">All status</SelectItem>
                  <SelectItem value="ok">Success</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filters.source || '_all'} onValueChange={(v) => setFilters((f) => ({ ...f, source: v === '_all' ? undefined : v }))}>
                <SelectTrigger className="w-28">
                  <SelectValue placeholder="Source" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">All source</SelectItem>
                  <SelectItem value="cache">Cache</SelectItem>
                  <SelectItem value="origin">Origin</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filters.api_key_name || '_all'} onValueChange={(v) => setFilters((f) => ({ ...f, api_key_name: v === '_all' ? undefined : v }))}>
                <SelectTrigger className="w-36">
                  <SelectValue placeholder="All keys" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">All keys</SelectItem>
                  {apiKeys.map((k) => <SelectItem key={k.id} value={k.name}>{k.name}</SelectItem>)}
                </SelectContent>
              </Select>
              {Object.values(filters).some(Boolean) && (
                <Button variant="ghost" size="sm" onClick={() => setFilters({})}>
                  <X className="h-4 w-4 mr-1" />Reset
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 pr-4">Time</th>
                    <th className="pb-2 pr-4">Service</th>
                    <th className="pb-2 pr-4">Method</th>
                    <th className="pb-2 pr-4">Path</th>
                    <th className="pb-2 pr-4">Status</th>
                    <th className="pb-2 pr-4">Duration</th>
                    <th className="pb-2 pr-4">Source</th>
                    <th className="pb-2">Key</th>
                  </tr>
                </thead>
                <tbody>
                  {recentLogs.map((log) => (
                    <tr key={log.id} className="border-b border-border/50 hover:bg-muted/50 cursor-pointer" onClick={() => setSelectedLog(log)}>
                      <td className="py-2 pr-4 text-muted-foreground whitespace-nowrap">
                        {new Date(log.created_at).toLocaleTimeString()}
                      </td>
                      <td className="py-2 pr-4 font-medium">{log.service_slug}</td>
                      <td className="py-2 pr-4">
                        <Badge variant="outline" className="text-xs">{log.method}</Badge>
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground max-w-[200px] truncate">{log.path}</td>
                      <td className="py-2 pr-4">
                        <Badge variant={log.status_code < 400 ? 'success' : 'destructive'}>
                          {log.status_code}
                        </Badge>
                      </td>
                      <td className="py-2 pr-4 whitespace-nowrap">{log.duration_ms}ms</td>
                      <td className="py-2 pr-4 space-x-1">
                        {log.is_cached ? (
                          <Badge variant="outline" className="text-xs text-green-500 border-green-500/30">cache</Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">origin</span>
                        )}
                        {log.is_fallback && (
                          <Badge variant="outline" className="text-xs text-orange-500 border-orange-500/30">fallback</Badge>
                        )}
                      </td>
                      <td className="py-2 text-muted-foreground">{log.api_key_name || '-'}</td>
                    </tr>
                  ))}
                  {recentLogs.length === 0 && (
                    <tr><td colSpan={8} className="py-8 text-center text-muted-foreground">No requests found</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

      {/* Request Detail Dialog */}
      <Dialog open={!!selectedLog} onOpenChange={(open) => { if (!open) { setSelectedLog(null); setAiErrorAnalysis(null) } }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Request Details</DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-muted-foreground">Time</span>
                  <div className="font-medium">{new Date(selectedLog.created_at).toLocaleString()}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Service</span>
                  <div className="font-medium">{selectedLog.service_slug}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Method</span>
                  <div><Badge variant="outline">{selectedLog.method}</Badge></div>
                </div>
                <div>
                  <span className="text-muted-foreground">Status</span>
                  <div>
                    <Badge variant={selectedLog.status_code < 400 ? 'success' : 'destructive'}>
                      {selectedLog.status_code}
                    </Badge>
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground">Duration</span>
                  <div className="font-medium">{selectedLog.duration_ms} ms</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Streaming</span>
                  <div className="font-medium">{selectedLog.is_streaming ? 'Yes' : 'No'}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Request Size</span>
                  <div className="font-medium">{formatBytes(selectedLog.request_size)}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Response Size</span>
                  <div className="font-medium">{formatBytes(selectedLog.response_size)}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">API Key</span>
                  <div className="font-medium">{selectedLog.api_key_name || '-'}</div>
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">Path</span>
                <div className="font-mono text-xs bg-muted rounded p-2 mt-1 break-all">{selectedLog.path}</div>
              </div>
              {selectedLog.is_fallback && (
                <div>
                  <span className="text-muted-foreground">Fallback</span>
                  <div className="text-sm mt-1">
                    <Badge variant="outline" className="text-orange-500 border-orange-500/30">
                      Fallback from {selectedLog.fallback_from_slug}
                    </Badge>
                  </div>
                </div>
              )}
              {selectedLog.error && (
                <div>
                  <span className="text-muted-foreground">Error</span>
                  <div className="font-mono text-xs bg-destructive/10 text-destructive rounded p-2 mt-1 break-all">{selectedLog.error}</div>
                </div>
              )}
              {aiSettings?.ai_enabled && selectedLog.status_code >= 400 && (
                <div className="pt-2 border-t">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-muted-foreground flex items-center gap-1">
                      <Sparkles className="h-3.5 w-3.5" /> AI Analysis
                    </span>
                    <Button variant="outline" size="sm" onClick={() => handleAiAnalyzeError(selectedLog)} disabled={aiErrorLoading}>
                      {aiErrorLoading ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Sparkles className="h-3 w-3 mr-1" />}
                      {aiErrorAnalysis ? 'Retry' : 'Analyze'}
                    </Button>
                  </div>
                  {aiErrorAnalysis && (
                    <div className="text-sm bg-muted rounded p-3 whitespace-pre-wrap">{aiErrorAnalysis}</div>
                  )}
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
