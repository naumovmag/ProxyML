import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Loader2, Mic, Upload, BookmarkPlus, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Service } from '@/api/services'
import { executePlaygroundUpload, saveHistory } from '@/api/playground'
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

export default function SttPlayground({ service, replay, onReplayConsumed }: Props) {
  const [model, setModel] = useState(service.default_model || '')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [transcription, setTranscription] = useState('')
  const [meta, setMeta] = useState<{ statusCode?: number; durationMs?: number; responseSize?: number } | null>(null)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setModel(service.default_model || '') }, [service])

  const getParams = () => ({ model })
  const loadParams = (params: Record<string, unknown>) => {
    if (params.model != null) setModel(String(params.model))
  }

  useEffect(() => {
    if (!replay) return
    if (replay.params) loadParams(replay.params)
    onReplayConsumed?.()
  }, [replay])

  const handleSaveResult = async () => {
    if (!transcription) return
    try {
      await saveHistory({
        service_id: service.id, service_name: service.name, service_type: service.service_type,
        params: getParams(), request_body: file?.name || 'audio file', response_body: transcription,
        status_code: meta?.statusCode, duration_ms: meta?.durationMs,
      })
      toast.success('Saved to history')
    } catch { toast.error('Failed to save') }
  }

  const handleTranscribe = async () => {
    if (!file || loading) return
    setLoading(true); setTranscription(''); setError(''); setMeta(null)
    try {
      const { data } = await executePlaygroundUpload(service.id, 'v1/audio/transcriptions', file, model || undefined)
      setMeta({ statusCode: data.status_code, durationMs: data.duration_ms, responseSize: data.response_size })
      if (data.status_code >= 400) { setError(data.body); return }
      try { setTranscription(JSON.parse(data.body).text || data.body) } catch { setTranscription(data.body) }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <PresetManager serviceId={service.id} serviceType="stt" getParams={getParams} onLoad={loadParams} />
        <div className="ml-auto">
          <CurlGenerator service={service} method="POST" path="v1/audio/transcriptions" body={{ model: model || undefined }} headers={{ 'Content-Type': 'multipart/form-data' }} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label className="text-xs">Audio File</Label>
          <div className="mt-1 flex gap-2">
            <input ref={fileRef} type="file" accept=".wav,.mp3,.m4a,.webm,.ogg,.flac" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <Button variant="outline" onClick={() => fileRef.current?.click()} className="flex-1">
              <Upload className="h-4 w-4 mr-2" />{file ? file.name : 'Choose audio file'}
            </Button>
          </div>
          {file && <p className="text-xs text-muted-foreground mt-1">{(file.size / 1024).toFixed(1)} KB</p>}
        </div>
        <div>
          <Label className="text-xs">Model</Label>
          <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="whisper-1" className="mt-1" />
        </div>
      </div>

      <Button onClick={handleTranscribe} disabled={loading || !file}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Mic className="h-4 w-4 mr-2" />}Transcribe
      </Button>

      {meta && (
        <div className="flex items-center gap-2">
          <ResponseMeta statusCode={meta.statusCode} durationMs={meta.durationMs} responseSize={meta.responseSize} />
          {transcription && <Button variant="ghost" size="sm" onClick={handleSaveResult} title="Save to history"><BookmarkPlus className="h-4 w-4" /></Button>}
        </div>
      )}

      {error && <Card className="border-red-500/30"><CardContent className="p-4 text-sm text-red-500 font-mono whitespace-pre-wrap">{error}</CardContent></Card>}

      {transcription && (
        <Card><CardContent className="p-4">
          <div className="text-xs text-muted-foreground mb-2">Transcription:</div>
          <p className="text-sm whitespace-pre-wrap">{transcription}</p>
        </CardContent></Card>
      )}
    </div>
  )
}
