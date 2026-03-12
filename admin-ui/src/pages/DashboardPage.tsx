import { useEffect, useState } from 'react'
import { fetchServices, Service } from '@/api/services'
import { fetchApiKeys, ApiKey } from '@/api/apiKeys'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Server, Key, Activity, Zap } from 'lucide-react'

export default function DashboardPage() {
  const [services, setServices] = useState<Service[]>([])
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])

  useEffect(() => {
    fetchServices().then((r) => setServices(r.data))
    fetchApiKeys().then((r) => setApiKeys(r.data))
  }, [])

  const activeServices = services.filter((s) => s.is_active).length
  const activeKeys = apiKeys.filter((k) => k.is_active).length
  const streamingServices = services.filter((s) => s.supports_streaming).length

  const stats = [
    { label: 'Total Services', value: services.length, icon: Server },
    { label: 'Active Services', value: activeServices, icon: Activity },
    { label: 'API Keys', value: activeKeys, icon: Key },
    { label: 'Streaming', value: streamingServices, icon: Zap },
  ]

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{stat.label}</CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
