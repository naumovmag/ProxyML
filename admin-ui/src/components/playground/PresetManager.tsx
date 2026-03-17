import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Save, Trash2, FolderOpen } from 'lucide-react'
import { toast } from 'sonner'
import { Preset, fetchPresets, createPreset, updatePreset, deletePreset } from '@/api/playground'

interface Props {
  serviceType: string
  getParams: () => Record<string, unknown>
  onLoad: (params: Record<string, unknown>) => void
}

export default function PresetManager({ serviceType, getParams, onLoad }: Props) {
  const [presets, setPresets] = useState<Preset[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [newName, setNewName] = useState('')

  const load = () => {
    fetchPresets(serviceType).then(({ data }) => setPresets(data)).catch(() => {})
  }

  useEffect(() => { load() }, [serviceType])

  const handleLoad = (presetId: string) => {
    const preset = presets.find((p) => p.id === presetId)
    if (preset) {
      onLoad(preset.params)
      setSelectedId(presetId)
      toast.success(`Loaded: ${preset.name}`)
    }
  }

  const handleSave = async () => {
    if (!newName.trim()) {
      toast.error('Enter a preset name')
      return
    }
    try {
      await createPreset({ service_type: serviceType, name: newName.trim(), params: getParams() })
      setNewName('')
      setSaving(false)
      load()
      toast.success('Preset saved')
    } catch {
      toast.error('Failed to save preset')
    }
  }

  const handleUpdate = async () => {
    if (!selectedId) return
    try {
      await updatePreset(selectedId, { params: getParams() })
      load()
      toast.success('Preset updated')
    } catch {
      toast.error('Failed to update preset')
    }
  }

  const handleDelete = async () => {
    if (!selectedId) return
    try {
      await deletePreset(selectedId)
      setSelectedId('')
      load()
      toast.success('Preset deleted')
    } catch {
      toast.error('Failed to delete preset')
    }
  }

  return (
    <div className="flex items-center gap-1.5">
      {presets.length > 0 && (
        <Select value={selectedId} onValueChange={handleLoad}>
          <SelectTrigger className="w-44 h-8 text-xs">
            <FolderOpen className="h-3 w-3 mr-1 shrink-0" />
            <SelectValue placeholder="Load preset" />
          </SelectTrigger>
          <SelectContent>
            {presets.map((p) => (
              <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {selectedId && (
        <>
          <Button variant="ghost" size="sm" onClick={handleUpdate} title="Update preset with current params" className="h-8 px-2">
            <Save className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" onClick={handleDelete} title="Delete preset" className="h-8 px-2 text-destructive">
            <Trash2 className="h-3 w-3" />
          </Button>
        </>
      )}

      {saving ? (
        <div className="flex items-center gap-1">
          <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Preset name" className="h-8 w-36 text-xs"
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setSaving(false) }}
            autoFocus
          />
          <Button size="sm" onClick={handleSave} className="h-8 px-2 text-xs">Save</Button>
          <Button variant="ghost" size="sm" onClick={() => setSaving(false)} className="h-8 px-2 text-xs">Cancel</Button>
        </div>
      ) : (
        <Button variant="ghost" size="sm" onClick={() => setSaving(true)} className="h-8 px-2 text-xs text-muted-foreground">
          <Save className="h-3 w-3 mr-1" />Save preset
        </Button>
      )}
    </div>
  )
}
