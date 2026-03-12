import { useEffect, useState } from 'react'
import { fetchServices, createService, updateService, deleteService, checkServiceHealth, Service, ServiceCreate, HealthCheckResult } from '@/api/services'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Plus, Trash2, Edit, Wifi, WifiOff, Loader2, CheckCircle, XCircle } from 'lucide-react'
import { toast } from 'sonner'

const SERVICE_TYPES = ['llm_chat', 'embedding', 'stt', 'tts', 'custom']
const AUTH_TYPES = ['none', 'bearer', 'header', 'query_param']

const emptyForm: ServiceCreate = {
  name: '', slug: '', service_type: 'custom', base_url: '', auth_type: 'none',
  auth_token: null, auth_header_name: 'Authorization', default_model: null,
  timeout_seconds: 120, supports_streaming: false, extra_headers: null,
  health_check_path: null, health_check_method: 'GET', description: null,
  tags: [], request_schema_hint: null, is_active: true,
}

export default function ServicesPage() {
  const [services, setServices] = useState<Service[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState<ServiceCreate>(emptyForm)
  const [healthResults, setHealthResults] = useState<Record<string, { loading: boolean; result?: HealthCheckResult }>>({})
  const [tagsInput, setTagsInput] = useState('')

  const load = () => fetchServices().then((r) => setServices(r.data))
  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditId(null)
    setForm(emptyForm)
    setTagsInput('')
    setDialogOpen(true)
  }

  const openEdit = (s: Service) => {
    setEditId(s.id)
    setForm({
      name: s.name, slug: s.slug, service_type: s.service_type, base_url: s.base_url,
      auth_type: s.auth_type, auth_token: s.auth_token, auth_header_name: s.auth_header_name,
      default_model: s.default_model, timeout_seconds: s.timeout_seconds,
      supports_streaming: s.supports_streaming, extra_headers: s.extra_headers,
      health_check_path: s.health_check_path, health_check_method: s.health_check_method,
      description: s.description, tags: s.tags, request_schema_hint: s.request_schema_hint,
      is_active: s.is_active,
    })
    setTagsInput(s.tags.join(', '))
    setDialogOpen(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const data = { ...form, tags: tagsInput.split(',').map((t) => t.trim()).filter(Boolean) }
    try {
      if (editId) {
        await updateService(editId, data)
        toast.success('Service updated')
      } else {
        await createService(data)
        toast.success('Service created')
      }
      setDialogOpen(false)
      load()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error saving service')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this service?')) return
    await deleteService(id)
    toast.success('Service deleted')
    load()
  }

  const handleCheck = async (id: string) => {
    setHealthResults((prev) => ({ ...prev, [id]: { loading: true } }))
    try {
      const { data } = await checkServiceHealth(id)
      setHealthResults((prev) => ({ ...prev, [id]: { loading: false, result: data } }))
    } catch {
      setHealthResults((prev) => ({ ...prev, [id]: { loading: false, result: { service_id: id, service_name: '', status: 'error', detail: 'Request failed', response_time_ms: null } } }))
    }
  }

  const setField = (key: string, value: any) => setForm((prev) => ({ ...prev, [key]: value }))

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Services</h2>
        <Button onClick={openCreate}><Plus className="h-4 w-4 mr-2" />Add Service</Button>
      </div>

      <div className="grid gap-4">
        {services.map((s) => {
          const health = healthResults[s.id]
          return (
            <Card key={s.id}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="flex items-center gap-3">
                  <CardTitle className="text-lg">{s.name}</CardTitle>
                  <Badge variant={s.is_active ? 'success' : 'secondary'}>{s.is_active ? 'Active' : 'Inactive'}</Badge>
                  <Badge variant="outline">{s.service_type}</Badge>
                  {s.supports_streaming && <Badge variant="warning">SSE</Badge>}
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => handleCheck(s.id)} disabled={health?.loading}>
                    {health?.loading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : health?.result?.status === 'ok' ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : health?.result?.status === 'error' ? (
                      <XCircle className="h-4 w-4 text-red-500" />
                    ) : (
                      <Wifi className="h-4 w-4" />
                    )}
                    <span className="ml-1">Check</span>
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => openEdit(s)}><Edit className="h-4 w-4" /></Button>
                  <Button variant="ghost" size="icon" onClick={() => handleDelete(s.id)}><Trash2 className="h-4 w-4 text-destructive" /></Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-muted-foreground space-y-1">
                  <div><span className="font-medium">URL:</span> {s.base_url}</div>
                  <div><span className="font-medium">Slug:</span> /api/v1/proxy/{s.slug}/</div>
                  {s.description && <div><span className="font-medium">Description:</span> {s.description}</div>}
                  {health?.result && (
                    <div className="mt-2">
                      <span className="font-medium">Health:</span>{' '}
                      <span className={health.result.status === 'ok' ? 'text-green-500' : 'text-red-500'}>
                        {health.result.status} - {health.result.detail}
                      </span>
                      {health.result.response_time_ms && <span> ({health.result.response_time_ms}ms)</span>}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}
        {services.length === 0 && (
          <Card>
            <CardContent className="p-12 text-center text-muted-foreground">
              No services yet. Click "Add Service" to create one.
            </CardContent>
          </Card>
        )}
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editId ? 'Edit Service' : 'Add Service'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={form.name} onChange={(e) => setField('name', e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label>Slug</Label>
                <Input value={form.slug} onChange={(e) => setField('slug', e.target.value)} required placeholder="my-service" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Type</Label>
                <Select value={form.service_type} onValueChange={(v) => setField('service_type', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {SERVICE_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Auth Type</Label>
                <Select value={form.auth_type} onValueChange={(v) => setField('auth_type', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {AUTH_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Base URL</Label>
              <Input value={form.base_url} onChange={(e) => setField('base_url', e.target.value)} required placeholder="http://backend:8080" />
            </div>

            {form.auth_type !== 'none' && (
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Auth Token</Label>
                  <Input value={form.auth_token || ''} onChange={(e) => setField('auth_token', e.target.value || null)} />
                </div>
                <div className="space-y-2">
                  <Label>Auth Header Name</Label>
                  <Input value={form.auth_header_name || 'Authorization'} onChange={(e) => setField('auth_header_name', e.target.value)} />
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Default Model</Label>
                <Input value={form.default_model || ''} onChange={(e) => setField('default_model', e.target.value || null)} />
              </div>
              <div className="space-y-2">
                <Label>Timeout (seconds)</Label>
                <Input type="number" value={form.timeout_seconds} onChange={(e) => setField('timeout_seconds', parseInt(e.target.value) || 120)} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Health Check Path</Label>
                <Input value={form.health_check_path || ''} onChange={(e) => setField('health_check_path', e.target.value || null)} placeholder="/v1/models" />
              </div>
              <div className="space-y-2">
                <Label>Health Check Method</Label>
                <Select value={form.health_check_method || 'GET'} onValueChange={(v) => setField('health_check_method', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="GET">GET</SelectItem>
                    <SelectItem value="POST">POST</SelectItem>
                    <SelectItem value="HEAD">HEAD</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Description</Label>
              <Input value={form.description || ''} onChange={(e) => setField('description', e.target.value || null)} />
            </div>

            <div className="space-y-2">
              <Label>Tags (comma separated)</Label>
              <Input value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} placeholder="llm, chat, openai" />
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Switch checked={form.supports_streaming} onCheckedChange={(v) => setField('supports_streaming', v)} />
                <Label>Supports Streaming</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={form.is_active} onCheckedChange={(v) => setField('is_active', v)} />
                <Label>Active</Label>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-4">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button type="submit">{editId ? 'Update' : 'Create'}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
