import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { fetchServices, Service } from '@/api/services'
import { fetchSettings } from '@/api/settings'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { FlaskConical, History, Zap } from 'lucide-react'
import { HistoryEntry } from '@/api/playground'
import ChatPlayground from '@/components/playground/ChatPlayground'
import EmbeddingPlayground from '@/components/playground/EmbeddingPlayground'
import SttPlayground from '@/components/playground/SttPlayground'
import TtsPlayground from '@/components/playground/TtsPlayground'
import CustomPlayground from '@/components/playground/CustomPlayground'
import QuickTestPlayground from '@/components/playground/QuickTestPlayground'
import HistoryPanel from '@/components/playground/HistoryPanel'

const TYPE_LABELS: Record<string, string> = {
  llm_chat: 'LLM Chat',
  embedding: 'Embedding',
  stt: 'Speech-to-Text',
  tts: 'Text-to-Speech',
  custom: 'Custom',
}

type Tab = 'playground' | 'quick-test' | 'history'

export default function PlaygroundPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const navServiceId = (location.state as { serviceId?: string } | null)?.serviceId
  const [services, setServices] = useState<Service[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('playground')
  const [replayEntry, setReplayEntry] = useState<HistoryEntry | null>(null)
  const [historyServiceFilter, setHistoryServiceFilter] = useState<string>('all')
  const [aiEnabled, setAiEnabled] = useState(false)

  useEffect(() => {
    fetchSettings().then(({ data }) => setAiEnabled(data.ai_enabled)).catch(() => {})
  }, [])

  useEffect(() => {
    fetchServices()
      .then(({ data }) => {
        const active = data.filter((s) => s.is_active)
        setServices(active)
        const initial = navServiceId && active.find((s) => s.id === navServiceId)
          ? navServiceId
          : active[0]?.id || ''
        if (!selectedId || navServiceId) {
          setSelectedId(initial)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [navServiceId])

  const selected = services.find((s) => s.id === selectedId)

  const handleReplay = (entry: HistoryEntry) => {
    if (entry.service_id) {
      setSelectedId(entry.service_id)
    }
    setReplayEntry(entry)
    setTab('playground')
  }

  const handleCreateServiceFromQuickTest = (params: {
    base_url: string
    auth_type: string
    auth_token?: string
    auth_header_name?: string
    default_model?: string
    supports_streaming?: boolean
    extra_headers?: Record<string, string>
  }) => {
    // Navigate to services page with pre-filled params
    navigate('/services', { state: { createService: params } })
  }

  const renderPlayground = () => {
    if (!selected) return null
    const replay = replayEntry
    const clearReplay = () => setReplayEntry(null)
    switch (selected.service_type) {
      case 'llm_chat':
        return <ChatPlayground service={selected} key={selected.id} replay={replay} onReplayConsumed={clearReplay} aiEnabled={aiEnabled} />
      case 'embedding':
        return <EmbeddingPlayground service={selected} key={selected.id} replay={replay} onReplayConsumed={clearReplay} aiEnabled={aiEnabled} />
      case 'stt':
        return <SttPlayground service={selected} key={selected.id} replay={replay} onReplayConsumed={clearReplay} />
      case 'tts':
        return <TtsPlayground service={selected} key={selected.id} replay={replay} onReplayConsumed={clearReplay} aiEnabled={aiEnabled} />
      default:
        return <CustomPlayground service={selected} key={selected.id} replay={replay} onReplayConsumed={clearReplay} aiEnabled={aiEnabled} />
    }
  }

  if (loading) {
    return <div className="text-center text-muted-foreground py-12">Loading services...</div>
  }

  return (
    <div>
      {/* Header with tabs */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <FlaskConical className="h-6 w-6" />
          <h2 className="text-2xl font-bold">Request Test</h2>
        </div>
        <div className="flex gap-1 bg-muted rounded-lg p-1">
          <Button
            variant={tab === 'playground' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setTab('playground')}
          >
            <FlaskConical className="h-4 w-4 mr-1" />
            Services
          </Button>
          <Button
            variant={tab === 'quick-test' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setTab('quick-test')}
          >
            <Zap className="h-4 w-4 mr-1" />
            Request Test
          </Button>
          <Button
            variant={tab === 'history' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setTab('history')}
          >
            <History className="h-4 w-4 mr-1" />
            History
          </Button>
        </div>
      </div>

      {/* Service selector — visible for playground and history tabs */}
      {tab === 'playground' && (
        <div className="flex items-center gap-4 mb-4">
          {services.length > 0 ? (
            <Select value={selectedId} onValueChange={setSelectedId}>
              <SelectTrigger className="w-80">
                <SelectValue placeholder="Select a service" />
              </SelectTrigger>
              <SelectContent>
                {services.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    <span className="flex items-center gap-2">
                      {s.name}
                      <span className="text-xs text-muted-foreground">
                        ({TYPE_LABELS[s.service_type] || s.service_type})
                      </span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <p className="text-sm text-muted-foreground">No active services. Use Request Test or add a service first.</p>
          )}

          {selected && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Badge variant="outline">{TYPE_LABELS[selected.service_type] || selected.service_type}</Badge>
              <span className="font-mono text-xs">{selected.base_url}</span>
              {selected.supports_streaming && <Badge variant="secondary">Streaming</Badge>}
              {selected.default_model && <Badge variant="secondary">{selected.default_model}</Badge>}
            </div>
          )}
        </div>
      )}

      {tab === 'history' && (
        <div className="flex items-center gap-4 mb-4">
          <Select value={historyServiceFilter} onValueChange={setHistoryServiceFilter}>
            <SelectTrigger className="w-80">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All services</SelectItem>
              {services.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  <span className="flex items-center gap-2">
                    {s.name}
                    <span className="text-xs text-muted-foreground">
                      ({TYPE_LABELS[s.service_type] || s.service_type})
                    </span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Content */}
      {tab === 'history' ? (
        <HistoryPanel
          serviceId={historyServiceFilter === 'all' ? undefined : historyServiceFilter}
          onReplay={handleReplay}
        />
      ) : tab === 'quick-test' ? (
        <QuickTestPlayground
          aiEnabled={aiEnabled}
          onCreateService={handleCreateServiceFromQuickTest}
        />
      ) : (
        selected ? renderPlayground() : (
          <Card>
            <CardContent className="p-12 text-center text-muted-foreground">
              No active services. Use the <button className="underline" onClick={() => setTab('quick-test')}>Request Test</button> tab to test and create services.
            </CardContent>
          </Card>
        )
      )}
    </div>
  )
}
