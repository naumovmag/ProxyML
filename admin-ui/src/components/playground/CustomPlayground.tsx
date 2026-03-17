import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Loader2, Send, BookmarkPlus, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Service } from '@/api/services'
import { executePlayground, saveHistory } from '@/api/playground'
import { aiGenerateTestParams } from '@/api/ai'
import ResponseMeta from './ResponseMeta'
import PresetManager from './PresetManager'
import CurlGenerator from './CurlGenerator'

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

import { HistoryEntry } from '@/api/playground'

interface Props {
  service: Service
  replay?: HistoryEntry | null
  onReplayConsumed?: () => void
}

export default function CustomPlayground({ service, replay, onReplayConsumed }: Props) {
  const [method, setMethod] = useState('POST')
  const [path, setPath] = useState('')
  const [body, setBody] = useState('{\n  \n}')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<{ body: string; statusCode: number; durationMs: number; responseSize: number; headers: Record<string, string> } | null>(null)
  const [error, setError] = useState('')
  const [aiGenerating, setAiGenerating] = useState(false)

  const getParams = () => ({ method, path })
  const loadParams = (params: Record<string, unknown>) => {
    if (params.method != null) setMethod(String(params.method))
    if (params.path != null) setPath(String(params.path))
  }

  useEffect(() => {
    if (!replay) return
    if (replay.params) loadParams(replay.params)
    if (replay.request_body) setBody(replay.request_body)
    onReplayConsumed?.()
  }, [replay])

  const handleAiGenerate = async () => {
    setAiGenerating(true)
    try {
      const { data } = await aiGenerateTestParams({
        name: service.name,
        service_type: service.service_type,
        default_model: service.default_model,
        supports_streaming: service.supports_streaming,
      })
      if (data.path) setPath(data.path)
      if (data.body) setBody(JSON.stringify(data.body, null, 2))
      if (data.description) toast.success(data.description)
    } catch {
      toast.error('Failed to generate test params')
    } finally {
      setAiGenerating(false)
    }
  }

  const handleSaveResult = async () => {
    if (!response) return
    try {
      await saveHistory({
        service_id: service.id, service_name: service.name, service_type: service.service_type,
        params: getParams(), request_body: body, response_body: response.body,
        status_code: response.statusCode, duration_ms: response.durationMs,
      })
      toast.success('Saved to history')
    } catch { toast.error('Failed to save') }
  }

  const handleSend = async () => {
    if (loading) return
    setLoading(true); setResponse(null); setError('')
    let parsedBody: unknown = undefined
    if (body.trim() && method !== 'GET' && method !== 'DELETE') {
      try { parsedBody = JSON.parse(body) } catch {
        setError('Invalid JSON body'); setLoading(false); return
      }
    }
    try {
      const { data } = await executePlayground({ service_id: service.id, method, path, body: parsedBody })
      let formattedBody = data.body
      try { formattedBody = JSON.stringify(JSON.parse(data.body), null, 2) } catch { /* keep raw */ }
      setResponse({ body: formattedBody, statusCode: data.status_code, durationMs: data.duration_ms, responseSize: data.response_size, headers: data.headers })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <PresetManager serviceType="custom" getParams={getParams} onLoad={loadParams} />
        <div className="ml-auto flex gap-1">
          <Button variant="outline" size="sm" onClick={handleAiGenerate} disabled={aiGenerating}>
            {aiGenerating ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Sparkles className="h-3 w-3 mr-1" />}
            AI Fill
          </Button>
          <CurlGenerator service={service} method={method} path={path} body={body.trim() && method !== 'GET' && method !== 'DELETE' ? (() => { try { return JSON.parse(body) } catch { return undefined } })() : undefined} />
        </div>
      </div>

      <div className="flex gap-2 items-end">
        <div>
          <Label className="text-xs">Method</Label>
          <select value={method} onChange={(e) => setMethod(e.target.value)}
            className="mt-1 flex h-9 w-24 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
            {METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <Label className="text-xs">Path</Label>
          <Input value={path} onChange={(e) => setPath(e.target.value)} placeholder="v1/chat/completions" className="mt-1" />
        </div>
        <Button onClick={handleSend} disabled={loading}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}Send
        </Button>
      </div>

      {method !== 'GET' && method !== 'DELETE' && (
        <div>
          <Label className="text-xs">Request Body (JSON)</Label>
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} className="mt-1 font-mono text-xs" rows={8} />
        </div>
      )}

      {response && (
        <>
          <div className="flex items-center gap-2">
            <ResponseMeta statusCode={response.statusCode} durationMs={response.durationMs} responseSize={response.responseSize} />
            <Button variant="ghost" size="sm" onClick={handleSaveResult} title="Save to history"><BookmarkPlus className="h-4 w-4" /></Button>
          </div>
          <Card>
            <CardContent className="p-0">
              <pre className="p-4 text-xs font-mono overflow-auto max-h-[400px] whitespace-pre-wrap">{response.body}</pre>
            </CardContent>
          </Card>
        </>
      )}

      {error && (
        <Card className="border-red-500/30"><CardContent className="p-4 text-sm text-red-500 font-mono whitespace-pre-wrap">{error}</CardContent></Card>
      )}
    </div>
  )
}
