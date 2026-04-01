import { useState, useEffect } from 'react'
import { Save, Loader2, Send, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import {
  updateChannel,
  testChannel,
  type VerificationChannel,
  type ChannelTypeSchema,
} from '@/api/verificationChannels'
import { aiGenerateEmailTemplate } from '@/api/ai'
import { fetchSettings, type SystemSettings } from '@/api/settings'

interface EmailChannelSettingsProps {
  channel: VerificationChannel
  systemId: string
  systemName: string
  providers: Record<string, ChannelTypeSchema>
  onUpdate: () => void
}

export function EmailChannelSettings({
  channel,
  systemId,
  systemName,
  providers,
  onUpdate,
}: EmailChannelSettingsProps) {
  const [configValues, setConfigValues] = useState<Record<string, any>>({ ...channel.provider_config })
  const [fromAddress, setFromAddress] = useState(channel.settings.from_address || '')
  const [fromName, setFromName] = useState(channel.settings.from_name || '')
  const [verificationMode, setVerificationMode] = useState(channel.settings.verification_mode || 'link')
  const [codeTtl, setCodeTtl] = useState(channel.settings.code_ttl_minutes || 1440)
  const [redirectUrl, setRedirectUrl] = useState(channel.settings.redirect_url || '')
  const [templateSubject, setTemplateSubject] = useState(channel.settings.template_subject || '')
  const [templateBody, setTemplateBody] = useState(channel.settings.template_body || '')
  const [isRequired, setIsRequired] = useState(channel.is_required)
  const [emailPreview, setEmailPreview] = useState(false)

  const [saving, setSaving] = useState(false)
  const [testTo, setTestTo] = useState('')
  const [testing, setTesting] = useState(false)
  const [aiGenerating, setAiGenerating] = useState(false)
  const [aiSettings, setAiSettings] = useState<SystemSettings | null>(null)

  // Sync state with channel prop
  useEffect(() => {
    setConfigValues({ ...channel.provider_config })
    setFromAddress(channel.settings.from_address || '')
    setFromName(channel.settings.from_name || '')
    setVerificationMode(channel.settings.verification_mode || 'link')
    setCodeTtl(channel.settings.code_ttl_minutes || 1440)
    setRedirectUrl(channel.settings.redirect_url || '')
    setTemplateSubject(channel.settings.template_subject || '')
    setTemplateBody(channel.settings.template_body || '')
    setIsRequired(channel.is_required)
  }, [channel.id, channel.updated_at])

  // Load AI settings on mount
  useEffect(() => {
    fetchSettings()
      .then((res) => setAiSettings(res.data))
      .catch(() => {})
  }, [])

  const providerSchema = providers[channel.channel_type]?.providers?.[channel.provider_type]
  const configFields = providerSchema?.config_schema || []

  const handleSave = async () => {
    try {
      setSaving(true)
      await updateChannel(systemId, channel.id, {
        provider_config: configValues,
        is_required: isRequired,
        settings: {
          from_address: fromAddress,
          from_name: fromName,
          verification_mode: verificationMode,
          code_ttl_minutes: codeTtl,
          redirect_url: redirectUrl,
          template_subject: templateSubject,
          template_body: templateBody,
        },
      })
      toast.success('Email channel settings saved')
      onUpdate()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to save email settings')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!testTo.trim()) return
    try {
      setTesting(true)
      const result = await testChannel(systemId, channel.id, testTo.trim())
      if (result.ok) {
        toast.success(result.message || 'Test email sent successfully')
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

  const handleAiGenerateTemplate = async () => {
    try {
      setAiGenerating(true)
      const { data: result } = await aiGenerateEmailTemplate({
        name: systemName,
        registration_fields: [],
        language: 'en',
        brand_color: '#2563eb',
      })
      setTemplateSubject(result.subject)
      setTemplateBody(result.body)
      toast.success('Template generated')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to generate template')
    } finally {
      setAiGenerating(false)
    }
  }

  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        {/* Required for login */}
        <div className="flex items-center space-x-2">
          <Switch checked={isRequired} onCheckedChange={setIsRequired} id="email-required" />
          <Label htmlFor="email-required">Required for login</Label>
        </div>

        {/* Provider config fields */}
        {configFields.length > 0 && (
          <div className="space-y-3 p-4 border rounded-md">
            <p className="text-sm font-medium">Provider Config: {channel.provider_type.toUpperCase()}</p>
            {configFields.map((field) => (
              <div key={field.name} className="grid grid-cols-3 gap-2 items-center">
                <Label>
                  {field.label}
                  {field.required && <span className="text-destructive ml-0.5">*</span>}
                </Label>
                {field.type === 'boolean' ? (
                  <div className="col-span-2 flex items-center space-x-2">
                    <Checkbox
                      checked={!!configValues[field.name]}
                      onCheckedChange={(v) =>
                        setConfigValues((prev) => ({ ...prev, [field.name]: !!v }))
                      }
                    />
                  </div>
                ) : (
                  <Input
                    className="col-span-2"
                    type={field.secret ? 'password' : field.type === 'number' ? 'number' : 'text'}
                    value={configValues[field.name] ?? ''}
                    onChange={(e) =>
                      setConfigValues((prev) => ({
                        ...prev,
                        [field.name]: field.type === 'number' ? Number(e.target.value) : e.target.value,
                      }))
                    }
                    placeholder={field.placeholder}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* From Address & From Name */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>From Address</Label>
            <Input
              value={fromAddress}
              onChange={(e) => setFromAddress(e.target.value)}
              placeholder="noreply@example.com"
            />
          </div>
          <div className="space-y-2">
            <Label>From Name</Label>
            <Input
              value={fromName}
              onChange={(e) => setFromName(e.target.value)}
              placeholder="My App"
            />
          </div>
        </div>

        {/* Verification Mode & Code TTL */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Verification Mode</Label>
            <Select value={verificationMode} onValueChange={setVerificationMode}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="link">Link</SelectItem>
                <SelectItem value="code">Code</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Verification Token TTL (minutes)</Label>
            <Input
              type="number"
              min={5}
              value={codeTtl}
              onChange={(e) => setCodeTtl(parseInt(e.target.value) || 1440)}
            />
          </div>
        </div>

        {/* Redirect URL */}
        <div className="space-y-2">
          <Label>Redirect URL after verification</Label>
          <Input
            value={redirectUrl}
            onChange={(e) => setRedirectUrl(e.target.value)}
            placeholder="https://myapp.com/verified"
          />
          <p className="text-xs text-muted-foreground">
            Leave empty to show a default "Email verified" page
          </p>
        </div>

        {/* Email Subject */}
        <div className="space-y-2">
          <Label>Email Subject</Label>
          <Input
            value={templateSubject}
            onChange={(e) => setTemplateSubject(e.target.value)}
            placeholder="Verify your email for {{system_name}}"
          />
        </div>

        {/* Email Body (HTML) with Code/Preview toggle & AI generate */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Email Body (HTML)</Label>
            <div className="flex items-center gap-2">
              {aiSettings?.ai_enabled && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAiGenerateTemplate}
                  disabled={aiGenerating}
                >
                  {aiGenerating ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5 mr-1" />
                  )}
                  Generate with AI
                </Button>
              )}
              <div className="flex border rounded-md overflow-hidden text-xs">
                <button
                  type="button"
                  onClick={() => setEmailPreview(false)}
                  className={`px-3 py-1 ${!emailPreview ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}
                >
                  Code
                </button>
                <button
                  type="button"
                  onClick={() => setEmailPreview(true)}
                  className={`px-3 py-1 ${emailPreview ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}
                >
                  Preview
                </button>
              </div>
            </div>
          </div>
          {!emailPreview ? (
            <>
              <textarea
                className="w-full min-h-[250px] rounded-md border bg-background px-3 py-2 text-sm font-mono"
                value={templateBody}
                onChange={(e) => setTemplateBody(e.target.value)}
                placeholder="Leave empty for default template"
              />
              <p className="text-xs text-muted-foreground">
                Placeholders: {'{{verification_link}}'}, {'{{user_email}}'}, {'{{system_name}}'}, {'{{ttl_hours}}'}
              </p>
            </>
          ) : (
            <div className="border rounded-md bg-white min-h-[250px] p-1">
              <iframe
                srcDoc={
                  (templateBody || '<p style="color:#999;text-align:center;padding:40px">No template — using default</p>')
                    .replace(/\{\{verification_link\}\}/g, '#')
                    .replace(/\{\{user_email\}\}/g, 'user@example.com')
                    .replace(/\{\{system_name\}\}/g, systemName)
                    .replace(/\{\{ttl_hours\}\}/g, String(Math.round(codeTtl / 60)))
                }
                className="w-full min-h-[250px] border-0"
                sandbox=""
                title="Email preview"
              />
            </div>
          )}
        </div>

        {/* Test send & Save */}
        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-2">
            <Input
              value={testTo}
              onChange={(e) => setTestTo(e.target.value)}
              placeholder="test@example.com"
              className="w-56"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleTest}
              disabled={testing || !testTo.trim()}
            >
              {testing ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : (
                <Send className="h-4 w-4 mr-1" />
              )}
              Send Test
            </Button>
          </div>
          <div className="ml-auto">
            <Button onClick={handleSave} disabled={saving}>
              <Save className="h-4 w-4 mr-2" />
              {saving ? 'Saving...' : 'Save Email Settings'}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
