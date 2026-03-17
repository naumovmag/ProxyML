import { useEffect, useState } from 'react'
import { fetchSettings, updateSettings, SystemSettings } from '@/api/settings'
import { fetchServices, Service } from '@/api/services'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Save, Sparkles, Bot } from 'lucide-react'
import { toast } from 'sonner'

export default function SettingsPage() {
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [services, setServices] = useState<Service[]>([])
  const [saving, setSaving] = useState(false)

  const [aiEnabled, setAiEnabled] = useState(false)
  const [llmSlug, setLlmSlug] = useState<string | null>(null)
  const [llmModel, setLlmModel] = useState('')

  useEffect(() => {
    fetchSettings().then((r) => {
      setSettings(r.data)
      setAiEnabled(r.data.ai_enabled)
      setLlmSlug(r.data.llm_service_slug)
      setLlmModel(r.data.llm_model || '')
    })
    fetchServices().then((r) => setServices(r.data))
  }, [])

  const llmServices = services.filter((s) => s.service_type === 'llm_chat')
  const selectedService = services.find((s) => s.slug === llmSlug)

  const handleSave = async () => {
    setSaving(true)
    try {
      const { data } = await updateSettings({
        ai_enabled: aiEnabled,
        llm_service_slug: llmSlug,
        llm_model: llmModel || null,
      })
      setSettings(data)
      toast.success('Settings saved')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Settings</h2>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* AI Assistant */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-primary" />
              <div>
                <CardTitle>AI Assistant</CardTitle>
                <CardDescription className="mt-1">
                  Configure an LLM service to enable AI-powered features across ProxyML
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-base">Enable AI Assistant</Label>
                <p className="text-sm text-muted-foreground mt-1">
                  cURL parsing, error analysis, health diagnostics, dashboard insights
                </p>
              </div>
              <Switch checked={aiEnabled} onCheckedChange={setAiEnabled} />
            </div>

            {aiEnabled && (
              <>
                <div className="space-y-2">
                  <Label>LLM Service</Label>
                  <Select value={llmSlug || '_none'} onValueChange={(v) => setLlmSlug(v === '_none' ? null : v)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select LLM service" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="_none">Not selected</SelectItem>
                      {llmServices.map((s) => (
                        <SelectItem key={s.slug} value={s.slug}>
                          <div className="flex items-center gap-2">
                            <Bot className="h-3.5 w-3.5" />
                            {s.name}
                            <span className="text-muted-foreground">({s.slug})</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {llmServices.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      No LLM services found. Create a service with type "llm_chat" first.
                    </p>
                  )}
                  {selectedService && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      <Badge variant="outline">{selectedService.base_url}</Badge>
                      {selectedService.default_model && (
                        <Badge variant="outline">Model: {selectedService.default_model}</Badge>
                      )}
                      <Badge variant={selectedService.is_active ? 'success' : 'secondary'}>
                        {selectedService.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>Model Override</Label>
                  <Input
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                    placeholder={selectedService?.default_model || 'Use service default model'}
                  />
                  <p className="text-sm text-muted-foreground">
                    Leave empty to use the service's default model
                  </p>
                </div>
              </>
            )}

            <div className="flex justify-end pt-2">
              <Button onClick={handleSave} disabled={saving}>
                <Save className="h-4 w-4 mr-2" />
                {saving ? 'Saving...' : 'Save Settings'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* AI capabilities info */}
        {aiEnabled && llmSlug && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">AI Features</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 text-sm">
                <div className="flex items-start gap-3">
                  <Badge variant="outline" className="shrink-0 mt-0.5">Services</Badge>
                  <div>
                    <span className="font-medium">Create from cURL</span> — paste a cURL command to auto-create a service with all fields parsed
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Badge variant="outline" className="shrink-0 mt-0.5">Services</Badge>
                  <div>
                    <span className="font-medium">Generate description</span> — auto-generate service descriptions
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Badge variant="outline" className="shrink-0 mt-0.5">Dashboard</Badge>
                  <div>
                    <span className="font-medium">AI Summary</span> — get insights about your traffic patterns
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Badge variant="outline" className="shrink-0 mt-0.5">Dashboard</Badge>
                  <div>
                    <span className="font-medium">Error analysis</span> — click on any error log to get AI diagnosis
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Badge variant="outline" className="shrink-0 mt-0.5">Health</Badge>
                  <div>
                    <span className="font-medium">Diagnose</span> — get AI-powered diagnosis for failed health checks
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
