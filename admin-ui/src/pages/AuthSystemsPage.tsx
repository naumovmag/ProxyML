import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchAuthSystems, createAuthSystem, deleteAuthSystem, AuthSystem } from '@/api/authSystems'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Plus, Trash2, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

export default function AuthSystemsPage() {
  const navigate = useNavigate()
  const [systems, setSystems] = useState<AuthSystem[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [confirmState, setConfirmState] = useState<{ open: boolean; onConfirm: () => void }>({ open: false, onConfirm: () => {} })

  const [formName, setFormName] = useState('')
  const [formSlug, setFormSlug] = useState('')

  const load = async () => {
    const { data } = await fetchAuthSystems()
    setSystems(data)
  }
  useEffect(() => { load() }, [])

  const openCreate = () => {
    setFormName('')
    setFormSlug('')
    setDialogOpen(true)
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const { data } = await createAuthSystem({ name: formName, slug: formSlug })
      toast.success('Auth system created')
      setDialogOpen(false)
      navigate(`/auth-systems/${data.id}`)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error')
    }
  }

  const handleDelete = (id: string) => {
    setConfirmState({
      open: true,
      onConfirm: async () => {
        await deleteAuthSystem(id)
        toast.success('Auth system deleted')
        load()
      },
    })
  }

  const slugFormatOk = !formSlug || /^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(formSlug)
  const slugDuplicate = formSlug && systems.some(s => s.slug === formSlug)
  const slugValid = slugFormatOk && !slugDuplicate

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Auth Systems</h2>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" />New Auth System
        </Button>
      </div>

      <Card className="mb-6">
        <CardContent className="py-4">
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck className="h-4 w-4" />
            <span className="font-medium">Security Technologies</span>
          </div>
          <div className="text-sm text-muted-foreground space-y-1">
            <div>Passwords are hashed with bcrypt.</div>
            <div>Access tokens are JWTs signed per system (HS256).</div>
            <div>Refresh tokens are random and stored as SHA-256 hashes with TTL.</div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {systems.map(sys => (
          <Card key={sys.id} className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => navigate(`/auth-systems/${sys.id}`)}>
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4" />
                    <span className="font-medium">{sys.name}</span>
                    <Badge variant={sys.is_active ? 'success' : 'secondary'}>
                      {sys.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                    <Badge variant="outline">{sys.registration_fields.length} fields</Badge>
                    <Badge variant="outline">Access: {sys.access_token_ttl_minutes}m</Badge>
                    <Badge variant="outline">Refresh: {sys.refresh_token_ttl_days}d</Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    <span className="font-mono">/auth/{sys.slug}/</span>
                    {' | '}Created: {new Date(sys.created_at).toLocaleDateString()}
                  </div>
                  {sys.registration_fields.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {sys.registration_fields.map(f => (
                        <Badge key={f.name} variant="secondary" className="text-xs">
                          {f.name}: {f.type}{f.required ? ' *' : ''}{f.unique ? ' !' : ''}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                <div className="ml-4" onClick={e => e.stopPropagation()}>
                  <Button variant="ghost" size="icon" onClick={() => handleDelete(sys.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        {systems.length === 0 && (
          <Card>
            <CardContent className="p-12 text-center text-muted-foreground">
              No auth systems yet. Click "New Auth System" to create one.
            </CardContent>
          </Card>
        )}
      </div>

      <ConfirmDialog
        open={confirmState.open}
        onOpenChange={open => setConfirmState(s => ({ ...s, open }))}
        title="Delete Auth System"
        description="This auth system may already have registered users. Deleting it will remove the system and all its users permanently."
        confirmLabel="Delete"
        variant="destructive"
        confirmText="delete"
        onConfirm={confirmState.onConfirm}
      />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Create Auth System</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={formName} onChange={e => setFormName(e.target.value)} required placeholder="My Auth" />
            </div>
            <div className="space-y-2">
              <Label>Slug</Label>
              <Input
                value={formSlug}
                onChange={e => setFormSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                required
                placeholder="my-auth"
                pattern="^[a-z0-9][a-z0-9-]*[a-z0-9]$"
              />
              {formSlug && !slugFormatOk && (
                <p className="text-xs text-destructive">Lowercase letters, digits and hyphens only</p>
              )}
              {slugDuplicate && (
                <p className="text-xs text-destructive">This slug is already taken</p>
              )}
            </div>
            <p className="text-xs text-muted-foreground">Fields, TTL and other settings can be configured after creation.</p>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={!slugValid}>Create</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
