import { useEffect, useState } from 'react'
import {
  fetchApiKeys, createApiKey, updateApiKey, deleteApiKey, toggleApiKey,
  ApiKey, ApiKeyCreate, ApiKeyUpdate,
} from '@/api/apiKeys'
import { fetchServices, Service } from '@/api/services'
import { fetchStatsByKey, fetchRecentLogs, KeyStats, RecentLog } from '@/api/stats'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Plus, Trash2, Copy, Check, Pencil, Shield, ShieldCheck, ShieldX, BarChart3, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null)
  const [newKey, setNewKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [confirmState, setConfirmState] = useState<{ open: boolean; onConfirm: () => void }>({ open: false, onConfirm: () => {} })
  const [keyStatsMap, setKeyStatsMap] = useState<Record<string, KeyStats>>({})
  const [statsModalKey, setStatsModalKey] = useState<ApiKey | null>(null)
  const [modalLogs, setModalLogs] = useState<RecentLog[]>([])
  const [modalLoading, setModalLoading] = useState(false)

  // Form state
  const [formName, setFormName] = useState('')
  const [formAllAccess, setFormAllAccess] = useState(true)
  const [formSelectedServices, setFormSelectedServices] = useState<string[]>([])
  const [formRateLimit, setFormRateLimit] = useState('')

  const load = async () => {
    const [keysRes, servicesRes, statsRes] = await Promise.all([
      fetchApiKeys(), fetchServices(), fetchStatsByKey(720),
    ])
    setKeys(keysRes.data)
    setServices(servicesRes.data)
    const map: Record<string, KeyStats> = {}
    for (const s of statsRes.data) {
      if (s.api_key_id) map[s.api_key_id] = s
    }
    setKeyStatsMap(map)
  }
  useEffect(() => { load() }, [])

  const resetForm = () => {
    setFormName('')
    setFormAllAccess(true)
    setFormSelectedServices([])
    setFormRateLimit('')
    setEditingKey(null)
    setNewKey(null)
    setCopied(false)
  }

  const openCreate = () => {
    resetForm()
    setDialogOpen(true)
  }

  const openEdit = (key: ApiKey) => {
    setEditingKey(key)
    setFormName(key.name)
    setFormAllAccess(key.allowed_services === null)
    setFormSelectedServices(key.allowed_services || [])
    setFormRateLimit(key.rate_limit_rpm?.toString() || '')
    setNewKey(null)
    setCopied(false)
    setDialogOpen(true)
  }

  const toggleService = (slug: string) => {
    setFormSelectedServices((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    )
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const payload: ApiKeyCreate = {
        name: formName,
        allowed_services: formAllAccess ? null : formSelectedServices,
        rate_limit_rpm: formRateLimit ? parseInt(formRateLimit) : null,
      }
      const { data } = await createApiKey(payload)
      setNewKey(data.raw_key)
      load()
      toast.success('API key created')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error creating key')
    }
  }

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingKey) return
    try {
      const payload: ApiKeyUpdate = {
        name: formName,
        rate_limit_rpm: formRateLimit ? parseInt(formRateLimit) : null,
      }
      if (formAllAccess) {
        payload.clear_allowed_services = true
      } else {
        payload.allowed_services = formSelectedServices
      }
      await updateApiKey(editingKey.id, payload)
      setDialogOpen(false)
      load()
      toast.success('API key updated')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error updating key')
    }
  }

  const handleCopy = () => {
    if (newKey) {
      navigator.clipboard.writeText(newKey)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      toast.success('Copied to clipboard')
    }
  }

  const handleDelete = (id: string) => {
    setConfirmState({
      open: true,
      onConfirm: async () => {
        await deleteApiKey(id)
        toast.success('API key deleted')
        load()
      },
    })
  }

  const handleToggle = async (id: string) => {
    await toggleApiKey(id)
    load()
  }

  const openStatsModal = async (key: ApiKey) => {
    setStatsModalKey(key)
    setModalLoading(true)
    setModalLogs([])
    try {
      const { data } = await fetchRecentLogs(100, { api_key_id: key.id })
      setModalLogs(data)
    } catch {
      setModalLogs([])
    } finally {
      setModalLoading(false)
    }
  }

  const getServiceName = (slug: string) => {
    const svc = services.find((s) => s.slug === slug)
    return svc ? svc.name : slug
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">API Keys</h2>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" />New API Key
        </Button>
      </div>

      <div className="space-y-3">
        {keys.map((k) => (
          <Card key={k.id}>
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{k.name}</span>
                    <Badge variant={k.is_active ? 'success' : 'secondary'}>
                      {k.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                    {k.allowed_services === null ? (
                      <Badge variant="outline" className="gap-1">
                        <ShieldCheck className="h-3 w-3" />All services
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="gap-1">
                        <Shield className="h-3 w-3" />{k.allowed_services.length} service{k.allowed_services.length !== 1 ? 's' : ''}
                      </Badge>
                    )}
                    {k.rate_limit_rpm && (
                      <Badge variant="outline">{k.rate_limit_rpm} rpm</Badge>
                    )}
                    <Badge
                      variant="outline"
                      className="gap-1 cursor-pointer hover:bg-muted"
                      onClick={(e) => { e.stopPropagation(); openStatsModal(k) }}
                    >
                      <BarChart3 className="h-3 w-3" />
                      {(keyStatsMap[k.id]?.request_count ?? 0).toLocaleString()} req
                    </Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    <span className="font-mono">{k.key_prefix}...</span>
                    {' | '}Created: {new Date(k.created_at).toLocaleDateString()}
                    {k.last_used_at && <>{' | '}Last used: {new Date(k.last_used_at).toLocaleDateString()}</>}
                    {k.expires_at && <>{' | '}Expires: {new Date(k.expires_at).toLocaleDateString()}</>}
                  </div>
                  {k.allowed_services && k.allowed_services.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {k.allowed_services.map((slug) => (
                        <Badge key={slug} variant="secondary" className="text-xs">
                          {getServiceName(slug)}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex gap-2 ml-4">
                  <Button variant="outline" size="sm" onClick={() => openEdit(k)}>
                    <Pencil className="h-4 w-4 mr-1" />Edit
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => handleToggle(k.id)}>
                    {k.is_active ? 'Disable' : 'Enable'}
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => handleDelete(k.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        {keys.length === 0 && (
          <Card>
            <CardContent className="p-12 text-center text-muted-foreground">
              No API keys yet. Click "New API Key" to create one.
            </CardContent>
          </Card>
        )}
      </div>

      <ConfirmDialog
        open={confirmState.open}
        onOpenChange={(open) => setConfirmState((s) => ({ ...s, open }))}
        title="Delete API key"
        description="Are you sure you want to delete this API key? This action cannot be undone."
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={confirmState.onConfirm}
      />

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {newKey ? 'API Key Created' : editingKey ? 'Edit API Key' : 'Create API Key'}
            </DialogTitle>
          </DialogHeader>

          {newKey ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Copy this key now. You won't be able to see it again.
              </p>
              <div className="flex gap-2">
                <Input value={newKey} readOnly className="font-mono text-sm" />
                <Button variant="outline" size="icon" onClick={handleCopy}>
                  {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
              <Button className="w-full" onClick={() => setDialogOpen(false)}>Done</Button>
            </div>
          ) : (
            <form onSubmit={editingKey ? handleUpdate : handleCreate} className="space-y-4">
              <div className="space-y-2">
                <Label>Key Name</Label>
                <Input value={formName} onChange={(e) => setFormName(e.target.value)} required placeholder="My API Key" />
              </div>

              <div className="space-y-2">
                <Label>Rate Limit (requests per minute)</Label>
                <Input
                  type="number"
                  value={formRateLimit}
                  onChange={(e) => setFormRateLimit(e.target.value)}
                  placeholder="No limit"
                  min={1}
                />
              </div>

              <div className="space-y-3">
                <Label>Service Access</Label>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="all-access"
                    checked={formAllAccess}
                    onCheckedChange={(checked) => {
                      setFormAllAccess(!!checked)
                      if (checked) setFormSelectedServices([])
                    }}
                  />
                  <label htmlFor="all-access" className="text-sm font-medium cursor-pointer">
                    Access to all services
                  </label>
                </div>

                {!formAllAccess && (
                  <div className="border rounded-md p-3 space-y-2 max-h-60 overflow-y-auto">
                    {services.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No services available</p>
                    ) : (
                      services.map((svc) => (
                        <div key={svc.slug} className="flex items-center space-x-2">
                          <Checkbox
                            id={`svc-${svc.slug}`}
                            checked={formSelectedServices.includes(svc.slug)}
                            onCheckedChange={() => toggleService(svc.slug)}
                          />
                          <label htmlFor={`svc-${svc.slug}`} className="text-sm cursor-pointer flex items-center gap-2">
                            {svc.name}
                            <span className="text-xs text-muted-foreground font-mono">{svc.slug}</span>
                          </label>
                        </div>
                      ))
                    )}
                    {!formAllAccess && formSelectedServices.length === 0 && services.length > 0 && (
                      <p className="text-xs text-destructive mt-1">Select at least one service</p>
                    )}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                <Button
                  type="submit"
                  disabled={!formAllAccess && formSelectedServices.length === 0}
                >
                  {editingKey ? 'Save' : 'Create'}
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
      {/* Stats Modal */}
      <Dialog open={!!statsModalKey} onOpenChange={(open) => { if (!open) setStatsModalKey(null) }}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Usage: {statsModalKey?.name}</DialogTitle>
          </DialogHeader>
          {statsModalKey && (
            <div className="space-y-4">
              <div className="flex gap-6 text-sm">
                <div>
                  <span className="text-muted-foreground">Requests: </span>
                  <span className="font-medium">{(keyStatsMap[statsModalKey.id]?.request_count ?? 0).toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Errors: </span>
                  <span className="font-medium text-destructive">{keyStatsMap[statsModalKey.id]?.error_count ?? 0}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Avg Duration: </span>
                  <span className="font-medium">{keyStatsMap[statsModalKey.id]?.avg_duration_ms ?? 0} ms</span>
                </div>
              </div>

              {modalLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="pb-2 pr-4">Time</th>
                        <th className="pb-2 pr-4">Service</th>
                        <th className="pb-2 pr-4">Method</th>
                        <th className="pb-2 pr-4">Path</th>
                        <th className="pb-2 pr-4">Status</th>
                        <th className="pb-2 pr-4 text-right">Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {modalLogs.map((log) => (
                        <tr key={log.id} className="border-b border-border/50">
                          <td className="py-2 pr-4 whitespace-nowrap text-muted-foreground">
                            {new Date(log.created_at).toLocaleString()}
                          </td>
                          <td className="py-2 pr-4">
                            <Badge variant="outline" className="text-xs">{log.service_slug}</Badge>
                          </td>
                          <td className="py-2 pr-4">
                            <Badge variant="secondary" className="text-xs">{log.method}</Badge>
                          </td>
                          <td className="py-2 pr-4 font-mono text-xs max-w-[200px] truncate">{log.path}</td>
                          <td className="py-2 pr-4">
                            <Badge variant={log.status_code < 400 ? 'success' : 'destructive'} className="text-xs">
                              {log.status_code}
                            </Badge>
                          </td>
                          <td className="py-2 pr-4 text-right whitespace-nowrap">{log.duration_ms} ms</td>
                        </tr>
                      ))}
                      {modalLogs.length === 0 && (
                        <tr>
                          <td colSpan={6} className="py-8 text-center text-muted-foreground">
                            No requests found
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
