import { useEffect, useState } from 'react'
import { fetchApiKeys, createApiKey, deleteApiKey, toggleApiKey, ApiKey, ApiKeyCreated } from '@/api/apiKeys'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Plus, Trash2, Copy, Check } from 'lucide-react'
import { toast } from 'sonner'

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [name, setName] = useState('')
  const [newKey, setNewKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const load = () => fetchApiKeys().then((r) => setKeys(r.data))
  useEffect(() => { load() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const { data } = await createApiKey({ name })
      setNewKey(data.raw_key)
      setName('')
      load()
      toast.success('API key created')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error creating key')
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

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this API key?')) return
    await deleteApiKey(id)
    toast.success('API key deleted')
    load()
  }

  const handleToggle = async (id: string) => {
    await toggleApiKey(id)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">API Keys</h2>
        <Button onClick={() => { setNewKey(null); setCopied(false); setDialogOpen(true) }}>
          <Plus className="h-4 w-4 mr-2" />New API Key
        </Button>
      </div>

      <div className="space-y-3">
        {keys.map((k) => (
          <Card key={k.id}>
            <CardContent className="flex items-center justify-between py-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{k.name}</span>
                  <Badge variant={k.is_active ? 'success' : 'secondary'}>{k.is_active ? 'Active' : 'Inactive'}</Badge>
                </div>
                <div className="text-sm text-muted-foreground">
                  <span className="font-mono">{k.key_prefix}...</span>
                  {' | '}Created: {new Date(k.created_at).toLocaleDateString()}
                  {k.last_used_at && <>{' | '}Last used: {new Date(k.last_used_at).toLocaleDateString()}</>}
                  {k.expires_at && <>{' | '}Expires: {new Date(k.expires_at).toLocaleDateString()}</>}
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => handleToggle(k.id)}>
                  {k.is_active ? 'Disable' : 'Enable'}
                </Button>
                <Button variant="ghost" size="icon" onClick={() => handleDelete(k.id)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
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

      {/* Create Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{newKey ? 'API Key Created' : 'Create API Key'}</DialogTitle>
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
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-2">
                <Label>Key Name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="My API Key" />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                <Button type="submit">Create</Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
