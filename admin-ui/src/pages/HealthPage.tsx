import { useState } from 'react'
import { checkAllServicesHealth, HealthReport } from '@/api/services'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, XCircle, Loader2, RefreshCw, AlertCircle } from 'lucide-react'
import { toast } from 'sonner'

export default function HealthPage() {
  const [report, setReport] = useState<HealthReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [checkedAt, setCheckedAt] = useState<Date | null>(null)

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
                <CardContent className="flex items-center justify-between py-3">
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
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
