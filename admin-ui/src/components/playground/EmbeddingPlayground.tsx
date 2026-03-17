import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Loader2, Zap, BookmarkPlus, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Service } from '@/api/services'
import { executePlayground, saveHistory } from '@/api/playground'
import { aiGenerateTestParams } from '@/api/ai'
import ResponseMeta from './ResponseMeta'
import PresetManager from './PresetManager'
import CurlGenerator from './CurlGenerator'

import { HistoryEntry } from '@/api/playground'

interface Props {
  service: Service
  replay?: HistoryEntry | null
  onReplayConsumed?: () => void
  aiEnabled?: boolean
}

export default function EmbeddingPlayground({ service, replay, onReplayConsumed, aiEnabled }: Props) {
  const [text, setText] = useState('')
  const [model, setModel] = useState(service.default_model || '')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{
    dimensions: number
    preview: number[]
    usage?: { prompt_tokens?: number; total_tokens?: number }
  } | null>(null)
  const [meta, setMeta] = useState<{ statusCode?: number; durationMs?: number; responseSize?: number } | null>(null)
  const [error, setError] = useState('')
  const [rawBody, setRawBody] = useState('')
  const [aiGenerating, setAiGenerating] = useState(false)

  useEffect(() => { setModel(service.default_model || '') }, [service])

  useEffect(() => {
    if (!replay) return
    if (replay.params) loadParams(replay.params)
    if (replay.request_body) setText(replay.request_body)
    onReplayConsumed?.()
  }, [replay])

  const getParams = () => ({ model })
  const loadParams = (params: Record<string, unknown>) => {
    if (params.model != null) setModel(String(params.model))
  }

  const handleAiGenerate = async () => {
    setAiGenerating(true)
    try {
      const { data } = await aiGenerateTestParams({
        name: service.name, service_type: service.service_type,
        default_model: service.default_model, supports_streaming: service.supports_streaming,
      })
      if (data.body) {
        const b = data.body as Record<string, unknown>
        if (b.model) setModel(String(b.model))
        if (b.input) setText(String(b.input))
      }
      if (data.description) toast.success(data.description)
    } catch { toast.error('Failed to generate test params') }
    finally { setAiGenerating(false) }
  }

  const handleSaveResult = async () => {
    if (!result) return
    try {
      await saveHistory({
        service_id: service.id, service_name: service.name, service_type: service.service_type,
        params: getParams(), request_body: text, response_body: rawBody,
        status_code: meta?.statusCode, duration_ms: meta?.durationMs,
        token_usage: result.usage as Record<string, number> | undefined,
      })
      toast.success('Saved to history')
    } catch { toast.error('Failed to save') }
  }

  const handleEmbed = async () => {
    if (!text.trim() || loading) return
    setLoading(true); setResult(null); setError(''); setMeta(null); setRawBody('')
    try {
      const { data } = await executePlayground({
        service_id: service.id, method: 'POST', path: 'v1/embeddings',
        body: { model: model || undefined, input: text },
      })
      setMeta({ statusCode: data.status_code, durationMs: data.duration_ms, responseSize: data.response_size })
      setRawBody(data.body)
      if (data.status_code >= 400) { setError(data.body); return }
      const parsed = JSON.parse(data.body)
      const embedding = parsed.data?.[0]?.embedding || []
      setResult({ dimensions: embedding.length, preview: embedding.slice(0, 20), usage: parsed.usage })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <PresetManager serviceId={service.id} serviceType="embedding" getParams={getParams} onLoad={loadParams} />
        <div className="ml-auto flex gap-1">
          {aiEnabled && (
            <Button variant="outline" size="sm" onClick={handleAiGenerate} disabled={aiGenerating}>
              {aiGenerating ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Sparkles className="h-3 w-3 mr-1" />}AI Fill
            </Button>
          )}
          <CurlGenerator service={service} method="POST" path="v1/embeddings" body={{ model: model || undefined, input: text }} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <Label className="text-xs">Text to embed</Label>
          <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Enter text to generate embeddings..." rows={4} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">Model</Label>
          <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="model name" className="mt-1" />
        </div>
        <div className="flex items-end gap-2">
          <Button onClick={handleEmbed} disabled={loading || !text.trim()}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Zap className="h-4 w-4 mr-2" />}Embed
          </Button>
        </div>
      </div>

      {meta && (
        <div className="flex items-center gap-2">
          <ResponseMeta statusCode={meta.statusCode} durationMs={meta.durationMs} responseSize={meta.responseSize} tokenUsage={result?.usage as Record<string, number> | null || null} />
          {result && <Button variant="ghost" size="sm" onClick={handleSaveResult} title="Save to history"><BookmarkPlus className="h-4 w-4" /></Button>}
        </div>
      )}

      {error && (
        <Card className="border-red-500/30"><CardContent className="p-4 text-sm text-red-500 font-mono whitespace-pre-wrap">{error}</CardContent></Card>
      )}

      {result && (
        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="text-sm"><span className="font-medium">Dimensions:</span> <span className="font-mono">{result.dimensions}</span></div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Vector preview (first 20 values):</div>
              <div className="font-mono text-xs bg-muted rounded p-2 break-all">
                [{result.preview.map((v) => v.toFixed(6)).join(', ')}{result.dimensions > 20 && ', ...'}]
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
