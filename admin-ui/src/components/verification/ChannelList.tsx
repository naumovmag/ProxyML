import { useEffect, useState, useCallback } from 'react'
import { Plus, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { ChannelCard } from './ChannelCard'
import { AddChannelDialog } from './AddChannelDialog'
import {
  fetchChannels,
  fetchVerificationProviders,
  type VerificationChannel,
  type ChannelTypeSchema,
} from '@/api/verificationChannels'

interface ChannelListProps {
  systemId: string
  systemName: string
}

export function ChannelList({ systemId, systemName }: ChannelListProps) {
  const [channels, setChannels] = useState<VerificationChannel[]>([])
  const [providers, setProviders] = useState<Record<string, ChannelTypeSchema>>({})
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const [ch, prov] = await Promise.all([
        fetchChannels(systemId),
        fetchVerificationProviders(),
      ])
      setChannels(ch)
      setProviders(prov)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to load verification channels')
    } finally {
      setLoading(false)
    }
  }, [systemId])

  useEffect(() => {
    loadData()
  }, [loadData])

  const getChannelLabel = (channelType: string): string => {
    return providers[channelType]?.label || channelType
  }

  const getProviderLabel = (channelType: string, providerType: string): string => {
    return providers[channelType]?.providers?.[providerType]?.label || providerType
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Verification Channels</h3>
        <Button onClick={() => setShowAdd(true)} size="sm">
          <Plus className="w-4 h-4 mr-1" /> Add Channel
        </Button>
      </div>

      {channels.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No verification channels configured.
        </p>
      )}

      {channels.map((ch) => (
        <ChannelCard
          key={ch.id}
          channel={ch}
          channelLabel={getChannelLabel(ch.channel_type)}
          providerLabel={getProviderLabel(ch.channel_type, ch.provider_type)}
          systemId={systemId}
          systemName={systemName}
          providers={providers}
          onUpdate={loadData}
        />
      ))}

      <AddChannelDialog
        open={showAdd}
        onClose={() => setShowAdd(false)}
        systemId={systemId}
        providers={providers}
        existingTypes={channels.map((ch) => ch.channel_type)}
        onCreated={loadData}
      />
    </div>
  )
}
