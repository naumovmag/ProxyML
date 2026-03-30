import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Terminal, Copy, Check, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Service } from '@/api/services'
import api from '@/api/client'

interface ApiKeyInfo {
  id: string
  name: string
  key_prefix: string
  is_active: boolean
}

interface Props {
  service: Service
  method?: string
  path?: string
  body?: unknown
  headers?: Record<string, string>
  triggerVariant?: 'button' | 'icon'
}

function getTemplateForService(service: Service) {
  const model = service.default_model || 'your-model'
  switch (service.service_type) {
    case 'llm_chat':
      return {
        path: 'v1/chat/completions',
        body: { model, messages: [{ role: 'user', content: 'Hello' }], max_tokens: 100 },
      }
    case 'embedding':
      return {
        path: 'v1/embeddings',
        body: { model, input: 'Hello world' },
      }
    case 'stt':
      return { path: 'v1/audio/transcriptions', body: null }
    case 'tts':
      return {
        path: 'v1/audio/speech',
        body: { model: service.default_model || 'tts-1', input: 'Hello world', voice: 'alloy' },
      }
    default:
      return {
        path: 'your-path',
        body: { key: 'value' },
      }
  }
}

export default function CurlGenerator({ service, method = 'POST', path, body, headers, triggerVariant = 'button' }: Props) {
  const [open, setOpen] = useState(false)
  const [keys, setKeys] = useState<ApiKeyInfo[]>([])
  const [apiKey, setApiKey] = useState('')
  const [selectedKeyId, setSelectedKeyId] = useState<string>('')
  const [copied, setCopied] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [rawKeysCache] = useState<Map<string, string>>(() => new Map())

  // If path/body not provided, use template based on service_type
  const useTemplate = path === undefined && body === undefined
  const template = useTemplate ? getTemplateForService(service) : null
  const effectivePath = path ?? template?.path ?? ''
  const effectiveBody = body ?? template?.body

  useEffect(() => {
    if (open) {
      api.get<ApiKeyInfo[]>(`/admin/api-keys/by-service/${service.slug}`)
        .then(({ data }) => setKeys(data))
        .catch(() => {})
    }
  }, [open, service.slug])

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) return
    try {
      const { data } = await api.post<{ raw_key: string; id: string; name: string; key_prefix: string; is_active: boolean }>(
        '/admin/api-keys',
        { name: newKeyName.trim(), allowed_services: [service.slug] },
      )
      rawKeysCache.set(data.id, data.raw_key)
      setApiKey(data.raw_key)
      setKeys((prev) => [...prev, { id: data.id, name: data.name, key_prefix: data.key_prefix, is_active: data.is_active }])
      setSelectedKeyId(data.id)
      setCreating(false)
      setNewKeyName('')
      toast.success(`Key created: ${data.key_prefix}...`)
    } catch {
      toast.error('Failed to create key')
    }
  }

  const proxyUrl = `${window.location.origin}/proxy/${service.slug}`
  const fullUrl = effectivePath ? `${proxyUrl}/${effectivePath.replace(/^\//, '')}` : proxyUrl
  const keyPlaceholder = apiKey || '<YOUR_API_KEY>'

  const isStt = useTemplate && service.service_type === 'stt'
  const isTts = useTemplate && service.service_type === 'tts'

  const buildCurl = () => {
    const parts: string[] = [`curl -X ${method}`]
    parts.push(`  '${fullUrl}'`)

    if (isStt) {
      // STT: multipart form, no Content-Type header
      parts.push(`  -H 'X-Api-Key: ${keyPlaceholder}'`)
      parts.push(`  -F 'file=@audio.wav'`)
      parts.push(`  -F 'model=${service.default_model || 'whisper-1'}'`)
    } else {
      parts.push(`  -H 'Content-Type: application/json'`)
      parts.push(`  -H 'X-Api-Key: ${keyPlaceholder}'`)

      if (headers) {
        for (const [k, v] of Object.entries(headers)) {
          if (k.toLowerCase() !== 'content-type') {
            parts.push(`  -H '${k}: ${v}'`)
          }
        }
      }

      if (effectiveBody && method !== 'GET' && method !== 'DELETE') {
        const bodyStr = typeof effectiveBody === 'string' ? effectiveBody : JSON.stringify(effectiveBody, null, 2)
        parts.push(`  -d '${bodyStr}'`)
      }

      if (isTts) {
        parts.push(`  --output speech.mp3`)
      }
    }

    return parts.join(' \\\n')
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(buildCurl())
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    toast.success('Copied to clipboard')
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {triggerVariant === 'icon' ? (
          <Button variant="ghost" size="icon" title="cURL">
            <Terminal className="h-4 w-4" />
          </Button>
        ) : (
          <Button variant="outline" size="sm">
            <Terminal className="h-4 w-4 mr-1" />
            cURL
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>cURL Command</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* API Key selection */}
          <div className="space-y-2">
            <Label className="text-sm">API Key</Label>
            <div className="flex gap-2">
              {keys.length > 0 && (
                <Select
                  value={selectedKeyId}
                  onValueChange={(id) => {
                    setSelectedKeyId(id)
                    const cached = rawKeysCache.get(id)
                    if (cached) {
                      setApiKey(cached)
                    } else {
                      const key = keys.find((k) => k.id === id)
                      if (key) {
                        setApiKey('')
                        toast.info(`Key ${key.key_prefix}... — paste your raw key value below, or create a new key`)
                      }
                    }
                  }}
                >
                  <SelectTrigger className="w-56">
                    <SelectValue placeholder="Select existing key" />
                  </SelectTrigger>
                  <SelectContent>
                    {keys.map((k) => (
                      <SelectItem key={k.id} value={k.id}>
                        {k.name} ({k.key_prefix}...)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Input
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Paste your API key or create new"
                className="flex-1 font-mono text-xs"
              />
            </div>
            <div className="flex gap-2">
              {creating ? (
                <div className="flex gap-1 items-center">
                  <Input
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="Key name"
                    className="h-8 w-48 text-xs"
                    onKeyDown={(e) => { if (e.key === 'Enter') handleCreateKey() }}
                    autoFocus
                  />
                  <Button size="sm" onClick={handleCreateKey} className="h-8 text-xs">Create</Button>
                  <Button variant="ghost" size="sm" onClick={() => setCreating(false)} className="h-8 text-xs">Cancel</Button>
                </div>
              ) : (
                <Button variant="ghost" size="sm" onClick={() => setCreating(true)} className="text-xs">
                  <Plus className="h-3 w-3 mr-1" />Create new key for {service.slug}
                </Button>
              )}
            </div>
          </div>

          {/* Generated cURL */}
          <Card>
            <CardContent className="p-0 relative">
              <pre className="p-4 text-xs font-mono overflow-auto max-h-[300px] whitespace-pre-wrap text-foreground">
                {buildCurl()}
              </pre>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopy}
                className="absolute top-2 right-2"
              >
                {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
              </Button>
            </CardContent>
          </Card>

          <p className="text-xs text-muted-foreground">
            Proxy URL: <span className="font-mono">{proxyUrl}</span>
          </p>
        </div>
      </DialogContent>
    </Dialog>
  )
}
