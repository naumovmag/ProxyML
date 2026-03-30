export function parseCurl(raw: string): {
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

  // Extract body: -d 'data' or --data 'data' or --data-raw 'data' or --data-binary 'data'
  const bodyMatch = s.match(/(?:-d|--data|--data-raw|--data-binary)\s+'([\s\S]*?)'/i)
    || s.match(/(?:-d|--data|--data-raw|--data-binary)\s+"([\s\S]*?)"/i)
  if (bodyMatch) result.body = bodyMatch[1]

  // Extract URL: first try explicit http(s)://, then find curl's positional argument
  const urlMatch = s.match(/['"]?(https?:\/\/[^\s'"]+)['"]?/)
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

interface ServiceConfig {
  name: string
  slug: string
  base_url: string
  service_type: string
  auth_type: string
  auth_token: string | null
  auth_header_name: string
  default_model: string | null
  supports_streaming: boolean
  extra_headers: Record<string, string> | null
  health_check_path: string | null
  timeout_seconds: number
  tags: string[]
  description: string | null
}

export function parseCurlToServiceConfig(raw: string): ServiceConfig {
  const parsed = parseCurl(raw)

  if (!parsed.url) {
    throw new Error('Could not extract URL from cURL command')
  }

  let parsedUrl: URL
  try {
    parsedUrl = new URL(parsed.url)
  } catch {
    throw new Error(`Invalid URL: ${parsed.url}`)
  }

  const base_url = `${parsedUrl.protocol}//${parsedUrl.host}`
  const path = parsedUrl.pathname

  // Detect service_type from path
  let service_type = 'custom'
  if (/\/chat\/completions/i.test(path)) service_type = 'llm_chat'
  else if (/\/embeddings/i.test(path)) service_type = 'embedding'
  else if (/\/audio\/transcriptions/i.test(path)) service_type = 'stt'
  else if (/\/audio\/speech/i.test(path)) service_type = 'tts'

  // Extract auth
  let auth_type = 'none'
  let auth_token: string | null = null
  let auth_header_name = 'Authorization'

  const authHeader = parsed.headers['Authorization'] || parsed.headers['authorization']
  const xApiKey = parsed.headers['X-Api-Key'] || parsed.headers['x-api-key']
  const apiKey = parsed.headers['api-key'] || parsed.headers['Api-Key']

  if (authHeader) {
    if (authHeader.toLowerCase().startsWith('bearer ')) {
      auth_type = 'bearer'
      auth_token = authHeader.slice(7)
    } else {
      auth_type = 'header'
      auth_token = authHeader
    }
  } else if (xApiKey) {
    auth_type = 'header'
    auth_header_name = 'X-Api-Key'
    auth_token = xApiKey
  } else if (apiKey) {
    auth_type = 'header'
    auth_header_name = 'api-key'
    auth_token = apiKey
  }

  // Parse body JSON for model and streaming
  let default_model: string | null = null
  let supports_streaming = false
  if (parsed.body) {
    try {
      const bodyJson = JSON.parse(parsed.body)
      if (bodyJson.model) default_model = String(bodyJson.model)
      if (bodyJson.stream === true) supports_streaming = true
    } catch { /* body not JSON, skip */ }
  }

  // Build extra_headers (exclude standard/auth headers)
  const skipHeaders = new Set([
    'content-type', 'authorization', 'host', 'accept', 'user-agent',
    auth_header_name.toLowerCase(),
  ])
  const extra: Record<string, string> = {}
  for (const [k, v] of Object.entries(parsed.headers)) {
    if (!skipHeaders.has(k.toLowerCase())) {
      extra[k] = v
    }
  }
  const extra_headers = Object.keys(extra).length > 0 ? extra : null

  // Generate name from hostname
  const hostname = parsedUrl.hostname
  let baseName = hostname
    .replace(/^(api|www)\./, '')
    .split('.')[0]
  baseName = baseName.charAt(0).toUpperCase() + baseName.slice(1)

  const typeSuffix: Record<string, string> = {
    llm_chat: 'Chat',
    embedding: 'Embedding',
    stt: 'STT',
    tts: 'TTS',
  }
  const suffix = typeSuffix[service_type]
  const name = suffix ? `${baseName} ${suffix}` : baseName

  // Generate slug
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')

  // Health check path
  const health_check_path = (service_type === 'llm_chat' || service_type === 'embedding')
    ? '/v1/models'
    : null

  // Timeout
  const timeout_seconds = 0

  // Tags
  const tagsMap: Record<string, string[]> = {
    llm_chat: ['llm', 'chat'],
    embedding: ['embedding'],
    stt: ['audio', 'stt'],
    tts: ['audio', 'tts'],
  }
  const tags = tagsMap[service_type] || []

  return {
    name,
    slug,
    base_url,
    service_type,
    auth_type,
    auth_token,
    auth_header_name,
    default_model,
    supports_streaming,
    extra_headers,
    health_check_path,
    timeout_seconds,
    tags,
    description: null,
  }
}
