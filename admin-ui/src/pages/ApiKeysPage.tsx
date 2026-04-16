import { useEffect, useState, useMemo } from 'react'
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
import {
  Plus, Trash2, Copy, Check, Pencil, Shield, ShieldCheck,
  BarChart3, Loader2, Power, PowerOff, ChevronLeft, ChevronRight, Search,
} from 'lucide-react'
import { toast } from 'sonner'

const PAGE_SIZE = 25

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 30) return `${d}d ago`
  return new Date(iso).toLocaleDateString()
}

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

  // Search + pagination
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)

  // Form state
  const [formName, setFormName] = useState('')
  const [formAllAccess, setFormAllAccess] = useState(true)
  const [formSelectedServices, setFormSelectedServices] = useState<string[]>([])
  const [formRateLimit, setFormRateLimit] = useState('')
  const [formExpires, setFormExpires] = useState('')

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
    setFormExpires('')
    setEditingKey(null)
    setNewKey(null)
    setCopied(false)
  }

  const openCreate = () => { resetForm(); setDialogOpen(true) }

  const openEdit = (key: ApiKey) => {
    setEditingKey(key)
    setFormName(key.name)
    setFormAllAccess(key.allowed_services === null)
    setFormSelectedServices(key.allowed_services || [])
    setFormRateLimit(key.rate_limit_rpm?.toString() || '')
    setFormExpires(key.expires_at ? key.expires_at.slice(0, 10) : '')
    setNewKey(null)
    setCopied(false)
    setDialogOpen(true)
  }

  const toggleService = (slug: string) =>
    setFormSelectedServices((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    )

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const payload: ApiKeyCreate = {
        name: formName,
        allowed_services: formAllAccess ? null : formSelectedServices,
        rate_limit_rpm: formRateLimit ? parseInt(formRateLimit) : null,
        expires_at: formExpires ? new Date(formExpires).toISOString() : null,
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
        expires_at: formExpires ? new Date(formExpires).toISOString() : null,
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

  // Client-side filter
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return keys
    return keys.filter(
      (k) => k.name.toLowerCase().includes(q) || k.key_prefix.toLowerCase().includes(q)
    )
  }, [keys, search])

  // Reset page when search changes
  useEffect(() => { setPage(0) }, [search])

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const pageKeys = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">API Keys</h2>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-4 w-4 mr-1.5" />New API Key
        </Button>
      </div>

      {/* Search bar */}
      <div className="mb-3 flex items-center gap-2">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or prefix…"
            className="pl-8 h-8 text-sm"
          />
        </div>
        <span className="text-xs text-muted-foreground tabular-nums">
          {filtered.length} {filtered.length === 1 ? 'key' : 'keys'}
        </span>
      </div>

      {/* Table */}
      <div className="rounded-md border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40 text-left">
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide w-6"></th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">Name</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">Prefix</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">Services</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide text-right">RPM</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide text-right">Requests</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">Created</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">Last used</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {pageKeys.map((k) => {
                const stats = keyStatsMap[k.id]
                return (
                  <tr
                    key={k.id}
                    className="border-b border-border/50 hover:bg-muted/30 transition-colors"
                  >
                    {/* Status dot */}
                    <td className="px-3 py-2.5">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${k.is_active ? 'bg-green-500' : 'bg-muted-foreground/40'}`}
                        title={k.is_active ? 'Active' : 'Inactive'}
                      />
                    </td>

                    {/* Name */}
                    <td className="px-3 py-2.5 max-w-[180px]">
                      <span className="font-medium truncate block">{k.name}</span>
                      {k.expires_at && (
                        <span className="text-[10px] text-muted-foreground">
                          exp {new Date(k.expires_at).toLocaleDateString()}
                        </span>
                      )}
                    </td>

                    {/* Prefix */}
                    <td className="px-3 py-2.5">
                      <span className="font-mono text-xs text-muted-foreground">{k.key_prefix}…</span>
                    </td>

                    {/* Services */}
                    <td className="px-3 py-2.5">
                      {k.allowed_services === null ? (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground">
                          <ShieldCheck className="h-3 w-3 shrink-0" />all
                        </span>
                      ) : k.allowed_services.length === 0 ? (
                        <span className="text-xs text-muted-foreground/50">none</span>
                      ) : (
                        <span
                          className="flex items-center gap-1 text-xs text-muted-foreground cursor-default"
                          title={k.allowed_services.map(getServiceName).join(', ')}
                        >
                          <Shield className="h-3 w-3 shrink-0" />
                          {k.allowed_services.length}
                        </span>
                      )}
                    </td>

                    {/* Rate limit */}
                    <td className="px-3 py-2.5 text-right">
                      {k.rate_limit_rpm ? (
                        <span className="text-xs tabular-nums text-muted-foreground">{k.rate_limit_rpm}</span>
                      ) : (
                        <span className="text-xs text-muted-foreground/30">—</span>
                      )}
                    </td>

                    {/* Requests (clickable → stats modal) */}
                    <td className="px-3 py-2.5 text-right">
                      <button
                        className="flex items-center gap-1 text-xs tabular-nums text-muted-foreground hover:text-foreground transition-colors ml-auto"
                        onClick={() => openStatsModal(k)}
                        title="View usage logs"
                      >
                        <BarChart3 className="h-3 w-3 shrink-0" />
                        {(stats?.request_count ?? 0).toLocaleString()}
                      </button>
                    </td>

                    {/* Created */}
                    <td className="px-3 py-2.5">
                      <span className="text-xs text-muted-foreground whitespace-nowrap" title={new Date(k.created_at).toLocaleString()}>
                        {relativeTime(k.created_at)}
                      </span>
                    </td>

                    {/* Last used */}
                    <td className="px-3 py-2.5">
                      {k.last_used_at ? (
                        <span className="text-xs text-muted-foreground whitespace-nowrap" title={new Date(k.last_used_at).toLocaleString()}>
                          {relativeTime(k.last_used_at)}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground/30">never</span>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="px-3 py-2.5">
                      <div className="flex items-center justify-end gap-0.5">
                        <Button
                          variant="ghost" size="icon" className="h-7 w-7"
                          onClick={() => openEdit(k)}
                          title="Edit"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost" size="icon" className="h-7 w-7"
                          onClick={() => handleToggle(k.id)}
                          title={k.is_active ? 'Disable' : 'Enable'}
                        >
                          {k.is_active
                            ? <PowerOff className="h-3.5 w-3.5 text-muted-foreground" />
                            : <Power className="h-3.5 w-3.5 text-green-500" />
                          }
                        </Button>
                        <Button
                          variant="ghost" size="icon" className="h-7 w-7 hover:text-destructive"
                          onClick={() => handleDelete(k.id)}
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}

              {pageKeys.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-3 py-12 text-center text-sm text-muted-foreground">
                    {search ? 'No keys match your search.' : 'No API keys yet. Click "New API Key" to create one.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <span>{page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}</span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost" size="icon" className="h-7 w-7"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="tabular-nums px-1">{page + 1} / {totalPages}</span>
            <Button
              variant="ghost" size="icon" className="h-7 w-7"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Confirm delete dialog */}
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
            /* ── Single-time secret reveal ── */
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Copy this key now — you won't be able to see it again.
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

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>Rate Limit (req/min)</Label>
                  <Input
                    type="number"
                    value={formRateLimit}
                    onChange={(e) => setFormRateLimit(e.target.value)}
                    placeholder="No limit"
                    min={1}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Expires</Label>
                  <Input
                    type="date"
                    value={formExpires}
                    onChange={(e) => setFormExpires(e.target.value)}
                    min={new Date().toISOString().slice(0, 10)}
                  />
                </div>
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
                  <div className="border rounded-md p-3 space-y-2 max-h-52 overflow-y-auto">
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

              <div className="flex justify-end gap-2 pt-2">
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

      {/* Stats / Logs Modal */}
      <Dialog open={!!statsModalKey} onOpenChange={(open) => { if (!open) setStatsModalKey(null) }}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Usage: {statsModalKey?.name}</DialogTitle>
          </DialogHeader>
          {statsModalKey && (
            <div className="space-y-4">
              {/* Summary stats */}
              <div className="flex gap-6 text-sm border-b pb-3">
                <div>
                  <span className="text-muted-foreground">Requests </span>
                  <span className="font-medium tabular-nums">
                    {(keyStatsMap[statsModalKey.id]?.request_count ?? 0).toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">Errors </span>
                  <span className="font-medium tabular-nums text-destructive">
                    {keyStatsMap[statsModalKey.id]?.error_count ?? 0}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">Avg latency </span>
                  <span className="font-medium tabular-nums">
                    {keyStatsMap[statsModalKey.id]?.avg_duration_ms ?? 0} ms
                  </span>
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
                        <th className="pb-2 pr-4 font-medium text-xs uppercase tracking-wide">Time</th>
                        <th className="pb-2 pr-4 font-medium text-xs uppercase tracking-wide">Service</th>
                        <th className="pb-2 pr-4 font-medium text-xs uppercase tracking-wide">Method</th>
                        <th className="pb-2 pr-4 font-medium text-xs uppercase tracking-wide">Path</th>
                        <th className="pb-2 pr-4 font-medium text-xs uppercase tracking-wide">Status</th>
                        <th className="pb-2 pr-4 font-medium text-xs uppercase tracking-wide text-right">Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {modalLogs.map((log) => (
                        <tr key={log.id} className="border-b border-border/50 hover:bg-muted/30">
                          <td className="py-2 pr-4 whitespace-nowrap text-muted-foreground text-xs">
                            {new Date(log.created_at).toLocaleString()}
                          </td>
                          <td className="py-2 pr-4">
                            <Badge variant="outline" className="text-xs">{log.service_slug}</Badge>
                          </td>
                          <td className="py-2 pr-4">
                            <Badge variant="secondary" className="text-xs">{log.method}</Badge>
                          </td>
                          <td className="py-2 pr-4 font-mono text-xs max-w-[200px] truncate text-muted-foreground">
                            {log.path}
                          </td>
                          <td className="py-2 pr-4">
                            <Badge variant={log.status_code < 400 ? 'success' : 'destructive'} className="text-xs">
                              {log.status_code}
                            </Badge>
                          </td>
                          <td className="py-2 pr-4 text-right whitespace-nowrap tabular-nums text-xs">
                            {log.duration_ms} ms
                          </td>
                        </tr>
                      ))}
                      {modalLogs.length === 0 && (
                        <tr>
                          <td colSpan={6} className="py-8 text-center text-muted-foreground text-sm">
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
