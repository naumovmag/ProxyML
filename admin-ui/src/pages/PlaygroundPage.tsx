import { useState, useEffect } from 'react'
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
  const [services, setServices] = useState<Service[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('playground')
  const [replayEntry, setReplayEntry] = useState<HistoryEntry | null>(null)

  useEffect(() => {
    fetchServices()
      .then(({ data }) => {
        const active = data.filter((s) => s.is_active)
        setServices(active)
        if (active.length > 0 && !selectedId) {
          setSelectedId(active[0].id)
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

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

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
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

      {services.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            No active services. Add a service first to use the playground.
          </CardContent>
        </Card>
      ) : tab === 'history' ? (
        <HistoryPanel serviceId={selectedId || undefined} onReplay={handleReplay} />
      ) : (
        <div className="space-y-4">
          {/* Service selector + info */}
          <div className="flex items-center gap-4">
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

            {selected && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Badge variant="outline">{TYPE_LABELS[selected.service_type] || selected.service_type}</Badge>
                <span className="font-mono text-xs">{selected.base_url}</span>
                {selected.supports_streaming && <Badge variant="secondary">Streaming</Badge>}
                {selected.default_model && <Badge variant="secondary">{selected.default_model}</Badge>}
              </div>
            )}
          </div>

          {/* Playground area */}
          {selected && renderPlayground()}
        </div>
      )}
    </div>
  )
}
