import { useState, useEffect } from 'react'
import {
  Mail,
  Smartphone,
  Send,
  Settings,
  Trash2,
  Loader2,
  ChevronDown,
  ChevronUp,
  FlaskConical,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import {
  updateChannel,
  deleteChannel,
  testChannel,
  type VerificationChannel,
  type ChannelTypeSchema,
} from '@/api/verificationChannels'
import { EmailChannelSettings } from './EmailChannelSettings'

const channelIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  email: Mail,
  sms: Smartphone,
  telegram: Send,
}

interface SettingsFieldDef {
  key: string
  label: string
  type: 'text' | 'number' | 'select'
  placeholder?: string
  options?: { value: string; label: string }[]
}

const channelSettingsFields: Record<string, SettingsFieldDef[]> = {
  email: [
    { key: 'from_address', label: 'From Address', type: 'text', placeholder: 'noreply@example.com' },
    { key: 'from_name', label: 'From Name', type: 'text', placeholder: 'My App' },
    {
      key: 'verification_mode',
      label: 'Verification Mode',
      type: 'select',
      options: [
        { value: 'code', label: 'Code' },
        { value: 'link', label: 'Link' },
      ],
    },
    { key: 'code_ttl_minutes', label: 'Code TTL (minutes)', type: 'number', placeholder: '10' },
    { key: 'redirect_url', label: 'Redirect URL', type: 'text', placeholder: 'https://example.com/verified' },
    { key: 'template_subject', label: 'Email Subject Template', type: 'text', placeholder: 'Verify your email' },
    { key: 'template_body', label: 'Email Body Template', type: 'text', placeholder: 'Your code is {{code}}' },
  ],
  sms: [
    { key: 'message_template', label: 'Message Template', type: 'text', placeholder: 'Your code is {{code}}' },
    { key: 'code_length', label: 'Code Length', type: 'number', placeholder: '6' },
    { key: 'code_ttl_minutes', label: 'Code TTL (minutes)', type: 'number', placeholder: '10' },
  ],
  telegram: [
    { key: 'bot_username', label: 'Bot Username', type: 'text', placeholder: '@mybot' },
    { key: 'message_template', label: 'Message Template', type: 'text', placeholder: 'Your code is {{code}}' },
    { key: 'code_length', label: 'Code Length', type: 'number', placeholder: '6' },
    { key: 'code_ttl_minutes', label: 'Code TTL (minutes)', type: 'number', placeholder: '10' },
  ],
}

interface ChannelCardProps {
  channel: VerificationChannel
  providerLabel: string
  channelLabel: string
  systemId: string
  systemName: string
  providers: Record<string, ChannelTypeSchema>
  onUpdate: () => void
}

export function ChannelCard({
  channel,
  providerLabel,
  channelLabel,
  systemId,
  systemName,
  providers,
  onUpdate,
}: ChannelCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [showTest, setShowTest] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [testTo, setTestTo] = useState('')
  const [testing, setTesting] = useState(false)

  // Editable state for config section
  const [configValues, setConfigValues] = useState<Record<string, any>>({ ...channel.provider_config })
  const [settingsValues, setSettingsValues] = useState<Record<string, any>>({ ...channel.settings })
  const [isRequired, setIsRequired] = useState(channel.is_required)

  // Sync state with props when channel changes
  useEffect(() => {
    setConfigValues({ ...channel.provider_config })
    setSettingsValues({ ...channel.settings })
    setIsRequired(channel.is_required)
  }, [channel.id, channel.updated_at])

  const Icon = channelIcons[channel.channel_type] || Mail

  const providerSchema = providers[channel.channel_type]?.providers?.[channel.provider_type]
  const configFields = providerSchema?.config_schema || []
  const settingsFields = channelSettingsFields[channel.channel_type] || []

  const testPlaceholder =
    channel.channel_type === 'email'
      ? 'user@example.com'
      : channel.channel_type === 'sms'
        ? '+1234567890'
        : 'chat_id'

  const handleToggle = async () => {
    try {
      setToggling(true)
      await updateChannel(systemId, channel.id, { is_enabled: !channel.is_enabled })
      toast.success(`Channel ${channel.is_enabled ? 'disabled' : 'enabled'}`)
      onUpdate()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to toggle channel')
    } finally {
      setToggling(false)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      await updateChannel(systemId, channel.id, {
        provider_config: configValues,
        settings: settingsValues,
        is_required: isRequired,
      })
      toast.success('Channel updated')
      onUpdate()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to update channel')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    try {
      await deleteChannel(systemId, channel.id)
      toast.success('Channel deleted')
      onUpdate()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to delete channel')
    }
  }

  const handleTest = async () => {
    if (!testTo.trim()) return
    try {
      setTesting(true)
      const result = await testChannel(systemId, channel.id, testTo.trim())
      if (result.ok) {
        toast.success(result.message || 'Test sent successfully')
        setTestTo('')
      } else {
        toast.error(result.message || 'Test failed')
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Test failed')
    } finally {
      setTesting(false)
    }
  }

  const handleConfigChange = (name: string, value: string) => {
    setConfigValues((prev) => ({ ...prev, [name]: value }))
  }

  const handleSettingsChange = (key: string, value: string | number) => {
    setSettingsValues((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <>
      <Card>
        <CardContent className="p-4">
          {/* Header row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Icon className="w-5 h-5 text-muted-foreground" />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{channelLabel}</span>
                  <Badge variant="outline" className="text-xs">
                    {providerLabel}
                  </Badge>
                  {channel.is_enabled ? (
                    <Badge className="text-xs bg-emerald-600/20 text-emerald-400 border-emerald-600/30">
                      Enabled
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="text-xs">
                      Disabled
                    </Badge>
                  )}
                  {channel.is_required && (
                    <Badge variant="secondary" className="text-xs">
                      Required
                    </Badge>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowTest(true)}
                title="Test channel"
              >
                <FlaskConical className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setExpanded(!expanded)}
                title="Configure"
              >
                {expanded ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <Settings className="w-4 h-4" />
                )}
              </Button>
              <Switch
                checked={channel.is_enabled}
                onCheckedChange={handleToggle}
                disabled={toggling}
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDelete(true)}
                title="Delete channel"
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Expandable config section */}
          {expanded && channel.channel_type === 'email' && (
            <div className="mt-4 pt-4 border-t">
              <EmailChannelSettings
                channel={channel}
                systemId={systemId}
                systemName={systemName}
                providers={providers}
                onUpdate={onUpdate}
              />
            </div>
          )}

          {expanded && channel.channel_type !== 'email' && (
            <div className="mt-4 pt-4 border-t space-y-6">
              {/* Provider config fields */}
              {configFields.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-sm font-medium text-muted-foreground">Provider Configuration</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {configFields.map((field) => (
                      <div key={field.name} className="space-y-1.5">
                        <Label className="text-xs">
                          {field.label}
                          {field.required && <span className="text-destructive ml-0.5">*</span>}
                        </Label>
                        <Input
                          type={field.secret ? 'password' : 'text'}
                          placeholder={field.placeholder}
                          value={configValues[field.name] || ''}
                          onChange={(e) => handleConfigChange(field.name, e.target.value)}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Channel settings */}
              {settingsFields.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-sm font-medium text-muted-foreground">Channel Settings</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {settingsFields.map((field) => (
                      <div key={field.key} className="space-y-1.5">
                        <Label className="text-xs">{field.label}</Label>
                        {field.type === 'select' ? (
                          <Select
                            value={settingsValues[field.key] || field.options?.[0]?.value || ''}
                            onValueChange={(val) => handleSettingsChange(field.key, val)}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {field.options?.map((opt) => (
                                <SelectItem key={opt.value} value={opt.value}>
                                  {opt.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Input
                            type={field.type}
                            placeholder={field.placeholder}
                            value={settingsValues[field.key] ?? ''}
                            onChange={(e) =>
                              handleSettingsChange(
                                field.key,
                                field.type === 'number' ? Number(e.target.value) : e.target.value
                              )
                            }
                          />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Required switch */}
              <div className="flex items-center gap-3">
                <Switch
                  checked={isRequired}
                  onCheckedChange={setIsRequired}
                />
                <Label className="text-sm">Required for registration</Label>
              </div>

              {/* Save button */}
              <div className="flex justify-end">
                <Button onClick={handleSave} disabled={saving} size="sm">
                  {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
                  Save
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Test dialog */}
      <Dialog open={showTest} onOpenChange={setShowTest}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Test {channelLabel} Channel</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label className="text-sm">Recipient</Label>
              <Input
                placeholder={testPlaceholder}
                value={testTo}
                onChange={(e) => setTestTo(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowTest(false)}>
                Cancel
              </Button>
              <Button onClick={handleTest} disabled={testing || !testTo.trim()}>
                {testing && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
                Send Test
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete confirm dialog */}
      <ConfirmDialog
        open={showDelete}
        onOpenChange={setShowDelete}
        title="Delete Channel"
        description={`Are you sure you want to delete the ${channelLabel} (${providerLabel}) channel? This action cannot be undone.`}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={handleDelete}
      />
    </>
  )
}
