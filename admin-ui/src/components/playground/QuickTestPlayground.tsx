import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader2, Send, Plus, Terminal } from 'lucide-react'
import { toast } from 'sonner'
import { executeQuickTest, PlaygroundResponse } from '@/api/playground'
import ResponseMeta from './ResponseMeta'

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
const AUTH_TYPES = [
  { value: 'none', label: 'No Auth' },
  { value: 'bearer', label: 'Bearer Token' },
  { value: 'header', label: 'Custom Header' },
]

function parseCurl(raw: string): {
  url?: string; method?: string; headers: Record<string, string>; body?: string
} {
  // Normalize: join line continuations, collapse whitespace
  const s = raw.replace(/\\\s*\n/g, ' ').replace(/\s+/g, ' ').trim()
  const result: { url?: string; method?: string; headers: Record<string, string>; body?: string } = { headers: {} }

  // Extract method: -X POST or --request POST
  const methodMatch = s.match(/(?:-X|--request)\s+([A-Z]+)/i)
  if (methodMatch) result.method = methodMatch[1].toUpperCase()

  // Extract headers: -H 'Key: Value' or -H "Key: Value"
  const headerRegex = /-H\s+['"](.*?)['"]/gi
  let hm
  while ((hm = headerRegex.exec(s)) !== null) {
    const idx = hm[1].indexOf(':')
    if (idx > 0) {
      result.headers[hm[1].slice(0, idx).trim()] = hm[1].slice(idx + 1).trim()
    }
  }
  // Also --header
  const headerRegex2 = /--header\s+['"](.*?)['"]/gi
  while ((hm = headerRegex2.exec(s)) !== null) {
    const idx = hm[1].indexOf(':')
    if (idx > 0) {
      result.headers[hm[1].slice(0, idx).trim()] = hm[1].slice(idx + 1).trim()
    }
  }

  // Extract body: -d 'data' or --data 'data' or --data-raw 'data'
  const bodyMatch = s.match(/(?:-d|--data|--data-raw)\s+'([\s\S]*?)'/i)
    || s.match(/(?:-d|--data|--data-raw)\s+"([\s\S]*?)"/i)
  if (bodyMatch) result.body = bodyMatch[1]

  // Extract URL: first try explicit http(s)://, then find curl's positional argument
  let urlMatch = s.match(/['"]?(https?:\/\/[^\s'"]+)['"]?/)
  if (urlMatch) {
    result.url = urlMatch[1]
  } else {
    // Strip known flags with their values, then find the remaining positional arg (the URL)
    const stripped = s
      .replace(/^curl\s+/, '')
      .replace(/(?:-X|--request|-H|--header|-d|--data|--data-raw|--data-binary|-u|--user|-o|--output|-A|--user-agent)\s+(?:'[^']*'|"[^"]*"|\S+)/gi, '')
      .replace(/(?:--location|--compressed|-s|--silent|-k|--insecure|-v|--verbose|-L|-S|-f)/gi, '')
      .trim()
    const bareMatch = stripped.match(/['"]?([^\s'"]+)['"]?/)
    if (bareMatch) {
      let u = bareMatch[1]
      if (!/^https?:\/\//i.test(u)) u = 'http://' + u
      result.url = u
    }
  }

  // Infer method from body if not explicit
  if (!result.method) result.method = result.body ? 'POST' : 'GET'

  return result
}

interface Props {
  aiEnabled?: boolean
  onCreateService?: (params: {
    base_url: string
    auth_type: string
    auth_token?: string
    auth_header_name?: string
    default_model?: string
    supports_streaming?: boolean
    extra_headers?: Record<string, string>
  }) => void
}

export default function QuickTestPlayground({ aiEnabled, onCreateService }: Props) {
  const [url, setUrl] = useState('')
  const [method, setMethod] = useState('POST')
  const [body, setBody] = useState('{\n  \n}')
  const [authType, setAuthType] = useState('none')
  const [authToken, setAuthToken] = useState('')
  const [authHeaderName, setAuthHeaderName] = useState('Authorization')
  const [extraHeaders, setExtraHeaders] = useState('')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<PlaygroundResponse | null>(null)
  const [error, setError] = useState('')
  const [curlInput, setCurlInput] = useState('')
  const [showCurlImport, setShowCurlImport] = useState(false)

  const handleParseCurl = () => {
    if (!curlInput.trim()) return
    try {
      const parsed = parseCurl(curlInput.trim())

      if (parsed.url) setUrl(parsed.url)
      if (parsed.method) setMethod(parsed.method)

      // Extract auth from headers
      const auth = parsed.headers['Authorization'] || parsed.headers['authorization']
      if (auth) {
        if (auth.toLowerCase().startsWith('bearer ')) {
          setAuthType('bearer')
          setAuthToken(auth.slice(7))
        } else {
          setAuthType('header')
          setAuthHeaderName('Authorization')
          setAuthToken(auth)
        }
        delete parsed.headers['Authorization']
        delete parsed.headers['authorization']
      }

      // Remove Content-Type from extra headers (we handle it internally)
      delete parsed.headers['Content-Type']
      delete parsed.headers['content-type']

      const extraHdrs = Object.entries(parsed.headers)
      if (extraHdrs.length > 0) {
        setExtraHeaders(extraHdrs.map(([k, v]) => `${k}: ${v}`).join('\n'))
      }

      if (parsed.body) {
        // Try to format as pretty JSON
        try {
          setBody(JSON.stringify(JSON.parse(parsed.body), null, 2))
        } catch {
          setBody(parsed.body)
        }
      }

      setShowCurlImport(false)
      setCurlInput('')
      toast.success('cURL parsed')
    } catch {
      toast.error('Failed to parse cURL')
    }
  }

  const parseExtraHeaders = (): Record<string, string> => {
    const result: Record<string, string> = {}
    for (const line of extraHeaders.split('\n')) {
      const idx = line.indexOf(':')
      if (idx > 0) {
        result[line.slice(0, idx).trim()] = line.slice(idx + 1).trim()
      }
    }
    return result
  }

  const handleSend = async () => {
    if (!url.trim() || loading) return
    setLoading(true)
    setResponse(null)
    setError('')

    let parsedBody: unknown = undefined
    if (body.trim() && method !== 'GET' && method !== 'DELETE') {
      try {
        parsedBody = JSON.parse(body)
      } catch {
        setError('Invalid JSON body')
        setLoading(false)
        return
      }
    }

    const headers = parseExtraHeaders()

    try {
      const { data } = await executeQuickTest({
        url: url.trim(),
        method,
        body: parsedBody,
        headers: Object.keys(headers).length > 0 ? headers : undefined,
        auth_type: authType,
        auth_token: authToken || undefined,
        auth_header_name: authHeaderName,
      })
      let formattedBody = data.body
      try {
        formattedBody = JSON.stringify(JSON.parse(data.body), null, 2)
      } catch { /* keep raw */ }
      setResponse({ ...data, body: formattedBody })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateService = () => {
    if (!url.trim()) return
    // Parse URL to extract base_url (without path)
    try {
      const parsed = new URL(url.trim())
      const base_url = `${parsed.protocol}//${parsed.host}`
      const hdrs = parseExtraHeaders()

      // Try to detect model from body
      let default_model: string | undefined
      let supports_streaming = false
      try {
        const b = JSON.parse(body)
        if (b.model) default_model = String(b.model)
        if (b.stream === true) supports_streaming = true
      } catch { /* ignore */ }

      onCreateService?.({
        base_url,
        auth_type: authType,
        auth_token: authToken || undefined,
        auth_header_name: authHeaderName !== 'Authorization' ? authHeaderName : undefined,
        default_model,
        supports_streaming,
        extra_headers: Object.keys(hdrs).length > 0 ? hdrs : undefined,
      })
    } catch {
      toast.error('Invalid URL')
    }
  }

  return (
    <div className="space-y-4">
      {/* cURL import */}
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowCurlImport(!showCurlImport)}
        >
          <Terminal className="h-3 w-3 mr-1" />
          Import from cURL
        </Button>
        <p className="text-xs text-muted-foreground">
          Test any HTTP endpoint directly, then create a proxy service from working config
        </p>
      </div>

      {showCurlImport && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <Label className="text-xs">Paste cURL command</Label>
            <Textarea
              value={curlInput}
              onChange={(e) => setCurlInput(e.target.value)}
              placeholder={"curl -X POST https://api.example.com/v1/chat/completions \\\n  -H 'Authorization: Bearer sk-...' \\\n  -d '{\"model\": \"gpt-4\", \"messages\": [...]}'"}
              rows={4}
              className="font-mono text-xs"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleParseCurl} disabled={!curlInput.trim()}>
                <Terminal className="h-3 w-3 mr-1" />
                Parse
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setShowCurlImport(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* URL + Method */}
      <div className="flex gap-2 items-end">
        <div>
          <Label className="text-xs">Method</Label>
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            className="mt-1 flex h-9 w-24 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {METHODS.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <Label className="text-xs">Full URL</Label>
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://api.example.com/v1/chat/completions"
            className="mt-1 font-mono text-xs"
          />
        </div>
        <Button onClick={handleSend} disabled={loading || !url.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
          Send
        </Button>
      </div>

      {/* Auth */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <Label className="text-xs">Auth Type</Label>
          <Select value={authType} onValueChange={setAuthType}>
            <SelectTrigger className="mt-1">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {AUTH_TYPES.map((t) => (
                <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {authType !== 'none' && (
          <div className={authType === 'header' ? '' : 'col-span-2'}>
            <Label className="text-xs">Token / Key</Label>
            <Input
              value={authToken}
              onChange={(e) => setAuthToken(e.target.value)}
              placeholder={authType === 'bearer' ? 'sk-...' : 'token value'}
              className="mt-1 font-mono text-xs"
              type="password"
            />
          </div>
        )}
        {authType === 'header' && (
          <div>
            <Label className="text-xs">Header Name</Label>
            <Input
              value={authHeaderName}
              onChange={(e) => setAuthHeaderName(e.target.value)}
              placeholder="Authorization"
              className="mt-1 text-xs"
            />
          </div>
        )}
      </div>

      {/* Extra Headers */}
      <div>
        <Label className="text-xs">Extra Headers (one per line: Name: Value)</Label>
        <Textarea
          value={extraHeaders}
          onChange={(e) => setExtraHeaders(e.target.value)}
          placeholder={"X-Custom-Header: value\nAccept: application/json"}
          rows={2}
          className="mt-1 font-mono text-xs"
        />
      </div>

      {/* Body */}
      {method !== 'GET' && method !== 'DELETE' && (
        <div>
          <Label className="text-xs">Request Body (JSON)</Label>
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="mt-1 font-mono text-xs"
            rows={8}
          />
        </div>
      )}

      {/* Response */}
      {response && (
        <>
          <div className="flex items-center gap-2">
            <ResponseMeta
              statusCode={response.status_code}
              durationMs={response.duration_ms}
              responseSize={response.response_size}
            />
            {response.status_code < 400 && onCreateService && (
              <Button variant="default" size="sm" onClick={handleCreateService}>
                <Plus className="h-4 w-4 mr-1" />
                Create Service
              </Button>
            )}
          </div>
          <Card>
            <CardContent className="p-0">
              <pre className="p-4 text-xs font-mono overflow-auto max-h-[400px] whitespace-pre-wrap">
                {response.body}
              </pre>
            </CardContent>
          </Card>
        </>
      )}

      {error && (
        <Card className="border-red-500/30">
          <CardContent className="p-4 text-sm text-red-500 font-mono whitespace-pre-wrap">
            {error}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
