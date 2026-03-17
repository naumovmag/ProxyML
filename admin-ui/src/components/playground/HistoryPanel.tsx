import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Trash2, Star, StarOff, Loader2, Play } from 'lucide-react'
import { toast } from 'sonner'
import {
  HistoryEntry,
  fetchHistory,
  updateHistoryEntry,
  deleteHistoryEntry,
  clearHistory,
} from '@/api/playground'

interface Props {
  serviceId?: string
  onReplay?: (entry: HistoryEntry) => void
}

export default function HistoryPanel({ serviceId, onReplay }: Props) {
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const load = () => {
    setLoading(true)
    fetchHistory({ service_id: serviceId, favorites_only: favoritesOnly, limit: 50 })
      .then(({ data }) => setEntries(data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [serviceId, favoritesOnly])

  const toggleFavorite = async (entry: HistoryEntry) => {
    try {
      const { data } = await updateHistoryEntry(entry.id, { is_favorite: !entry.is_favorite })
      setEntries((prev) => prev.map((e) => (e.id === entry.id ? data : e)))
    } catch { toast.error('Failed to update') }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteHistoryEntry(id)
      setEntries((prev) => prev.filter((e) => e.id !== id))
      toast.success('Deleted')
    } catch { toast.error('Failed to delete') }
  }

  const handleClearAll = async () => {
    try {
      await clearHistory()
      setEntries([])
      toast.success('History cleared')
    } catch { toast.error('Failed to clear') }
  }

  if (loading) {
    return <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Button
          variant={favoritesOnly ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFavoritesOnly(!favoritesOnly)}
        >
          <Star className="h-3 w-3 mr-1" />
          Favorites
        </Button>
        {entries.length > 0 && (
          <Button variant="ghost" size="sm" className="text-destructive ml-auto" onClick={handleClearAll}>
            <Trash2 className="h-3 w-3 mr-1" />Clear all
          </Button>
        )}
      </div>

      {entries.length === 0 && (
        <div className="text-center text-muted-foreground text-sm py-8">
          {favoritesOnly ? 'No favorite entries' : 'No history yet. Save results from the playground.'}
        </div>
      )}

      {entries.map((entry) => (
        <Card key={entry.id} className="overflow-hidden">
          <CardContent className="p-3">
            <div className="flex items-start justify-between gap-2">
              <div
                className="flex-1 cursor-pointer"
                onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
              >
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">{entry.service_name}</span>
                  <Badge variant="outline" className="text-xs">{entry.service_type}</Badge>
                  {entry.status_code != null && (
                    <Badge variant={entry.status_code < 400 ? 'default' : 'destructive'} className="text-xs">
                      {entry.status_code}
                    </Badge>
                  )}
                  {entry.duration_ms != null && (
                    <span className="text-xs text-muted-foreground">{entry.duration_ms} ms</span>
                  )}
                  {entry.token_usage?.total_tokens != null && (
                    <span className="text-xs text-muted-foreground font-mono">{entry.token_usage.total_tokens} tok</span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {new Date(entry.created_at).toLocaleString()}
                  {entry.note && <span className="ml-2 italic">{entry.note}</span>}
                </div>
              </div>
              <div className="flex gap-1 shrink-0">
                {onReplay && (
                  <Button variant="ghost" size="sm" onClick={() => onReplay(entry)} className="h-7 w-7 p-0 text-primary" title="Replay in playground">
                    <Play className="h-3.5 w-3.5" />
                  </Button>
                )}
                <Button variant="ghost" size="sm" onClick={() => toggleFavorite(entry)} className="h-7 w-7 p-0">
                  {entry.is_favorite
                    ? <Star className="h-3.5 w-3.5 text-yellow-500 fill-yellow-500" />
                    : <StarOff className="h-3.5 w-3.5 text-muted-foreground" />
                  }
                </Button>
                <Button variant="ghost" size="sm" onClick={() => handleDelete(entry.id)} className="h-7 w-7 p-0 text-destructive">
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>

            {expandedId === entry.id && (
              <div className="mt-3 space-y-2 border-t pt-3">
                {entry.params && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-1">Parameters</div>
                    <pre className="text-xs font-mono bg-muted rounded p-2 max-h-24 overflow-auto">
                      {JSON.stringify(entry.params, null, 2)}
                    </pre>
                  </div>
                )}
                {entry.request_body && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-1">Request</div>
                    <pre className="text-xs font-mono bg-muted rounded p-2 max-h-40 overflow-auto whitespace-pre-wrap">
                      {entry.request_body}
                    </pre>
                  </div>
                )}
                {entry.response_body && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-1">Response</div>
                    <pre className="text-xs font-mono bg-muted rounded p-2 max-h-60 overflow-auto whitespace-pre-wrap">
                      {entry.response_body}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
