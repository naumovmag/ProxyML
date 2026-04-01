import { useState, useEffect } from 'react'
import { Mail, Smartphone, Send, Loader2, ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  createChannel,
  type ChannelTypeSchema,
  type VerificationChannelCreate,
} from '@/api/verificationChannels'

const channelIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  email: Mail,
  sms: Smartphone,
  telegram: Send,
}

interface AddChannelDialogProps {
  open: boolean
  onClose: () => void
  systemId: string
  providers: Record<string, ChannelTypeSchema>
  existingTypes: string[]
  onCreated: () => void
}

export function AddChannelDialog({
  open,
  onClose,
  systemId,
  providers,
  existingTypes,
  onCreated,
}: AddChannelDialogProps) {
  const [step, setStep] = useState(1)
  const [selectedType, setSelectedType] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('')
  const [configValues, setConfigValues] = useState<Record<string, any>>({})
  const [isRequired, setIsRequired] = useState(false)
  const [codeTtl, setCodeTtl] = useState(10)
  const [creating, setCreating] = useState(false)

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setStep(1)
      setSelectedType('')
      setSelectedProvider('')
      setConfigValues({})
      setIsRequired(false)
      setCodeTtl(10)
    }
  }, [open])

  const selectedSchema = selectedType ? providers[selectedType] : null
  const providerEntries = selectedSchema
    ? Object.entries(selectedSchema.providers)
    : []
  const selectedProviderSchema =
    selectedType && selectedProvider
      ? providers[selectedType]?.providers?.[selectedProvider]
      : null
  const configFields = selectedProviderSchema?.config_schema || []

  const handleSelectType = (type: string) => {
    setSelectedType(type)
    setSelectedProvider('')
    setConfigValues({})
    // If only one provider, auto-select and skip to step 3
    const provEntries = Object.entries(providers[type]?.providers || {})
    if (provEntries.length === 1) {
      setSelectedProvider(provEntries[0][0])
      setStep(3)
    } else {
      setStep(2)
    }
  }

  const handleSelectProvider = (providerKey: string) => {
    setSelectedProvider(providerKey)
    setConfigValues({})
    setStep(3)
  }

  const handleBack = () => {
    if (step === 3) {
      const provEntries = Object.entries(providers[selectedType]?.providers || {})
      if (provEntries.length === 1) {
        // Only one provider, go back to type selection
        setSelectedType('')
        setSelectedProvider('')
        setStep(1)
      } else {
        setSelectedProvider('')
        setStep(2)
      }
    } else if (step === 2) {
      setSelectedType('')
      setStep(1)
    }
  }

  const handleCreate = async () => {
    try {
      setCreating(true)
      const payload: VerificationChannelCreate = {
        channel_type: selectedType,
        provider_type: selectedProvider,
        provider_config: configValues,
        is_required: isRequired,
        settings: { code_ttl_minutes: codeTtl },
      }
      await createChannel(systemId, payload)
      toast.success('Verification channel created')
      onCreated()
      onClose()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to create channel')
    } finally {
      setCreating(false)
    }
  }

  const canCreate = () => {
    // Check all required config fields are filled
    for (const field of configFields) {
      if (field.required && !configValues[field.name]?.toString().trim()) {
        return false
      }
    }
    return true
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Verification Channel</DialogTitle>
        </DialogHeader>

        {/* Step 1: Select channel type */}
        {step === 1 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Select a channel type:</p>
            <div className="grid grid-cols-3 gap-3">
              {Object.entries(providers).map(([type, schema]) => {
                const Icon = channelIcons[type] || Mail
                const disabled = existingTypes.includes(type)
                return (
                  <button
                    key={type}
                    disabled={disabled}
                    onClick={() => handleSelectType(type)}
                    className={cn(
                      'p-4 border rounded-lg text-left hover:border-primary transition-colors',
                      disabled && 'opacity-50 cursor-not-allowed hover:border-border',
                      selectedType === type && 'border-primary'
                    )}
                  >
                    <Icon className="w-6 h-6 mb-2" />
                    <div className="font-medium text-sm">{schema.label}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {schema.description}
                    </div>
                    {disabled && (
                      <div className="text-xs text-muted-foreground mt-1 italic">
                        Already added
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Step 2: Select provider */}
        {step === 2 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Select a provider for {selectedSchema?.label}:
            </p>
            <div className="space-y-2">
              {providerEntries.map(([key, schema]) => (
                <button
                  key={key}
                  onClick={() => handleSelectProvider(key)}
                  className={cn(
                    'w-full p-3 border rounded-lg text-left hover:border-primary transition-colors',
                    selectedProvider === key && 'border-primary'
                  )}
                >
                  <div className="font-medium text-sm">{schema.label}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 3: Configure */}
        {step === 3 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Configure {selectedProviderSchema?.label} for {selectedSchema?.label}:
            </p>

            {/* Dynamic config fields */}
            {configFields.length > 0 && (
              <div className="space-y-3">
                {configFields.map((field) => (
                  <div key={field.name} className="space-y-1.5">
                    <Label className="text-sm">
                      {field.label}
                      {field.required && <span className="text-destructive ml-0.5">*</span>}
                    </Label>
                    <Input
                      type={field.secret ? 'password' : 'text'}
                      placeholder={field.placeholder}
                      value={configValues[field.name] || ''}
                      onChange={(e) =>
                        setConfigValues((prev) => ({
                          ...prev,
                          [field.name]: e.target.value,
                        }))
                      }
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Basic settings */}
            <div className="space-y-3 pt-2 border-t">
              <div className="space-y-1.5">
                <Label className="text-sm">Code TTL (minutes)</Label>
                <Input
                  type="number"
                  value={codeTtl}
                  onChange={(e) => setCodeTtl(Number(e.target.value))}
                  min={1}
                  max={60}
                />
              </div>
              <div className="flex items-center gap-3">
                <Switch checked={isRequired} onCheckedChange={setIsRequired} />
                <Label className="text-sm">Required for registration</Label>
              </div>
            </div>
          </div>
        )}

        {/* Footer with navigation */}
        <div className="flex justify-between pt-2">
          <div>
            {step > 1 && (
              <Button variant="ghost" onClick={handleBack} size="sm">
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose} size="sm">
              Cancel
            </Button>
            {step === 3 && (
              <Button
                onClick={handleCreate}
                disabled={creating || !canCreate()}
                size="sm"
              >
                {creating && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
                Create
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
