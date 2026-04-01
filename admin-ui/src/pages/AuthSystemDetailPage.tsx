import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getAuthSystem, updateAuthSystem, fetchAuthSystemUsers, toggleAuthUser, updateAuthUser, resetAuthUserPassword, fetchAuthSystemStats,
  fetchEmailProviders, sendTestEmail,
  AuthSystem, AuthSystemUpdate, RegistrationField, AuthSystemUser, AuthSystemStatsResponse, ProviderField,
} from '@/api/authSystems'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Switch } from '@/components/ui/switch'
import { ArrowLeft, Plus, Trash2, Save, Copy, Check, Users, Settings, Code, Layers, BarChart3, FlaskConical, Loader2, Send, Pencil, KeyRound, Mail, CheckCircle, XCircle, Sparkles, ShieldCheck } from 'lucide-react'
import { ChannelList } from '@/components/verification/ChannelList'
import { toast } from 'sonner'
import { RegistrationsChart } from '@/components/charts'
import { fetchSettings, SystemSettings } from '@/api/settings'
import { aiGenerateEmailTemplate } from '@/api/ai'
import axios from 'axios'

const FIELD_TYPES = ['string', 'number', 'boolean', 'email', 'phone'] as const

type Tab = 'settings' | 'verification' | 'fields' | 'users' | 'stats' | 'playground' | 'api'

export default function AuthSystemDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [system, setSystem] = useState<AuthSystem | null>(null)
  const [tab, setTab] = useState<Tab>('settings')
  const [saving, setSaving] = useState(false)

  // Settings form
  const [formName, setFormName] = useState('')
  const [formSlug, setFormSlug] = useState('')
  const [formAccessTTL, setFormAccessTTL] = useState(60)
  const [formRefreshTTL, setFormRefreshTTL] = useState(30)
  const [formActive, setFormActive] = useState(true)
  const [formUsersActiveByDefault, setFormUsersActiveByDefault] = useState(true)

  // Fields
  const [formFields, setFormFields] = useState<RegistrationField[]>([])

  // Users
  const [users, setUsers] = useState<AuthSystemUser[]>([])
  const [usersLoaded, setUsersLoaded] = useState(false)

  // AI
  const [aiSettings, setAiSettings] = useState<SystemSettings | null>(null)
  const [aiGenerating, setAiGenerating] = useState(false)

  // Email tab
  const [emailPreview, setEmailPreview] = useState(false)
  const [emailProviders, setEmailProviders] = useState<Record<string, ProviderField[]>>({})
  const [emailSaving, setEmailSaving] = useState(false)
  const [testEmailTo, setTestEmailTo] = useState('')
  const [testEmailSending, setTestEmailSending] = useState(false)
  const [formEmailEnabled, setFormEmailEnabled] = useState(false)
  const [formRequireVerification, setFormRequireVerification] = useState(false)
  const [formProviderType, setFormProviderType] = useState<string>('')
  const [formProviderConfig, setFormProviderConfig] = useState<Record<string, any>>({})
  const [formFromAddress, setFormFromAddress] = useState('')
  const [formFromName, setFormFromName] = useState('')
  const [formTokenTTL, setFormTokenTTL] = useState(1440)
  const [formRedirectUrl, setFormRedirectUrl] = useState('')
  const [formTemplateSubject, setFormTemplateSubject] = useState('')
  const [formTemplateBody, setFormTemplateBody] = useState('')

  // Edit user modal
  const [editUser, setEditUser] = useState<AuthSystemUser | null>(null)
  const [editEmail, setEditEmail] = useState('')
  const [editFields, setEditFields] = useState<Record<string, any>>({})

  // Reset password modal
  const [resetPwUser, setResetPwUser] = useState<AuthSystemUser | null>(null)
  const [resetPwValue, setResetPwValue] = useState('')

  // Stats
  const [stats, setStats] = useState<AuthSystemStatsResponse | null>(null)
  const [statsHours, setStatsHours] = useState(720)

  // Playground
  const [pgAction, setPgAction] = useState<'register' | 'login' | 'me' | 'update-profile' | 'change-password' | 'refresh' | 'logout' | 'verify'>('register')
  const [pgEmail, setPgEmail] = useState('')
  const [pgPassword, setPgPassword] = useState('')
  const [pgFields, setPgFields] = useState<Record<string, any>>({})
  const [pgAccessToken, setPgAccessToken] = useState('')
  const [pgRefreshToken, setPgRefreshToken] = useState('')
  const [pgOldPassword, setPgOldPassword] = useState('')
  const [pgNewPassword, setPgNewPassword] = useState('')
  const [pgResult, setPgResult] = useState<string | null>(null)
  const [pgLoading, setPgLoading] = useState(false)
  const [pgStatus, setPgStatus] = useState<number | null>(null)

  // Copy state
  const [copiedKey, setCopiedKey] = useState<string | null>(null)

  const load = async () => {
    if (!id) return
    try {
      const { data } = await getAuthSystem(id)
      setSystem(data)
      setFormName(data.name)
      setFormSlug(data.slug)
      setFormAccessTTL(data.access_token_ttl_minutes)
      setFormRefreshTTL(data.refresh_token_ttl_days)
      setFormActive(data.is_active)
      setFormUsersActiveByDefault(data.users_active_by_default)
      setFormFields(data.registration_fields.map(f => ({ ...f })))
      setFormEmailEnabled(data.email_verification_enabled)
      setFormRequireVerification(data.require_email_verification)
      setFormProviderType(data.email_provider_type || '')
      setFormProviderConfig(data.email_provider_config || {})
      setFormFromAddress(data.email_from_address || '')
      setFormFromName(data.email_from_name || '')
      setFormTokenTTL(data.verification_token_ttl_minutes)
      setFormRedirectUrl(data.verification_redirect_url || '')
      setFormTemplateSubject(data.email_template_subject || '')
      setFormTemplateBody(data.email_template_body || '')
    } catch {
      toast.error('Auth system not found')
      navigate('/auth-systems')
    }
  }

  useEffect(() => { load() }, [id])
  useEffect(() => { fetchSettings().then(r => setAiSettings(r.data)).catch(() => {}) }, [])

  const loadUsers = async () => {
    if (!id || usersLoaded) return
    try {
      const { data } = await fetchAuthSystemUsers(id)
      setUsers(data)
      setUsersLoaded(true)
    } catch {
      setUsers([])
    }
  }

  const loadStats = async () => {
    if (!id) return
    try {
      const { data } = await fetchAuthSystemStats(id, statsHours)
      setStats(data)
    } catch { setStats(null) }
  }

  useEffect(() => {
    if (tab === 'users') loadUsers()
    if (tab === 'stats') loadStats()
  }, [tab, statsHours])

  const handleSaveSettings = async () => {
    if (!id) return
    setSaving(true)
    try {
      const { data } = await updateAuthSystem(id, {
        name: formName,
        access_token_ttl_minutes: formAccessTTL,
        refresh_token_ttl_days: formRefreshTTL,
        is_active: formActive,
        users_active_by_default: formUsersActiveByDefault,
      })
      setSystem(data)
      toast.success('Settings saved')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error saving')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveFields = async () => {
    if (!id) return
    setSaving(true)
    try {
      const validFields = formFields.filter(f => f.name.trim() !== '')
      const { data } = await updateAuthSystem(id, { registration_fields: validFields })
      setSystem(data)
      setFormFields(data.registration_fields.map(f => ({ ...f })))
      toast.success('Fields saved')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error saving')
    } finally {
      setSaving(false)
    }
  }

  const addField = () => setFormFields([...formFields, { name: '', type: 'string', required: true, unique: false }])
  const removeField = (idx: number) => setFormFields(formFields.filter((_, i) => i !== idx))
  const updateField = (idx: number, key: keyof RegistrationField, value: any) => {
    const updated = [...formFields]
    ;(updated[idx] as any)[key] = value
    setFormFields(updated)
  }

  const copyText = (text: string, key: string) => {
    navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey(null), 2000)
  }

  const handleAiGenerateTemplate = async () => {
    if (!system) return
    setAiGenerating(true)
    try {
      const { data } = await aiGenerateEmailTemplate({
        name: system.name,
        registration_fields: system.registration_fields.map(f => f.name),
        language: 'Russian',
        brand_color: '#2563eb',
      })
      if (data.subject) setFormTemplateSubject(data.subject)
      if (data.body) setFormTemplateBody(data.body)
      toast.success('Template generated')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'AI generation failed')
    } finally {
      setAiGenerating(false)
    }
  }

  const handleSaveEmail = async () => {
    if (!id) return
    setEmailSaving(true)
    try {
      const { data } = await updateAuthSystem(id, {
        email_verification_enabled: formEmailEnabled,
        require_email_verification: formRequireVerification,
        email_provider_type: formProviderType || null,
        email_provider_config: Object.keys(formProviderConfig).length > 0 ? formProviderConfig : null,
        email_from_address: formFromAddress || null,
        email_from_name: formFromName || null,
        verification_token_ttl_minutes: formTokenTTL,
        verification_redirect_url: formRedirectUrl || null,
        email_template_subject: formTemplateSubject || null,
        email_template_body: formTemplateBody || null,
      } as any)
      setSystem(data)
      toast.success('Email settings saved')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error saving')
    } finally {
      setEmailSaving(false)
    }
  }

  const handleTestEmail = async () => {
    if (!id || !testEmailTo) return
    setTestEmailSending(true)
    try {
      await sendTestEmail(id, testEmailTo)
      toast.success(`Test email sent to ${testEmailTo}`)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to send test email')
    } finally {
      setTestEmailSending(false)
    }
  }

  const openEditUser = (u: AuthSystemUser) => {
    setEditUser(u)
    setEditEmail(u.email)
    setEditFields({ ...u.custom_fields })
  }

  const handleSaveUser = async () => {
    if (!editUser || !id) return
    try {
      const { data } = await updateAuthUser(id, editUser.id, { email: editEmail, custom_fields: editFields })
      setUsers(users.map(u => u.id === editUser.id ? data : u))
      setEditUser(null)
      toast.success('User updated')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error')
    }
  }

  const handleResetPassword = async () => {
    if (!resetPwUser || !id || resetPwValue.length < 6) return
    try {
      await resetAuthUserPassword(id, resetPwUser.id, resetPwValue)
      setResetPwUser(null)
      setResetPwValue('')
      toast.success('Password reset')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error')
    }
  }

  const executePg = async () => {
    if (!system) return
    setPgLoading(true)
    setPgResult(null)
    setPgStatus(null)
    const base = `/api/auth/${system.slug}`
    try {
      let res: any
      if (pgAction === 'register') {
        res = await axios.post(`${base}/register`, { email: pgEmail, password: pgPassword, fields: pgFields })
      } else if (pgAction === 'login') {
        res = await axios.post(`${base}/login`, { email: pgEmail, password: pgPassword })
      } else if (pgAction === 'me') {
        res = await axios.get(`${base}/me`, { headers: { Authorization: `Bearer ${pgAccessToken}` } })
      } else if (pgAction === 'refresh') {
        res = await axios.post(`${base}/refresh`, { refresh_token: pgRefreshToken })
      } else if (pgAction === 'update-profile') {
        res = await axios.patch(`${base}/me`, { fields: pgFields }, { headers: { Authorization: `Bearer ${pgAccessToken}` } })
      } else if (pgAction === 'change-password') {
        res = await axios.post(`${base}/change-password`, { old_password: pgOldPassword, new_password: pgNewPassword }, { headers: { Authorization: `Bearer ${pgAccessToken}` } })
      } else if (pgAction === 'logout') {
        res = await axios.post(`${base}/logout`, { refresh_token: pgRefreshToken })
      } else if (pgAction === 'verify') {
        res = await axios.get(`${base}/verify`, { headers: { Authorization: `Bearer ${pgAccessToken}` } })
      }
      setPgStatus(res.status)
      setPgResult(JSON.stringify(res.data, null, 2))
      if ((pgAction === 'register' || pgAction === 'login' || pgAction === 'refresh') && res.data.access_token) {
        setPgAccessToken(res.data.access_token)
        setPgRefreshToken(res.data.refresh_token)
      }
    } catch (err: any) {
      setPgStatus(err.response?.status || 0)
      setPgResult(JSON.stringify(err.response?.data || { error: err.message }, null, 2))
    } finally {
      setPgLoading(false)
    }
  }

  if (!system) return null

  const baseUrl = `${window.location.origin}/api/auth/${system.slug}`

  const tabs: { key: Tab; label: string; icon: typeof Settings }[] = [
    { key: 'settings', label: 'Settings', icon: Settings },
    { key: 'verification', label: 'Verification', icon: ShieldCheck },
    { key: 'fields', label: 'Fields', icon: Layers },
    { key: 'users', label: 'Users', icon: Users },
    { key: 'stats', label: 'Stats', icon: BarChart3 },
    { key: 'playground', label: 'Playground', icon: FlaskConical },
    { key: 'api', label: 'API Docs', icon: Code },
  ]

  // Build example registration body
  const regBodyExample: Record<string, any> = { email: 'user@example.com', password: 'secret123' }
  if (system.registration_fields.length > 0) {
    const fieldsExample: Record<string, any> = {}
    for (const f of system.registration_fields) {
      if (f.type === 'string' || f.type === 'email' || f.type === 'phone') fieldsExample[f.name] = f.type === 'email' ? 'value@example.com' : f.type === 'phone' ? '+77001234567' : 'value'
      else if (f.type === 'number') fieldsExample[f.name] = 0
      else if (f.type === 'boolean') fieldsExample[f.name] = true
    }
    regBodyExample.fields = fieldsExample
  }

  const endpoints = [
    {
      title: 'Register',
      method: 'POST',
      path: '/register',
      description: 'Register a new user. Returns access and refresh tokens.',
      curl: `curl -X POST ${baseUrl}/register \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify(regBodyExample, null, 2)}'`,
      response: '{\n  "access_token": "eyJ...",\n  "refresh_token": "abc...",\n  "token_type": "bearer",\n  "expires_in": ' + system.access_token_ttl_minutes * 60 + '\n}',
    },
    {
      title: 'Login',
      method: 'POST',
      path: '/login',
      description: 'Authenticate user by email and password.',
      curl: `curl -X POST ${baseUrl}/login \\\n  -H "Content-Type: application/json" \\\n  -d '{"email": "user@example.com", "password": "secret123"}'`,
      response: '{\n  "access_token": "eyJ...",\n  "refresh_token": "abc...",\n  "token_type": "bearer",\n  "expires_in": ' + system.access_token_ttl_minutes * 60 + '\n}',
    },
    {
      title: 'Get Current User',
      method: 'GET',
      path: '/me',
      description: 'Get authenticated user profile. Requires access token.',
      curl: `curl ${baseUrl}/me \\\n  -H "Authorization: Bearer ACCESS_TOKEN"`,
      response: '{\n  "id": "uuid",\n  "email": "user@example.com",\n  "custom_fields": {...},\n  "is_active": true,\n  "created_at": "2026-03-31T..."\n}',
    },
    {
      title: 'Refresh Token',
      method: 'POST',
      path: '/refresh',
      description: 'Exchange refresh token for a new access token. Old refresh token is rotated.',
      curl: `curl -X POST ${baseUrl}/refresh \\\n  -H "Content-Type: application/json" \\\n  -d '{"refresh_token": "abc..."}'`,
      response: '{\n  "access_token": "eyJ...(new)",\n  "refresh_token": "def...(new)",\n  "token_type": "bearer",\n  "expires_in": ' + system.access_token_ttl_minutes * 60 + '\n}',
    },
    {
      title: 'Verify Token',
      method: 'GET',
      path: '/verify',
      description: 'Check if access token is valid. Use for middleware/gateway auth checks.',
      curl: `curl ${baseUrl}/verify \\\n  -H "Authorization: Bearer ACCESS_TOKEN"`,
      response: '{\n  "valid": true,\n  "user_id": "uuid",\n  "email": "user@example.com"\n}',
    },
    {
      title: 'Update Profile',
      method: 'PATCH',
      path: '/me',
      description: 'Update custom fields of the authenticated user.',
      curl: `curl -X PATCH ${baseUrl}/me \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer ACCESS_TOKEN" \\\n  -d '{"fields": {...}}'`,
      response: '{\n  "id": "uuid",\n  "email": "user@example.com",\n  "custom_fields": {...},\n  "is_active": true,\n  "created_at": "..."\n}',
    },
    {
      title: 'Change Password',
      method: 'POST',
      path: '/change-password',
      description: 'Change password for the authenticated user.',
      curl: `curl -X POST ${baseUrl}/change-password \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer ACCESS_TOKEN" \\\n  -d '{"old_password": "current", "new_password": "newpass123"}'`,
      response: '{\n  "ok": true\n}',
    },
    {
      title: 'Logout',
      method: 'POST',
      path: '/logout',
      description: 'Invalidate refresh token. Use on user logout.',
      curl: `curl -X POST ${baseUrl}/logout \\\n  -H "Content-Type: application/json" \\\n  -d '{"refresh_token": "abc..."}'`,
      response: '{\n  "ok": true\n}',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/auth-systems')}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h2 className="text-2xl font-bold">{system.name}</h2>
          <p className="text-sm text-muted-foreground font-mono">/auth/{system.slug}/</p>
        </div>
        <Badge variant={system.is_active ? 'success' : 'secondary'} className="ml-2">
          {system.is_active ? 'Active' : 'Inactive'}
        </Badge>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? 'border-foreground text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Settings Tab */}
      {tab === 'settings' && (
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={formName} onChange={e => setFormName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Slug</Label>
                <Input value={system?.slug || ''} disabled className="font-mono" />
                <p className="text-xs text-muted-foreground">Slug cannot be changed after creation</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Access Token TTL (minutes)</Label>
                <Input type="number" min={1} value={formAccessTTL} onChange={e => setFormAccessTTL(parseInt(e.target.value) || 60)} />
              </div>
              <div className="space-y-2">
                <Label>Refresh Token TTL (days)</Label>
                <Input type="number" min={1} value={formRefreshTTL} onChange={e => setFormRefreshTTL(parseInt(e.target.value) || 30)} />
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="flex items-center space-x-2">
                <Switch checked={formActive} onCheckedChange={setFormActive} id="active-switch" />
                <Label htmlFor="active-switch">System Active</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Switch checked={formUsersActiveByDefault} onCheckedChange={setFormUsersActiveByDefault} id="users-active-switch" />
                <Label htmlFor="users-active-switch">Users active by default</Label>
              </div>
            </div>
            <div className="flex justify-end">
              <Button onClick={handleSaveSettings} disabled={saving}>
                <Save className="h-4 w-4 mr-2" />{saving ? 'Saving...' : 'Save Settings'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Verification Tab */}
      {tab === 'verification' && (
        <ChannelList systemId={id!} systemName={system.name} />
      )}

      {/* Fields Tab */}
      {tab === 'fields' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Constructor */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Registration Fields</CardTitle>
                <Button variant="outline" size="sm" onClick={addField}>
                  <Plus className="h-4 w-4 mr-1" />Add Field
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">Email and password are always included.</p>
            </CardHeader>
            <CardContent className="space-y-2">
              {formFields.map((field, idx) => (
                <div key={idx} className="flex items-center gap-2 p-3 border rounded-md">
                  <Input
                    value={field.name}
                    onChange={e => updateField(idx, 'name', e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                    placeholder="field_name"
                    className="w-32"
                  />
                  <Select value={field.type} onValueChange={v => updateField(idx, 'type', v)}>
                    <SelectTrigger className="w-28">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {FIELD_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <div className="flex items-center space-x-1">
                    <Checkbox checked={field.required} onCheckedChange={v => updateField(idx, 'required', !!v)} />
                    <span className="text-xs">Req</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <Checkbox checked={field.unique} onCheckedChange={v => updateField(idx, 'unique', !!v)} />
                    <span className="text-xs">Uniq</span>
                  </div>
                  <Button type="button" variant="ghost" size="icon" onClick={() => removeField(idx)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              ))}
              {formFields.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">No custom fields. Only email + password.</p>
              )}
              <div className="flex justify-end pt-2">
                <Button onClick={handleSaveFields} disabled={saving}>
                  <Save className="h-4 w-4 mr-2" />{saving ? 'Saving...' : 'Save Fields'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Preview */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Registration Form Preview</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 p-4 border rounded-md bg-muted/30">
                <div className="space-y-1">
                  <label className="text-sm font-medium">Email <span className="text-destructive">*</span></label>
                  <Input disabled placeholder="user@example.com" />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Password <span className="text-destructive">*</span></label>
                  <Input disabled type="password" placeholder="********" />
                </div>
                {formFields.filter(f => f.name.trim()).map(f => (
                  <div key={f.name} className="space-y-1">
                    <label className="text-sm font-medium">
                      {f.name}
                      {f.required && <span className="text-destructive"> *</span>}
                      {f.unique && <Badge variant="outline" className="ml-1 text-[10px] px-1 py-0">unique</Badge>}
                    </label>
                    {f.type === 'boolean' ? (
                      <div className="flex items-center space-x-2">
                        <Checkbox disabled />
                        <span className="text-sm text-muted-foreground">{f.name}</span>
                      </div>
                    ) : (
                      <Input
                        disabled
                        placeholder={f.type === 'email' ? 'value@example.com' : f.type === 'phone' ? '+77001234567' : f.type === 'number' ? '0' : 'value'}
                        type={f.type === 'number' ? 'number' : 'text'}
                      />
                    )}
                  </div>
                ))}
                <Button disabled className="w-full mt-2">Register</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Users Tab */}
      {tab === 'users' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Registered Users ({users.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 pr-4">Email</th>
                    <th className="pb-2 pr-4">Status</th>
                    {system.registration_fields.map(f => (
                      <th key={f.name} className="pb-2 pr-4">{f.name}</th>
                    ))}
                    <th className="pb-2 pr-4">Created</th>
                    <th className="pb-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id} className="border-b border-border/50">
                      <td className="py-2 pr-4 font-medium flex items-center gap-1">
                        {u.email}
                        {u.email_verified
                          ? <span title="Email verified"><CheckCircle className="h-3.5 w-3.5 text-green-500 shrink-0" /></span>
                          : <span title="Not verified"><XCircle className="h-3.5 w-3.5 text-muted-foreground shrink-0" /></span>
                        }
                      </td>
                      <td className="py-2 pr-4">
                        <Badge variant={u.is_active ? 'success' : 'secondary'} className="text-xs">
                          {u.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      {system.registration_fields.map(f => (
                        <td key={f.name} className="py-2 pr-4 text-muted-foreground">
                          {u.custom_fields[f.name]?.toString() ?? '-'}
                        </td>
                      ))}
                      <td className="py-2 pr-4 text-muted-foreground">{new Date(u.created_at).toLocaleDateString()}</td>
                      <td className="py-2">
                        <div className="flex gap-1">
                          <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => openEditUser(u)} title="Edit">
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => { setResetPwUser(u); setResetPwValue('') }} title="Reset password">
                            <KeyRound className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7"
                            onClick={async () => {
                              await toggleAuthUser(id!, u.id)
                              setUsers(users.map(x => x.id === u.id ? { ...x, is_active: !x.is_active } : x))
                              toast.success(u.is_active ? 'User deactivated' : 'User activated')
                            }}
                          >
                            {u.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td colSpan={4 + system.registration_fields.length} className="py-8 text-center text-muted-foreground">
                        No users registered yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Tab */}
      {tab === 'stats' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div />
            <Select value={String(statsHours)} onValueChange={v => setStatsHours(Number(v))}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24">Last 24 hours</SelectItem>
                <SelectItem value="168">Last 7 days</SelectItem>
                <SelectItem value="720">Last 30 days</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total Users</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{stats?.total_users ?? '-'}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Active</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-green-500">{stats?.active_users ?? '-'}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Inactive</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{stats?.inactive_users ?? '-'}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">New Users</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{stats?.new_users ?? '-'}</div>
                <p className="text-xs text-muted-foreground">in selected period</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Registrations Over Time</CardTitle>
            </CardHeader>
            <CardContent>
              <RegistrationsChart data={stats?.timeseries ?? []} hours={statsHours} />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Playground Tab */}
      {tab === 'playground' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Request</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Action</Label>
                <Select value={pgAction} onValueChange={v => setPgAction(v as any)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="register">POST /register</SelectItem>
                    <SelectItem value="login">POST /login</SelectItem>
                    <SelectItem value="me">GET /me</SelectItem>
                    <SelectItem value="update-profile">PATCH /me</SelectItem>
                    <SelectItem value="change-password">POST /change-password</SelectItem>
                    <SelectItem value="refresh">POST /refresh</SelectItem>
                    <SelectItem value="logout">POST /logout</SelectItem>
                    <SelectItem value="verify">GET /verify</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {(pgAction === 'register' || pgAction === 'login') && (
                <>
                  <div className="space-y-2">
                    <Label>Email</Label>
                    <Input value={pgEmail} onChange={e => setPgEmail(e.target.value)} placeholder="user@example.com" />
                  </div>
                  <div className="space-y-2">
                    <Label>Password</Label>
                    <Input type="password" value={pgPassword} onChange={e => setPgPassword(e.target.value)} placeholder="******" />
                  </div>
                </>
              )}

              {pgAction === 'register' && system.registration_fields.length > 0 && (
                <div className="space-y-2">
                  <Label>Custom Fields</Label>
                  {system.registration_fields.map(f => (
                    <div key={f.name} className="flex items-center gap-2">
                      <span className="text-sm w-28 shrink-0">{f.name}{f.required ? ' *' : ''}</span>
                      {f.type === 'boolean' ? (
                        <Checkbox
                          checked={!!pgFields[f.name]}
                          onCheckedChange={v => setPgFields({ ...pgFields, [f.name]: !!v })}
                        />
                      ) : (
                        <Input
                          value={pgFields[f.name] ?? ''}
                          onChange={e => setPgFields({ ...pgFields, [f.name]: f.type === 'number' ? Number(e.target.value) : e.target.value })}
                          type={f.type === 'number' ? 'number' : 'text'}
                          placeholder={f.type}
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}

              {(pgAction === 'me' || pgAction === 'verify' || pgAction === 'update-profile' || pgAction === 'change-password') && (
                <div className="space-y-2">
                  <Label>Access Token</Label>
                  <Input value={pgAccessToken} onChange={e => setPgAccessToken(e.target.value)} placeholder="eyJ..." className="font-mono text-xs" />
                </div>
              )}

              {pgAction === 'update-profile' && system.registration_fields.length > 0 && (
                <div className="space-y-2">
                  <Label>Fields to Update</Label>
                  {system.registration_fields.map(f => (
                    <div key={f.name} className="flex items-center gap-2">
                      <span className="text-sm w-28 shrink-0">{f.name}</span>
                      {f.type === 'boolean' ? (
                        <Checkbox checked={!!pgFields[f.name]} onCheckedChange={v => setPgFields({ ...pgFields, [f.name]: !!v })} />
                      ) : (
                        <Input
                          value={pgFields[f.name] ?? ''}
                          onChange={e => setPgFields({ ...pgFields, [f.name]: f.type === 'number' ? Number(e.target.value) : e.target.value })}
                          type={f.type === 'number' ? 'number' : 'text'}
                          placeholder={f.type}
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}

              {pgAction === 'change-password' && (
                <>
                  <div className="space-y-2">
                    <Label>Old Password</Label>
                    <Input type="password" value={pgOldPassword} onChange={e => setPgOldPassword(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label>New Password</Label>
                    <Input type="password" value={pgNewPassword} onChange={e => setPgNewPassword(e.target.value)} placeholder="Min 6 characters" />
                  </div>
                </>
              )}

              {(pgAction === 'refresh' || pgAction === 'logout') && (
                <div className="space-y-2">
                  <Label>Refresh Token</Label>
                  <Input value={pgRefreshToken} onChange={e => setPgRefreshToken(e.target.value)} placeholder="token..." className="font-mono text-xs" />
                </div>
              )}

              <Button onClick={executePg} disabled={pgLoading} className="w-full">
                {pgLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                Execute
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Response</CardTitle>
                {pgStatus && (
                  <Badge variant={pgStatus < 400 ? 'success' : 'destructive'}>{pgStatus}</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {pgResult ? (
                <pre className="bg-muted p-4 rounded text-xs font-mono overflow-auto max-h-[500px] whitespace-pre">{pgResult}</pre>
              ) : (
                <div className="flex items-center justify-center h-[200px] text-muted-foreground">
                  Execute a request to see the response
                </div>
              )}
              {pgAccessToken && (
                <div className="mt-4 space-y-2">
                  <Label className="text-xs text-muted-foreground">Stored Access Token</Label>
                  <Input value={pgAccessToken} readOnly className="font-mono text-xs" />
                  <Label className="text-xs text-muted-foreground">Stored Refresh Token</Label>
                  <Input value={pgRefreshToken} readOnly className="font-mono text-xs" />
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* API Docs Tab */}
      {tab === 'api' && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Base URL</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-muted px-3 py-2 rounded font-mono text-sm">{baseUrl}</code>
                <Button variant="outline" size="icon" onClick={() => copyText(baseUrl, 'base')}>
                  {copiedKey === 'base' ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                </Button>
                <a href={`${baseUrl}/docs`} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm">Swagger UI</Button>
                </a>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                No API key required. Endpoints are public, identified by slug.
              </p>
            </CardContent>
          </Card>

          {endpoints.map(ep => (
            <Card key={ep.path}>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Badge variant={ep.method === 'GET' ? 'outline' : 'default'} className="text-xs font-mono">{ep.method}</Badge>
                  <CardTitle className="text-base font-mono">{ep.path}</CardTitle>
                  <span className="text-sm text-muted-foreground ml-2">{ep.title}</span>
                </div>
                <p className="text-sm text-muted-foreground">{ep.description}</p>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-muted-foreground">Request</span>
                    <Button variant="ghost" size="sm" className="h-6 px-2" onClick={() => copyText(ep.curl, ep.path)}>
                      {copiedKey === ep.path ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
                      <span className="ml-1 text-xs">Copy</span>
                    </Button>
                  </div>
                  <pre className="bg-muted p-3 rounded text-xs font-mono overflow-x-auto whitespace-pre">{ep.curl}</pre>
                </div>
                <div>
                  <span className="text-xs font-medium text-muted-foreground">Response</span>
                  <pre className="bg-muted p-3 rounded text-xs font-mono overflow-x-auto whitespace-pre mt-1">{ep.response}</pre>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {/* Edit User Modal */}
      <Dialog open={!!editUser} onOpenChange={open => { if (!open) setEditUser(null) }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
          </DialogHeader>
          {editUser && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Email</Label>
                <Input value={editEmail} onChange={e => setEditEmail(e.target.value)} />
              </div>
              {system.registration_fields.map(f => (
                <div key={f.name} className="space-y-2">
                  <Label>{f.name}</Label>
                  {f.type === 'boolean' ? (
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        checked={!!editFields[f.name]}
                        onCheckedChange={v => setEditFields({ ...editFields, [f.name]: !!v })}
                      />
                    </div>
                  ) : (
                    <Input
                      value={editFields[f.name] ?? ''}
                      onChange={e => setEditFields({ ...editFields, [f.name]: f.type === 'number' ? Number(e.target.value) : e.target.value })}
                      type={f.type === 'number' ? 'number' : 'text'}
                    />
                  )}
                </div>
              ))}
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setEditUser(null)}>Cancel</Button>
                <Button onClick={handleSaveUser}>Save</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Reset Password Modal */}
      <Dialog open={!!resetPwUser} onOpenChange={open => { if (!open) setResetPwUser(null) }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Reset Password</DialogTitle>
          </DialogHeader>
          {resetPwUser && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Set new password for <span className="font-medium text-foreground">{resetPwUser.email}</span>
              </p>
              <div className="space-y-2">
                <Label>New Password</Label>
                <Input type="password" value={resetPwValue} onChange={e => setResetPwValue(e.target.value)} placeholder="Min 6 characters" />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setResetPwUser(null)}>Cancel</Button>
                <Button onClick={handleResetPassword} disabled={resetPwValue.length < 6}>Reset Password</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
