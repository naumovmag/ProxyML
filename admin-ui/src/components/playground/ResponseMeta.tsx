import { Badge } from '@/components/ui/badge'

interface TokenUsage {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
}

interface Props {
  statusCode?: number
  durationMs?: number
  responseSize?: number
  tokenUsage?: TokenUsage | null
}

export default function ResponseMeta({ statusCode, durationMs, responseSize, tokenUsage }: Props) {
  if (statusCode == null && durationMs == null) return null

  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
      {statusCode != null && (
        <Badge variant={statusCode < 400 ? 'default' : 'destructive'} className="text-xs">
          {statusCode}
        </Badge>
      )}
      {durationMs != null && <span>{durationMs} ms</span>}
      {responseSize != null && responseSize > 0 && (
        <span>{responseSize > 1024 ? `${(responseSize / 1024).toFixed(1)} KB` : `${responseSize} B`}</span>
      )}
      {tokenUsage && (
        <span className="font-mono">
          {tokenUsage.prompt_tokens != null && `in: ${tokenUsage.prompt_tokens}`}
          {tokenUsage.completion_tokens != null && ` out: ${tokenUsage.completion_tokens}`}
          {tokenUsage.total_tokens != null && ` (${tokenUsage.total_tokens} total)`}
        </span>
      )}
    </div>
  )
}
