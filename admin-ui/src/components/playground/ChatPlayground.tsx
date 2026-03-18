import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Send, Loader2, Trash2, Settings2, ChevronDown, ChevronUp, User, Bot, Save, BookmarkPlus, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Service } from '@/api/services'
import { executePlayground, executePlaygroundStream, saveHistory } from '@/api/playground'
import { aiGenerateTestParams } from '@/api/ai'
import ResponseMeta from './ResponseMeta'
import PresetManager from './PresetManager'
import CurlGenerator from './CurlGenerator'

interface Message {
  role: 'system' | 'user' | 'assistant'
  content: string
}

interface Meta {
  statusCode?: number
  durationMs?: number
  responseSize?: number
  tokenUsage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } | null
}

import { HistoryEntry } from '@/api/playground'

interface Props {
  service: Service
  replay?: HistoryEntry | null
  onReplayConsumed?: () => void
  aiEnabled?: boolean
}

export default function ChatPlayground({ service, replay, onReplayConsumed, aiEnabled }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [model, setModel] = useState(service.default_model || '')
  const [temperature, setTemperature] = useState(0.7)
  const [maxTokens, setMaxTokens] = useState(1024)
  const [streaming, setStreaming] = useState(service.supports_streaming)
  const [loading, setLoading] = useState(false)
  const [streamedContent, setStreamedContent] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [lastMeta, setLastMeta] = useState<Meta | null>(null)
  const [aiGenerating, setAiGenerating] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setModel(service.default_model || '')
    setStreaming(service.supports_streaming)
  }, [service])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, streamedContent])

  useEffect(() => {
    if (!replay) return
    if (replay.params) {
      loadParams(replay.params)
    }
    if (replay.request_body) {
      try {
        const msgs = JSON.parse(replay.request_body) as Message[]
        if (Array.isArray(msgs)) {
          setMessages(msgs.filter(m => m.role !== 'system'))
          const sys = msgs.find(m => m.role === 'system')
          if (sys) setSystemPrompt(sys.content)
        }
      } catch {
        setInput(replay.request_body)
      }
    }
    onReplayConsumed?.()
  }, [replay])

  const getParams = () => ({
    model, temperature, max_tokens: maxTokens, system_prompt: systemPrompt, streaming,
  })

  const loadParams = (params: Record<string, unknown>) => {
    if (params.model != null) setModel(String(params.model))
    if (params.temperature != null) setTemperature(Number(params.temperature))
    if (params.max_tokens != null) setMaxTokens(Number(params.max_tokens))
    if (params.system_prompt != null) setSystemPrompt(String(params.system_prompt))
    if (params.streaming != null) setStreaming(Boolean(params.streaming))
  }

  const handleSaveResult = async () => {
    if (messages.length === 0) return
    try {
      await saveHistory({
        service_id: service.id,
        service_name: service.name,
        service_type: service.service_type,
        params: getParams(),
        request_body: JSON.stringify(messages, null, 2),
        response_body: messages.filter(m => m.role === 'assistant').map(m => m.content).join('\n---\n'),
        status_code: lastMeta?.statusCode,
        duration_ms: lastMeta?.durationMs,
        token_usage: lastMeta?.tokenUsage as Record<string, number> | undefined,
      })
      toast.success('Saved to history')
    } catch {
      toast.error('Failed to save')
    }
  }

  const handleAiGenerate = async () => {
    setAiGenerating(true)
    try {
      const { data } = await aiGenerateTestParams({
        name: service.name,
        service_type: service.service_type,
        default_model: service.default_model,
        supports_streaming: service.supports_streaming,
      })
      if (data.body) {
        const b = data.body as Record<string, unknown>
        if (b.model) setModel(String(b.model))
        if (b.temperature != null) setTemperature(Number(b.temperature))
        if (b.max_tokens != null) setMaxTokens(Number(b.max_tokens))
        if (b.messages && Array.isArray(b.messages)) {
          const msgs = b.messages as Array<{ role: string; content: string }>
          const sys = msgs.find(m => m.role === 'system')
          if (sys) setSystemPrompt(sys.content)
          const user = msgs.find(m => m.role === 'user')
          if (user) setInput(user.content)
        }
      }
      if (data.description) toast.success(data.description)
    } catch {
      toast.error('Failed to generate test params')
    } finally {
      setAiGenerating(false)
    }
  }

  const currentRequestBody = () => {
    const apiMessages = [
      ...(systemPrompt ? [{ role: 'system', content: systemPrompt }] : []),
      ...messages,
      ...(input.trim() ? [{ role: 'user', content: input.trim() }] : []),
    ]
    const b: Record<string, unknown> = { model: model || undefined, messages: apiMessages, temperature, max_tokens: maxTokens }
    if (streaming) b.stream = true
    return b
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: Message = { role: 'user', content: text }
    const allMessages = [...messages, userMsg]
    setMessages(allMessages)
    setInput('')
    setLoading(true)
    setLastMeta(null)

    const apiMessages = [
      ...(systemPrompt ? [{ role: 'system' as const, content: systemPrompt }] : []),
      ...allMessages,
    ]

    const body: Record<string, unknown> = {
      model: model || undefined,
      messages: apiMessages,
      temperature,
      max_tokens: maxTokens,
    }
    if (streaming) body.stream = true

    if (streaming && service.supports_streaming) {
      setStreamedContent('')
      let accumulated = ''
      await executePlaygroundStream(
        { service_id: service.id, method: 'POST', path: 'v1/chat/completions', body, stream: true },
        (chunk) => { accumulated += chunk; setStreamedContent(accumulated) },
        (meta) => {
          setMessages((prev) => [...prev, { role: 'assistant', content: accumulated }])
          setStreamedContent('')
          setLastMeta({ durationMs: meta.duration_ms })
          setLoading(false)
        },
        (error) => {
          setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${error}` }])
          setStreamedContent('')
          setLoading(false)
        },
      )
    } else {
      try {
        const { data } = await executePlayground({
          service_id: service.id, method: 'POST', path: 'v1/chat/completions', body,
        })
        const parsed = JSON.parse(data.body)
        const content = parsed.choices?.[0]?.message?.content || data.body
        setMessages((prev) => [...prev, { role: 'assistant', content }])
        setLastMeta({
          statusCode: data.status_code, durationMs: data.duration_ms,
          responseSize: data.response_size, tokenUsage: parsed.usage || null,
        })
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Request failed'
        setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${msg}` }])
      } finally {
        setLoading(false)
      }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-16rem)]">
      {/* Settings + Presets */}
      <div className="mb-3 flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => setShowSettings(!showSettings)} className="text-muted-foreground">
          <Settings2 className="h-4 w-4 mr-1" />Settings
          {showSettings ? <ChevronUp className="h-3 w-3 ml-1" /> : <ChevronDown className="h-3 w-3 ml-1" />}
        </Button>
        <PresetManager serviceId={service.id} serviceType="llm_chat" getParams={getParams} onLoad={loadParams} />
        <div className="ml-auto flex gap-1">
          {aiEnabled && (
            <Button variant="outline" size="sm" onClick={handleAiGenerate} disabled={aiGenerating} title="AI: generate test params">
              {aiGenerating ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Sparkles className="h-3 w-3 mr-1" />}
              AI Fill
            </Button>
          )}
          <CurlGenerator service={service} method="POST" path="v1/chat/completions" body={currentRequestBody()} />
        </div>
      </div>
      {showSettings && (
        <Card className="mb-3">
          <CardContent className="p-4 grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Label className="text-xs">System Prompt</Label>
              <Textarea value={systemPrompt} onChange={(e) => setSystemPrompt(e.target.value)} placeholder="You are a helpful assistant..." rows={2} className="mt-1" />
            </div>
            <div>
              <Label className="text-xs">Model</Label>
              <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="model name" className="mt-1" />
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={streaming} onCheckedChange={setStreaming} disabled={!service.supports_streaming} />
              <Label className="text-xs">Streaming</Label>
            </div>
            <div>
              <Label className="text-xs">Temperature: {temperature}</Label>
              <Slider value={[temperature]} onValueChange={([v]) => setTemperature(v)} min={0} max={2} step={0.1} className="mt-2" />
            </div>
            <div>
              <Label className="text-xs">Max Tokens: {maxTokens}</Label>
              <Slider value={[maxTokens]} onValueChange={([v]) => setMaxTokens(v)} min={1} max={8192} step={1} className="mt-2" />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 mb-3 pr-1">
        {messages.length === 0 && !loading && (
          <div className="text-center text-muted-foreground text-sm py-12">Send a message to start the conversation</div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-1"><Bot className="h-4 w-4 text-primary" /></div>
            )}
            <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
              {msg.content}
            </div>
            {msg.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center shrink-0 mt-1"><User className="h-4 w-4 text-primary-foreground" /></div>
            )}
          </div>
        ))}
        {streamedContent && (
          <div className="flex gap-2 justify-start">
            <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-1"><Bot className="h-4 w-4 text-primary" /></div>
            <div className="max-w-[80%] rounded-lg px-3 py-2 text-sm bg-muted whitespace-pre-wrap">{streamedContent}<span className="animate-pulse">▊</span></div>
          </div>
        )}
        {loading && !streamedContent && (
          <div className="flex gap-2 justify-start">
            <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-1"><Bot className="h-4 w-4 text-primary" /></div>
            <div className="rounded-lg px-3 py-2 text-sm bg-muted"><Loader2 className="h-4 w-4 animate-spin" /></div>
          </div>
        )}
      </div>

      {/* Meta + Save */}
      {lastMeta && (
        <div className="mb-2 flex items-center gap-2">
          <ResponseMeta {...lastMeta} />
          <Button variant="ghost" size="sm" onClick={handleSaveResult} title="Save to history">
            <BookmarkPlus className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2 items-end">
        <Button variant="outline" size="icon" onClick={() => { setMessages([]); setLastMeta(null) }} title="Clear chat">
          <Trash2 className="h-4 w-4" />
        </Button>
        <Textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="Type a message... (Enter to send, Shift+Enter for new line)" rows={1} className="flex-1 min-h-[40px] max-h-[120px] resize-none" />
        <Button onClick={handleSend} disabled={loading || !input.trim()} size="icon">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  )
}
