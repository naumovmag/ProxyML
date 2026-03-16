import { useEffect, useState } from 'react'
import {
  fetchServices, createService, updateService, deleteService, checkServiceHealth,
  exportServices, importServices, fetchServiceGroups, createServiceGroup, updateServiceGroup, deleteServiceGroup,
  Service, ServiceCreate, ServiceGroup, ServiceGroupCreate, HealthCheckResult,
} from '@/api/services'
import { DndContext, DragEndEvent, DragOverlay, DragStartEvent, PointerSensor, useSensor, useSensors, useDroppable, closestCenter } from '@dnd-kit/core'
import { useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Plus, Trash2, Edit, Wifi, Loader2, CheckCircle, XCircle, Download, Upload, Copy, FolderPlus, ChevronDown, ChevronRight, GripVertical, Terminal, Check } from 'lucide-react'
import { toast } from 'sonner'

function DroppableZone({ id, children, isOver }: { id: string; children: React.ReactNode; isOver?: boolean }) {
  const { setNodeRef, isOver: over } = useDroppable({ id })
  const active = isOver !== undefined ? isOver : over
  return (
    <div ref={setNodeRef} className={`transition-colors rounded-lg ${active ? 'bg-accent/50 ring-2 ring-accent' : ''}`}>
      {children}
    </div>
  )
}

function DraggableServiceCard({ service, children }: { service: Service; children: React.ReactNode }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: service.id })
  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.3 : 1,
  }
  return (
    <div ref={setNodeRef} style={style} className="relative">
      <div
        {...listeners}
        {...attributes}
        className="absolute left-0 top-0 bottom-0 w-8 flex items-center justify-center cursor-grab active:cursor-grabbing z-10 hover:bg-accent/50 rounded-l-lg transition-colors"
      >
        <GripVertical className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="pl-8">{children}</div>
    </div>
  )
}

const SERVICE_TYPES = ['llm_chat', 'embedding', 'stt', 'tts', 'custom']
const AUTH_TYPES = ['none', 'bearer', 'header', 'query_param']

const emptyForm: ServiceCreate = {
  name: '', slug: '', service_type: 'custom', base_url: '', auth_type: 'none',
  auth_token: null, auth_header_name: 'Authorization', default_model: null,
  timeout_seconds: 120, supports_streaming: false, extra_headers: null,
  health_check_path: null, health_check_method: 'GET', description: null,
  tags: [], request_schema_hint: null, cache_enabled: false,
  cache_ttl_seconds: 86400, fallback_service_id: null,
  fallback_on_statuses: [502, 503, 504], is_active: true, group_id: null,
}

export default function ServicesPage() {
  const [services, setServices] = useState<Service[]>([])
  const [groups, setGroups] = useState<ServiceGroup[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState<ServiceCreate>(emptyForm)
  const [healthResults, setHealthResults] = useState<Record<string, { loading: boolean; result?: HealthCheckResult }>>({})
  const [modalHealth, setModalHealth] = useState<{ loading: boolean; result?: HealthCheckResult } | null>(null)
  const [tagsInput, setTagsInput] = useState('')
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({})
  const [curlDialog, setCurlDialog] = useState<{ open: boolean; curl: string }>({ open: false, curl: '' })
  const [curlCopied, setCurlCopied] = useState(false)

  const [confirmState, setConfirmState] = useState<{ open: boolean; title: string; description: string; onConfirm: () => void }>({ open: false, title: '', description: '', onConfirm: () => {} })

  const [draggingId, setDraggingId] = useState<string | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }))

  const handleDragStart = (event: DragStartEvent) => {
    setDraggingId(String(event.active.id))
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    setDraggingId(null)
    const { active, over } = event
    if (!over) return

    const serviceId = String(active.id)
    const targetGroupId = String(over.id)

    const service = services.find((s) => s.id === serviceId)
    if (!service) return

    const newGroupId = targetGroupId === '_ungrouped' ? null : targetGroupId
    if (service.group_id === newGroupId) return

    // Optimistic update
    setServices((prev) => prev.map((s) => s.id === serviceId ? { ...s, group_id: newGroupId } : s))

    try {
      await updateService(serviceId, { group_id: newGroupId })
    } catch {
      toast.error('Failed to move service')
      load()
    }
  }

  // Group dialog
  const [groupDialogOpen, setGroupDialogOpen] = useState(false)
  const [editGroupId, setEditGroupId] = useState<string | null>(null)
  const [groupForm, setGroupForm] = useState<ServiceGroupCreate>({ name: '', description: null, sort_order: 0 })

  const load = () => {
    fetchServices().then((r) => setServices(r.data))
    fetchServiceGroups().then((r) => setGroups(r.data))
  }
  useEffect(() => { load() }, [])

  const toggleGroup = (id: string) => setCollapsedGroups((prev) => ({ ...prev, [id]: !prev[id] }))

  // --- Service CRUD ---
  const openCreate = (groupId?: string) => {
    setEditId(null)
    setForm({ ...emptyForm, group_id: groupId || null })
    setTagsInput('')
    setModalHealth(null)
    setDialogOpen(true)
  }

  const openClone = (s: Service) => {
    setEditId(null)
    setModalHealth(null)
    setForm({
      name: `${s.name} (copy)`, slug: `${s.slug}-copy`, service_type: s.service_type, base_url: s.base_url,
      auth_type: s.auth_type, auth_token: s.auth_token, auth_header_name: s.auth_header_name,
      default_model: s.default_model, timeout_seconds: s.timeout_seconds,
      supports_streaming: s.supports_streaming, extra_headers: s.extra_headers,
      health_check_path: s.health_check_path, health_check_method: s.health_check_method,
      description: s.description, tags: s.tags, request_schema_hint: s.request_schema_hint,
      cache_enabled: s.cache_enabled, cache_ttl_seconds: s.cache_ttl_seconds,
      fallback_service_id: null, fallback_on_statuses: [502, 503, 504],
      is_active: s.is_active, group_id: s.group_id,
    })
    setTagsInput(s.tags.join(', '))
    setDialogOpen(true)
  }

  const openEdit = (s: Service) => {
    setEditId(s.id)
    setModalHealth(null)
    setForm({
      name: s.name, slug: s.slug, service_type: s.service_type, base_url: s.base_url,
      auth_type: s.auth_type, auth_token: s.auth_token, auth_header_name: s.auth_header_name,
      default_model: s.default_model, timeout_seconds: s.timeout_seconds,
      supports_streaming: s.supports_streaming, extra_headers: s.extra_headers,
      health_check_path: s.health_check_path, health_check_method: s.health_check_method,
      description: s.description, tags: s.tags, request_schema_hint: s.request_schema_hint,
      cache_enabled: s.cache_enabled, cache_ttl_seconds: s.cache_ttl_seconds,
      fallback_service_id: s.fallback_service_id, fallback_on_statuses: s.fallback_on_statuses || [502, 503, 504],
      is_active: s.is_active, group_id: s.group_id,
    })
    setTagsInput(s.tags.join(', '))
    setDialogOpen(true)
  }

  const handleSubmit = async (e: React.FormEvent, andCheck = false) => {
    e.preventDefault()
    const data = { ...form, tags: tagsInput.split(',').map((t) => t.trim()).filter(Boolean) }
    try {
      if (editId) {
        await updateService(editId, data)
        toast.success('Service updated')
        if (andCheck) {
          setModalHealth({ loading: true })
          try {
            const { data: health } = await checkServiceHealth(editId)
            setModalHealth({ loading: false, result: health })
          } catch {
            setModalHealth({ loading: false, result: { service_id: editId, service_name: '', status: 'error', detail: 'Request failed', response_time_ms: null } })
          }
          load()
          return
        }
      } else {
        const { data: created } = await createService(data)
        toast.success('Service created')
        if (andCheck) {
          setEditId(created.id)
          setModalHealth({ loading: true })
          try {
            const { data: health } = await checkServiceHealth(created.id)
            setModalHealth({ loading: false, result: health })
          } catch {
            setModalHealth({ loading: false, result: { service_id: created.id, service_name: '', status: 'error', detail: 'Request failed', response_time_ms: null } })
          }
          load()
          return
        }
      }
      setDialogOpen(false)
      load()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error saving service')
    }
  }

  const handleDelete = (id: string) => {
    setConfirmState({
      open: true,
      title: 'Delete service',
      description: 'Are you sure you want to delete this service? This action cannot be undone.',
      onConfirm: async () => {
        await deleteService(id)
        toast.success('Service deleted')
        load()
      },
    })
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

  const handleExport = async () => {
    try {
      const { data } = await exportServices()
      const blob = new Blob([data], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `proxyml-services-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Services exported')
    } catch {
      toast.error('Export failed')
    }
  }

  const handleImport = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return
      try {
        const { data } = await importServices(file)
        const parts = [`Services: ${data.created} created, ${data.updated} updated`]
        if (data.groups_created || data.groups_updated) parts.push(`Groups: ${data.groups_created} created, ${data.groups_updated} updated`)
        toast.success(parts.join('. '))
        if (data.errors.length > 0) {
          toast.warning(`${data.errors.length} errors during import`)
        }
        load()
      } catch (err: any) {
        toast.error(err.response?.data?.detail || 'Import failed')
      }
    }
    input.click()
  }

  // --- Group CRUD ---
  const openCreateGroup = () => {
    setEditGroupId(null)
    setGroupForm({ name: '', description: null, sort_order: 0 })
    setGroupDialogOpen(true)
  }

  const openEditGroup = (g: ServiceGroup) => {
    setEditGroupId(g.id)
    setGroupForm({ name: g.name, description: g.description, sort_order: g.sort_order })
    setGroupDialogOpen(true)
  }

  const handleGroupSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editGroupId) {
        await updateServiceGroup(editGroupId, groupForm)
        toast.success('Group updated')
      } else {
        await createServiceGroup(groupForm)
        toast.success('Group created')
      }
      setGroupDialogOpen(false)
      load()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error saving group')
    }
  }

  const handleDeleteGroup = (id: string) => {
    setConfirmState({
      open: true,
      title: 'Delete group',
      description: 'Delete this group? Services in it will become ungrouped.',
      onConfirm: async () => {
        await deleteServiceGroup(id)
        toast.success('Group deleted')
        load()
      },
    })
  }

  const generateCurl = (s: Service) => {
    const origin = window.location.origin
    const baseProxy = `${origin}/proxy/${s.slug}`

    const lines: string[] = []

    if (s.service_type === 'llm_chat') {
      const model = s.default_model || 'your-model'
      lines.push(`curl -X POST '${baseProxy}/v1/chat/completions' \\`)
      lines.push(`  -H 'Content-Type: application/json' \\`)
      lines.push(`  -H 'X-Api-Key: YOUR_API_KEY' \\`)
      lines.push(`  -d '{`)
      lines.push(`  "model": "${model}",`)
      lines.push(`  "messages": [{"role": "user", "content": "Hello"}],`)
      lines.push(`  "max_tokens": 100`)
      lines.push(`}'`)
    } else if (s.service_type === 'embedding') {
      const model = s.default_model || 'your-model'
      lines.push(`curl -X POST '${baseProxy}/v1/embeddings' \\`)
      lines.push(`  -H 'Content-Type: application/json' \\`)
      lines.push(`  -H 'X-Api-Key: YOUR_API_KEY' \\`)
      lines.push(`  -d '{`)
      lines.push(`  "model": "${model}",`)
      lines.push(`  "input": "Hello world"`)
      lines.push(`}'`)
    } else if (s.service_type === 'stt') {
      lines.push(`curl -X POST '${baseProxy}/v1/audio/transcriptions' \\`)
      lines.push(`  -H 'X-Api-Key: YOUR_API_KEY' \\`)
      lines.push(`  -F 'file=@audio.wav' \\`)
      lines.push(`  -F 'model=${s.default_model || 'whisper-1'}'`)
    } else if (s.service_type === 'tts') {
      lines.push(`curl -X POST '${baseProxy}/v1/audio/speech' \\`)
      lines.push(`  -H 'Content-Type: application/json' \\`)
      lines.push(`  -H 'X-Api-Key: YOUR_API_KEY' \\`)
      lines.push(`  -d '{`)
      lines.push(`  "model": "${s.default_model || 'tts-1'}",`)
      lines.push(`  "input": "Hello world",`)
      lines.push(`  "voice": "alloy"`)
      lines.push(`}' \\`)
      lines.push(`  --output speech.mp3`)
    } else {
      lines.push(`curl -X POST '${baseProxy}/your-path' \\`)
      lines.push(`  -H 'Content-Type: application/json' \\`)
      lines.push(`  -H 'X-Api-Key: YOUR_API_KEY' \\`)
      lines.push(`  -d '{"key": "value"}'`)
    }

    return lines.join('\n')
  }

  const openCurl = (s: Service) => {
    setCurlDialog({ open: true, curl: generateCurl(s) })
    setCurlCopied(false)
  }

  const copyCurl = () => {
    navigator.clipboard.writeText(curlDialog.curl)
    setCurlCopied(true)
    setTimeout(() => setCurlCopied(false), 2000)
  }

  const setField = (key: string, value: any) => setForm((prev) => ({ ...prev, [key]: value }))

  // Group services
  const groupedServices = groups.map((g) => ({
    group: g,
    services: services.filter((s) => s.group_id === g.id),
  }))
  const ungroupedServices = services.filter((s) => !s.group_id)

  const renderServiceCard = (s: Service) => {
    const health = healthResults[s.id]
    return (
      <Card key={s.id}>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div className="flex items-center gap-3">
            <CardTitle className="text-lg">{s.name}</CardTitle>
            <Badge variant={s.is_active ? 'success' : 'secondary'}>{s.is_active ? 'Active' : 'Inactive'}</Badge>
            <Badge variant="outline">{s.service_type}</Badge>
            {s.supports_streaming && <Badge variant="warning">SSE</Badge>}
            {s.cache_enabled && <Badge variant="outline">Cache</Badge>}
            {s.fallback_service_id && <Badge variant="outline">Fallback</Badge>}
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
            <Button variant="ghost" size="icon" onClick={() => openCurl(s)} title="cURL"><Terminal className="h-4 w-4" /></Button>
            <Button variant="ghost" size="icon" onClick={() => openClone(s)} title="Clone"><Copy className="h-4 w-4" /></Button>
            <Button variant="ghost" size="icon" onClick={() => openEdit(s)} title="Edit"><Edit className="h-4 w-4" /></Button>
            <Button variant="ghost" size="icon" onClick={() => handleDelete(s.id)} title="Delete"><Trash2 className="h-4 w-4 text-destructive" /></Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground space-y-1">
            <div><span className="font-medium">URL:</span> {s.base_url}</div>
            <div><span className="font-medium">Slug:</span> /proxy/{s.slug}/</div>
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
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Services</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleExport}><Download className="h-4 w-4 mr-2" />Export</Button>
          <Button variant="outline" onClick={handleImport}><Upload className="h-4 w-4 mr-2" />Import</Button>
          <Button variant="outline" onClick={openCreateGroup}><FolderPlus className="h-4 w-4 mr-2" />Add Group</Button>
          <Button onClick={() => openCreate()}><Plus className="h-4 w-4 mr-2" />Add Service</Button>
        </div>
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div className="space-y-6">
          {/* Grouped services */}
          {groupedServices.map(({ group, services: groupSvcs }) => (
            <DroppableZone key={group.id} id={group.id}>
              <div className="space-y-3 p-2">
                <div className="flex items-center gap-3 group">
                  <button
                    className="flex items-center gap-2 text-lg font-semibold hover:text-foreground/80 transition-colors"
                    onClick={() => toggleGroup(group.id)}
                  >
                    {collapsedGroups[group.id]
                      ? <ChevronRight className="h-5 w-5" />
                      : <ChevronDown className="h-5 w-5" />
                    }
                    {group.name}
                  </button>
                  <Badge variant="outline" className="text-xs">{groupSvcs.length}</Badge>
                  {group.description && <span className="text-sm text-muted-foreground">{group.description}</span>}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openCreate(group.id)} title="Add service to group">
                      <Plus className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEditGroup(group)} title="Edit group">
                      <Edit className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleDeleteGroup(group.id)} title="Delete group">
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </div>
                </div>
                {!collapsedGroups[group.id] && (
                  <div className="grid gap-3 pl-4 border-l-2 border-border">
                    {groupSvcs.map((s) => (
                      <DraggableServiceCard key={s.id} service={s}>
                        {renderServiceCard(s)}
                      </DraggableServiceCard>
                    ))}
                    {groupSvcs.length === 0 && (
                      <div className="text-sm text-muted-foreground py-4 pl-2">
                        Empty group. Drag a service here or <button className="underline" onClick={() => openCreate(group.id)}>add one</button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </DroppableZone>
          ))}

          {/* Ungrouped services */}
          <DroppableZone id="_ungrouped">
            <div className="space-y-3 p-2">
              {groups.length > 0 && (
                <div className="text-lg font-semibold text-muted-foreground">Ungrouped</div>
              )}
              <div className="grid gap-3">
                {ungroupedServices.map((s) => (
                  <DraggableServiceCard key={s.id} service={s}>
                    {renderServiceCard(s)}
                  </DraggableServiceCard>
                ))}
              </div>
              {ungroupedServices.length === 0 && groups.length > 0 && (
                <div className="text-sm text-muted-foreground py-4">
                  Drag services here to ungroup them
                </div>
              )}
            </div>
          </DroppableZone>

          {services.length === 0 && (
            <Card>
              <CardContent className="p-12 text-center text-muted-foreground">
                No services yet. Click "Add Service" to create one.
              </CardContent>
            </Card>
          )}
        </div>

        <DragOverlay>
          {draggingId ? (
            <div className="opacity-80 rotate-2 shadow-xl">
              {renderServiceCard(services.find((s) => s.id === draggingId)!)}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Create/Edit Service Dialog */}
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
                <Label>Group</Label>
                <Select value={form.group_id || '_none'} onValueChange={(v) => setField('group_id', v === '_none' ? null : v)}>
                  <SelectTrigger><SelectValue placeholder="No group" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_none">No group</SelectItem>
                    {groups.map((g) => <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Type</Label>
                <Select value={form.service_type} onValueChange={(v) => {
                  setField('service_type', v)
                  // Reset fallback if it's incompatible with new type
                  if (form.fallback_service_id) {
                    const fb = services.find((s) => s.id === form.fallback_service_id)
                    if (fb && fb.service_type !== v) setField('fallback_service_id', null)
                  }
                }}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {SERVICE_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
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

            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <Switch checked={form.supports_streaming} onCheckedChange={(v) => setField('supports_streaming', v)} />
                <Label>Supports Streaming</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={form.cache_enabled} onCheckedChange={(v) => setField('cache_enabled', v)} />
                <Label>Cache</Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={form.is_active} onCheckedChange={(v) => setField('is_active', v)} />
                <Label>Active</Label>
              </div>
            </div>

            {form.cache_enabled && (
              <div className="space-y-2">
                <Label>Cache TTL (seconds)</Label>
                <div className="flex items-center gap-3">
                  <Input type="number" value={form.cache_ttl_seconds} onChange={(e) => setField('cache_ttl_seconds', parseInt(e.target.value) || 86400)} className="w-40" />
                  <span className="text-sm text-muted-foreground">
                    = {form.cache_ttl_seconds && form.cache_ttl_seconds >= 3600
                      ? `${Math.floor((form.cache_ttl_seconds || 0) / 3600)}h ${Math.floor(((form.cache_ttl_seconds || 0) % 3600) / 60)}m`
                      : `${Math.floor((form.cache_ttl_seconds || 0) / 60)}m`}
                  </span>
                </div>
              </div>
            )}

            {/* Fallback */}
            <div className="space-y-3 rounded-md border p-4">
              <Label className="text-sm font-medium">Fallback Service</Label>
              <Select
                value={form.fallback_service_id || '_none'}
                onValueChange={(v) => setField('fallback_service_id', v === '_none' ? null : v)}
              >
                <SelectTrigger><SelectValue placeholder="No fallback" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="_none">No fallback</SelectItem>
                  {services
                    .filter((s) => s.id !== editId && s.service_type === form.service_type)
                    .map((s) => (
                      <SelectItem key={s.id} value={s.id}>{s.name} ({s.slug})</SelectItem>
                    ))}
                </SelectContent>
              </Select>
              {form.fallback_service_id && (
                <div className="space-y-2">
                  <Label className="text-xs">Trigger on HTTP statuses (comma separated)</Label>
                  <Input
                    value={(form.fallback_on_statuses || []).join(', ')}
                    onChange={(e) => {
                      const statuses = e.target.value.split(',').map((s) => parseInt(s.trim())).filter((n) => !isNaN(n))
                      setField('fallback_on_statuses', statuses.length > 0 ? statuses : [502, 503, 504])
                    }}
                    placeholder="502, 503, 504"
                  />
                  <p className="text-xs text-muted-foreground">
                    Also triggers on connection errors and timeouts
                  </p>
                </div>
              )}
            </div>

            {/* Check Connection inside modal */}
            <div className="rounded-md border p-4 space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Connection Check</Label>
                {editId && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      setModalHealth({ loading: true })
                      try {
                        const { data } = await checkServiceHealth(editId)
                        setModalHealth({ loading: false, result: data })
                      } catch {
                        setModalHealth({ loading: false, result: { service_id: editId, service_name: '', status: 'error', detail: 'Request failed', response_time_ms: null } })
                      }
                    }}
                    disabled={modalHealth?.loading}
                  >
                    {modalHealth?.loading ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : modalHealth?.result?.status === 'ok' ? (
                      <CheckCircle className="h-4 w-4 text-green-500 mr-2" />
                    ) : modalHealth?.result?.status === 'error' ? (
                      <XCircle className="h-4 w-4 text-red-500 mr-2" />
                    ) : (
                      <Wifi className="h-4 w-4 mr-2" />
                    )}
                    Check Connection
                  </Button>
                )}
              </div>
              {modalHealth?.loading && (
                <div className="text-sm text-muted-foreground flex items-center gap-2">
                  <Loader2 className="h-3 w-3 animate-spin" /> Checking...
                </div>
              )}
              {modalHealth?.result && (
                <div className={`text-sm ${modalHealth.result.status === 'ok' ? 'text-green-500' : 'text-red-500'}`}>
                  {modalHealth.result.status === 'ok' ? 'Connected' : 'Failed'}: {modalHealth.result.detail}
                  {modalHealth.result.response_time_ms != null && ` (${modalHealth.result.response_time_ms}ms)`}
                </div>
              )}
              {!editId && !modalHealth && (
                <div className="text-sm text-muted-foreground">
                  Use "Create & Check" to save and verify connection
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-4">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button type="button" variant="secondary" onClick={(e) => handleSubmit(e as any, true)}>
                {editId ? 'Save & Check' : 'Create & Check'}
              </Button>
              <Button type="submit">{editId ? 'Update' : 'Create'}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmState.open}
        onOpenChange={(open) => setConfirmState((s) => ({ ...s, open }))}
        title={confirmState.title}
        description={confirmState.description}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={confirmState.onConfirm}
      />

      {/* Create/Edit Group Dialog */}
      <Dialog open={groupDialogOpen} onOpenChange={setGroupDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editGroupId ? 'Edit Group' : 'Add Group'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleGroupSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={groupForm.name} onChange={(e) => setGroupForm((f) => ({ ...f, name: e.target.value }))} required placeholder="LLM Services" />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input value={groupForm.description || ''} onChange={(e) => setGroupForm((f) => ({ ...f, description: e.target.value || null }))} placeholder="Optional description" />
            </div>
            <div className="space-y-2">
              <Label>Sort Order</Label>
              <Input type="number" value={groupForm.sort_order} onChange={(e) => setGroupForm((f) => ({ ...f, sort_order: parseInt(e.target.value) || 0 }))} className="w-24" />
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <Button type="button" variant="outline" onClick={() => setGroupDialogOpen(false)}>Cancel</Button>
              <Button type="submit">{editGroupId ? 'Update' : 'Create'}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* cURL Dialog */}
      <Dialog open={curlDialog.open} onOpenChange={(open) => setCurlDialog((s) => ({ ...s, open }))}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>cURL Command</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Replace <code className="font-mono bg-muted px-1 rounded">YOUR_API_KEY</code> with an actual API key.
            </p>
            <pre className="bg-muted p-4 rounded-md text-sm font-mono whitespace-pre-wrap break-all overflow-auto max-h-80">
              {curlDialog.curl}
            </pre>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={copyCurl}>
                {curlCopied ? <Check className="h-4 w-4 mr-2 text-green-500" /> : <Copy className="h-4 w-4 mr-2" />}
                {curlCopied ? 'Copied' : 'Copy'}
              </Button>
              <Button onClick={() => setCurlDialog({ open: false, curl: '' })}>Close</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
