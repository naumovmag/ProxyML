import { useState, useEffect } from 'react'
import { checkAllServicesHealth, fetchServices, HealthReport, Service } from '@/api/services'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, XCircle, Loader2, RefreshCw, AlertCircle, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { fetchSettings, SystemSettings } from '@/api/settings'
import { aiDiagnoseHealth } from '@/api/ai'

export default function HealthPage() {
  const [report, setReport] = useState<HealthReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [checkedAt, setCheckedAt] = useState<Date | null>(null)
  const [services, setServices] = useState<Service[]>([])
  const [aiSettings, setAiSettings] = useState<SystemSettings | null>(null)
  const [diagnoses, setDiagnoses] = useState<Record<string, { loading: boolean; text?: string }>>({})

  useEffect(() => {
    fetchSettings().then((r) => setAiSettings(r.data)).catch(() => {})
    fetchServices().then((r) => setServices(r.data)).catch(() => {})
  }, [])

  const handleDiagnose = async (item: HealthReport['items'][0]) => {
    const svc = services.find((s) => s.id === item.service_id)
    setDiagnoses((prev) => ({ ...prev, [item.service_id]: { loading: true } }))
    try {
      const { data } = await aiDiagnoseHealth({
        name: item.service_name,
        service_type: svc?.service_type || 'custom',
        base_url: svc?.base_url || '',
        health_check_path: svc?.health_check_path,
        health_check_method: svc?.health_check_method || 'GET',
        status: item.status,
        detail: item.detail,
        response_time_ms: item.response_time_ms,
      })
      setDiagnoses((prev) => ({ ...prev, [item.service_id]: { loading: false, text: data.text } }))
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Diagnosis failed')
      setDiagnoses((prev) => ({ ...prev, [item.service_id]: { loading: false } }))
    }
  }

  const handleCheck = async () => {
    setLoading(true)
    try {
      const { data } = await checkAllServicesHealth()
      setReport(data)
      setCheckedAt(new Date())
    } catch {
      toast.error('Failed to check services')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Health Check</h2>
          {checkedAt && (
            <p className="text-sm text-muted-foreground mt-1">
              Last check: {checkedAt.toLocaleTimeString()}
            </p>
          )}
        </div>
        <Button onClick={handleCheck} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
          {report ? 'Recheck All' : 'Check All Services'}
        </Button>
      </div>

      {!report && !loading && (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            Click "Check All Services" to run health checks on all configured services.
          </CardContent>
        </Card>
      )}

      {loading && !report && (
        <Card>
          <CardContent className="p-12 flex items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
            Checking all services...
          </CardContent>
        </Card>
      )}

      {report && (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-bold">{report.total}</div>
                <div className="text-sm text-muted-foreground mt-1">Total</div>
              </CardContent>
            </Card>
            <Card className="border-green-500/30">
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-bold text-green-500">{report.healthy}</div>
                <div className="text-sm text-muted-foreground mt-1">Healthy</div>
              </CardContent>
            </Card>
            <Card className="border-red-500/30">
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-bold text-red-500">{report.unhealthy}</div>
                <div className="text-sm text-muted-foreground mt-1">Unhealthy</div>
              </CardContent>
            </Card>
            <Card className="border-yellow-500/30">
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-bold text-yellow-500">{report.unconfigured}</div>
                <div className="text-sm text-muted-foreground mt-1">No health path</div>
              </CardContent>
            </Card>
          </div>

          {/* Service list */}
          <div className="space-y-2">
            {report.items.map((item) => (
              <Card
                key={item.service_id}
                className={
                  item.status === 'ok' ? 'border-green-500/30' :
                  item.status === 'error' ? 'border-red-500/30' : 'border-yellow-500/30'
                }
              >
                <CardContent className="py-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {item.status === 'ok' ? (
                        <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
                      ) : item.status === 'error' ? (
                        <XCircle className="h-5 w-5 text-red-500 shrink-0" />
                      ) : (
                        <AlertCircle className="h-5 w-5 text-yellow-500 shrink-0" />
                      )}
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{item.service_name}</span>
                          {!item.is_active && <Badge variant="secondary">Inactive</Badge>}
                        </div>
                        <div className="text-xs text-muted-foreground font-mono">/proxy/{item.slug}/</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className={`text-sm font-medium ${
                          item.status === 'ok' ? 'text-green-500' :
                          item.status === 'error' ? 'text-red-500' : 'text-yellow-500'
                        }`}>
                          {item.detail || item.status}
                        </div>
                        {item.response_time_ms != null && (
                          <div className="text-xs text-muted-foreground">{item.response_time_ms} ms</div>
                        )}
                      </div>
                      {aiSettings?.ai_enabled && item.status === 'error' && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDiagnose(item)}
                          disabled={diagnoses[item.service_id]?.loading}
                        >
                          {diagnoses[item.service_id]?.loading
                            ? <Loader2 className="h-3 w-3 animate-spin mr-1" />
                            : <Sparkles className="h-3 w-3 mr-1" />
                          }
                          Diagnose
                        </Button>
                      )}
                    </div>
                  </div>
                  {diagnoses[item.service_id]?.text && (
                    <div className="text-sm bg-muted rounded p-3 ml-8 whitespace-pre-wrap">
                      {diagnoses[item.service_id].text}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
