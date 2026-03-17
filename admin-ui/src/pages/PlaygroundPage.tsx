import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { fetchServices, Service } from '@/api/services'
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
import { FlaskConical, History } from 'lucide-react'
import { HistoryEntry } from '@/api/playground'
import ChatPlayground from '@/components/playground/ChatPlayground'
import EmbeddingPlayground from '@/components/playground/EmbeddingPlayground'
import SttPlayground from '@/components/playground/SttPlayground'
import TtsPlayground from '@/components/playground/TtsPlayground'
import CustomPlayground from '@/components/playground/CustomPlayground'
import HistoryPanel from '@/components/playground/HistoryPanel'

const TYPE_LABELS: Record<string, string> = {
  llm_chat: 'LLM Chat',
  embedding: 'Embedding',
  stt: 'Speech-to-Text',
  tts: 'Text-to-Speech',
  custom: 'Custom',
}

type Tab = 'playground' | 'history'

export default function PlaygroundPage() {
  const location = useLocation()
  const navServiceId = (location.state as { serviceId?: string } | null)?.serviceId
  const [services, setServices] = useState<Service[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('playground')
  const [replayEntry, setReplayEntry] = useState<HistoryEntry | null>(null)
  const [historyServiceFilter, setHistoryServiceFilter] = useState<string>('all')

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

  const renderPlayground = () => {
    if (!selected) return null
    const replay = replayEntry
    const clearReplay = () => setReplayEntry(null)
    switch (selected.service_type) {
      case 'llm_chat':
        return <ChatPlayground service={selected} key={selected.id} replay={replay} onReplayConsumed={clearReplay} />
      case 'embedding':
        return <EmbeddingPlayground service={selected} key={selected.id} replay={replay} onReplayConsumed={clearReplay} />
      case 'stt':
        return <SttPlayground service={selected} key={selected.id} replay={replay} onReplayConsumed={clearReplay} />
      case 'tts':
        return <TtsPlayground service={selected} key={selected.id} replay={replay} onReplayConsumed={clearReplay} />
      default:
        return <CustomPlayground service={selected} key={selected.id} replay={replay} onReplayConsumed={clearReplay} />
    }
  }

  if (loading) {
    return <div className="text-center text-muted-foreground py-12">Loading services...</div>
  }

  if (services.length === 0) {
    return (
      <div>
        <div className="flex items-center gap-3 mb-6">
          <FlaskConical className="h-6 w-6" />
          <h2 className="text-2xl font-bold">Playground</h2>
        </div>
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            No active services. Add a service first to use the playground.
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div>
      {/* Header with tabs */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <FlaskConical className="h-6 w-6" />
          <h2 className="text-2xl font-bold">Playground</h2>
        </div>
        <div className="flex gap-1 bg-muted rounded-lg p-1">
          <Button
            variant={tab === 'playground' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setTab('playground')}
          >
            <FlaskConical className="h-4 w-4 mr-1" />
            Playground
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

      {/* Service selector — always visible */}
      <div className="flex items-center gap-4 mb-4">
        {tab === 'playground' ? (
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
        )}

        {tab === 'playground' && selected && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="outline">{TYPE_LABELS[selected.service_type] || selected.service_type}</Badge>
            <span className="font-mono text-xs">{selected.base_url}</span>
            {selected.supports_streaming && <Badge variant="secondary">Streaming</Badge>}
            {selected.default_model && <Badge variant="secondary">{selected.default_model}</Badge>}
          </div>
        )}
      </div>

      {/* Content */}
      {tab === 'history' ? (
        <HistoryPanel
          serviceId={historyServiceFilter === 'all' ? undefined : historyServiceFilter}
          onReplay={handleReplay}
        />
      ) : (
        selected && renderPlayground()
      )}
    </div>
  )
}
