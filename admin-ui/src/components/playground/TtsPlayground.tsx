import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Loader2, Volume2, BookmarkPlus, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Service } from '@/api/services'
import { executePlaygroundTts, saveHistory } from '@/api/playground'
import { aiGenerateTestParams } from '@/api/ai'
import ResponseMeta from './ResponseMeta'
import PresetManager from './PresetManager'
import CurlGenerator from './CurlGenerator'

import { HistoryEntry } from '@/api/playground'

interface Props {
  service: Service
  replay?: HistoryEntry | null
  onReplayConsumed?: () => void
}

export default function TtsPlayground({ service, replay, onReplayConsumed }: Props) {
  const [text, setText] = useState('')
  const [model, setModel] = useState(service.default_model || '')
  const [voice, setVoice] = useState('alloy')
  const [loading, setLoading] = useState(false)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [meta, setMeta] = useState<{ durationMs?: number } | null>(null)
  const [error, setError] = useState('')
  const audioRef = useRef<HTMLAudioElement>(null)

  useEffect(() => { setModel(service.default_model || '') }, [service])
  useEffect(() => { return () => { if (audioUrl) URL.revokeObjectURL(audioUrl) } }, [audioUrl])

  useEffect(() => {
    if (!replay) return
    if (replay.params) loadParams(replay.params)
    if (replay.request_body) setText(replay.request_body)
    onReplayConsumed?.()
  }, [replay])

  const getParams = () => ({ model, voice })
  const loadParams = (params: Record<string, unknown>) => {
    if (params.model != null) setModel(String(params.model))
    if (params.voice != null) setVoice(String(params.voice))
  }

  const [aiGenerating, setAiGenerating] = useState(false)

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
        if (b.voice) setVoice(String(b.voice))
        if (b.input) setText(String(b.input))
      }
      if (data.description) toast.success(data.description)
    } catch { toast.error('Failed to generate test params') }
    finally { setAiGenerating(false) }
  }

  const handleSaveResult = async () => {
    if (!audioUrl) return
    try {
      await saveHistory({
        service_id: service.id, service_name: service.name, service_type: service.service_type,
        params: getParams(), request_body: text, response_body: '[audio response]',
        duration_ms: meta?.durationMs,
      })
      toast.success('Saved to history')
    } catch { toast.error('Failed to save') }
  }

  const handleSpeak = async () => {
    if (!text.trim() || loading) return
    setLoading(true); setError(''); setMeta(null)
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioUrl(null)
    const startTime = performance.now()
    try {
      const { data } = await executePlaygroundTts({
        service_id: service.id, method: 'POST', path: 'v1/audio/speech',
        body: { model: model || undefined, input: text, voice },
      })
      const durationMs = Math.round(performance.now() - startTime)
      const url = URL.createObjectURL(data as Blob)
      setAudioUrl(url)
      setMeta({ durationMs })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <PresetManager serviceId={service.id} serviceType="tts" getParams={getParams} onLoad={loadParams} />
        <div className="ml-auto flex gap-1">
          <Button variant="outline" size="sm" onClick={handleAiGenerate} disabled={aiGenerating}>
            {aiGenerating ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Sparkles className="h-3 w-3 mr-1" />}AI Fill
          </Button>
          <CurlGenerator service={service} method="POST" path="v1/audio/speech" body={{ model: model || undefined, input: text, voice }} />
        </div>
      </div>
      <div>
        <Label className="text-xs">Text</Label>
        <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Enter text to synthesize..." rows={4} className="mt-1" />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <Label className="text-xs">Model</Label>
          <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="tts-1" className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">Voice</Label>
          <Input value={voice} onChange={(e) => setVoice(e.target.value)} placeholder="alloy" className="mt-1" />
        </div>
        <div className="flex items-end">
          <Button onClick={handleSpeak} disabled={loading || !text.trim()}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Volume2 className="h-4 w-4 mr-2" />}Speak
          </Button>
        </div>
      </div>

      {meta && (
        <div className="flex items-center gap-2">
          <ResponseMeta durationMs={meta.durationMs} />
          {audioUrl && <Button variant="ghost" size="sm" onClick={handleSaveResult} title="Save to history"><BookmarkPlus className="h-4 w-4" /></Button>}
        </div>
      )}
      {error && <Card className="border-red-500/30"><CardContent className="p-4 text-sm text-red-500 font-mono whitespace-pre-wrap">{error}</CardContent></Card>}
      {audioUrl && <Card><CardContent className="p-4"><audio ref={audioRef} src={audioUrl} controls className="w-full" /></CardContent></Card>}
    </div>
  )
}
