import { useEffect, useState } from 'react'
import {
  fetchPermissions, createPermission, updatePermission, deletePermission,
  fetchRoles, createRole, updateRole, deleteRole, setRolePermissions,
  AuthPermission, AuthRole,
} from '@/api/authRoles'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Plus, Trash2, Pencil, Shield, Key, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

type InnerTab = 'roles' | 'permissions'

export function RolesTab({ systemId }: { systemId: string }) {
  const [tab, setTab] = useState<InnerTab>('roles')
  const [loading, setLoading] = useState(true)

  const [permissions, setPermissions] = useState<AuthPermission[]>([])
  const [roles, setRoles] = useState<AuthRole[]>([])

  // Create/Edit permission modal
  const [permDialog, setPermDialog] = useState(false)
  const [editPerm, setEditPerm] = useState<AuthPermission | null>(null)
  const [permSlug, setPermSlug] = useState('')
  const [permName, setPermName] = useState('')
  const [permDesc, setPermDesc] = useState('')
  const [permSaving, setPermSaving] = useState(false)

  // Create/Edit role modal
  const [roleDialog, setRoleDialog] = useState(false)
  const [editRole, setEditRole] = useState<AuthRole | null>(null)
  const [roleSlug, setRoleSlug] = useState('')
  const [roleName, setRoleName] = useState('')
  const [roleDesc, setRoleDesc] = useState('')
  const [roleIsDefault, setRoleIsDefault] = useState(false)
  const [roleIsAdmin, setRoleIsAdmin] = useState(false)
  const [rolePermIds, setRolePermIds] = useState<string[]>([])
  const [roleSaving, setRoleSaving] = useState(false)

  // Delete confirm
  const [deleteRoleTarget, setDeleteRoleTarget] = useState<AuthRole | null>(null)
  const [deletePermTarget, setDeletePermTarget] = useState<AuthPermission | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [permsRes, rolesRes] = await Promise.all([
        fetchPermissions(systemId),
        fetchRoles(systemId),
      ])
      setPermissions(permsRes.data)
      setRoles(rolesRes.data)
    } catch {
      toast.error('Не удалось загрузить данные')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [systemId])

  // Permission handlers
  const openCreatePerm = () => {
    setEditPerm(null)
    setPermSlug('')
    setPermName('')
    setPermDesc('')
    setPermDialog(true)
  }

  const openEditPerm = (p: AuthPermission) => {
    setEditPerm(p)
    setPermSlug(p.slug)
    setPermName(p.name)
    setPermDesc(p.description ?? '')
    setPermDialog(true)
  }

  const handleSavePerm = async () => {
    if (!permSlug.trim() || !permName.trim()) return
    setPermSaving(true)
    try {
      if (editPerm) {
        const { data } = await updatePermission(systemId, editPerm.id, {
          name: permName,
          description: permDesc || undefined,
        })
        setPermissions(permissions.map(p => p.id === editPerm.id ? data : p))
        toast.success('Разрешение обновлено')
      } else {
        const { data } = await createPermission(systemId, {
          slug: permSlug,
          name: permName,
          description: permDesc || undefined,
        })
        setPermissions([...permissions, data])
        toast.success('Разрешение создано')
      }
      setPermDialog(false)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка сохранения')
    } finally {
      setPermSaving(false)
    }
  }

  const handleDeletePerm = async () => {
    if (!deletePermTarget) return
    setDeleting(true)
    try {
      await deletePermission(systemId, deletePermTarget.id)
      setPermissions(permissions.filter(p => p.id !== deletePermTarget.id))
      setDeletePermTarget(null)
      toast.success('Разрешение удалено')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка удаления')
    } finally {
      setDeleting(false)
    }
  }

  // Role handlers
  const openCreateRole = () => {
    setEditRole(null)
    setRoleSlug('')
    setRoleName('')
    setRoleDesc('')
    setRoleIsDefault(false)
    setRoleIsAdmin(false)
    setRolePermIds([])
    setRoleDialog(true)
  }

  const openEditRole = (r: AuthRole) => {
    setEditRole(r)
    setRoleSlug(r.slug)
    setRoleName(r.name)
    setRoleDesc(r.description ?? '')
    setRoleIsDefault(r.is_default)
    setRoleIsAdmin(r.is_admin_role)
    setRolePermIds(r.permissions.map(p => p.id))
    setRoleDialog(true)
  }

  const handleSaveRole = async () => {
    if (!roleName.trim()) return
    setRoleSaving(true)
    try {
      if (editRole) {
        await Promise.all([
          updateRole(systemId, editRole.id, {
            name: roleName,
            description: roleDesc || undefined,
            is_default: roleIsDefault,
            is_admin_role: roleIsAdmin,
          }),
          setRolePermissions(systemId, editRole.id, rolePermIds),
        ])
        // Reload roles to get updated permissions
        const { data: rolesData } = await fetchRoles(systemId)
        setRoles(rolesData)
        toast.success('Роль обновлена')
      } else {
        if (!roleSlug.trim()) return
        const { data } = await createRole(systemId, {
          slug: roleSlug,
          name: roleName,
          description: roleDesc || undefined,
          is_default: roleIsDefault,
          is_admin_role: roleIsAdmin,
          permission_ids: rolePermIds,
        })
        setRoles([...roles, data])
        toast.success('Роль создана')
      }
      setRoleDialog(false)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка сохранения')
    } finally {
      setRoleSaving(false)
    }
  }

  const handleDeleteRole = async () => {
    if (!deleteRoleTarget) return
    setDeleting(true)
    try {
      await deleteRole(systemId, deleteRoleTarget.id)
      setRoles(roles.filter(r => r.id !== deleteRoleTarget.id))
      setDeleteRoleTarget(null)
      toast.success('Роль удалена')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка удаления')
    } finally {
      setDeleting(false)
    }
  }

  const toggleRolePermId = (id: string) => {
    setRolePermIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const innerTabs: { key: InnerTab; label: string; icon: typeof Shield }[] = [
    { key: 'roles', label: 'Роли', icon: Shield },
    { key: 'permissions', label: 'Разрешения', icon: Key },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-xl font-bold">Роли и разрешения</h3>
      </div>

      {/* Inner Tabs */}
      <div className="flex gap-1 border-b">
        {innerTabs.map(t => (
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

      {/* Roles Tab */}
      {tab === 'roles' && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Роли ({roles.length})</CardTitle>
              <Button size="sm" onClick={openCreateRole}>
                <Plus className="h-4 w-4 mr-1" />Создать роль
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 pr-4">Slug</th>
                    <th className="pb-2 pr-4">Название</th>
                    <th className="pb-2 pr-4">Разрешения</th>
                    <th className="pb-2 pr-4">Флаги</th>
                    <th className="pb-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {roles.map(r => (
                    <tr key={r.id} className="border-b border-border/50">
                      <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">{r.slug}</td>
                      <td className="py-2 pr-4 font-medium">{r.name}</td>
                      <td className="py-2 pr-4">
                        <span className="text-muted-foreground">{r.permissions.length}</span>
                      </td>
                      <td className="py-2 pr-4">
                        <div className="flex gap-1 flex-wrap">
                          {r.is_default && (
                            <Badge variant="outline" className="text-xs">По умолчанию</Badge>
                          )}
                          {r.is_system && (
                            <Badge variant="secondary" className="text-xs">Системная</Badge>
                          )}
                          {r.is_admin_role && (
                            <Badge variant="destructive" className="text-xs">Админская</Badge>
                          )}
                        </div>
                      </td>
                      <td className="py-2">
                        <div className="flex gap-1">
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => openEditRole(r)}
                            title="Редактировать"
                            disabled={r.is_system}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setDeleteRoleTarget(r)}
                            title="Удалить"
                            disabled={r.is_system}
                          >
                            <Trash2 className="h-3.5 w-3.5 text-destructive" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {roles.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-muted-foreground">
                        Роли не созданы
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Permissions Tab */}
      {tab === 'permissions' && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Разрешения ({permissions.length})</CardTitle>
              <Button size="sm" onClick={openCreatePerm}>
                <Plus className="h-4 w-4 mr-1" />Создать разрешение
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 pr-4">Slug</th>
                    <th className="pb-2 pr-4">Название</th>
                    <th className="pb-2 pr-4">Описание</th>
                    <th className="pb-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {permissions.map(p => (
                    <tr key={p.id} className="border-b border-border/50">
                      <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">{p.slug}</td>
                      <td className="py-2 pr-4 font-medium">{p.name}</td>
                      <td className="py-2 pr-4 text-muted-foreground">{p.description ?? '—'}</td>
                      <td className="py-2">
                        <div className="flex gap-1">
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => openEditPerm(p)}
                            title="Редактировать"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => setDeletePermTarget(p)}
                            title="Удалить"
                          >
                            <Trash2 className="h-3.5 w-3.5 text-destructive" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {permissions.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-muted-foreground">
                        Разрешения не созданы
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Create/Edit Permission Modal */}
      <Dialog open={permDialog} onOpenChange={open => { if (!open) setPermDialog(false) }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editPerm ? 'Редактировать разрешение' : 'Создать разрешение'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {!editPerm && (
              <div className="space-y-2">
                <Label>Slug</Label>
                <Input
                  value={permSlug}
                  onChange={e => setPermSlug(e.target.value.toLowerCase().replace(/[^a-z0-9_.]/g, ''))}
                  placeholder="posts.create"
                  className="font-mono"
                />
              </div>
            )}
            <div className="space-y-2">
              <Label>Название</Label>
              <Input value={permName} onChange={e => setPermName(e.target.value)} placeholder="Чтение пользователей" />
            </div>
            <div className="space-y-2">
              <Label>Описание <span className="text-muted-foreground text-xs">(необязательно)</span></Label>
              <Input value={permDesc} onChange={e => setPermDesc(e.target.value)} placeholder="Описание разрешения" />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setPermDialog(false)}>Отмена</Button>
              <Button onClick={handleSavePerm} disabled={permSaving || !permName.trim() || (!editPerm && !permSlug.trim())}>
                {permSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Сохранить
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Create/Edit Role Modal */}
      <Dialog open={roleDialog} onOpenChange={open => { if (!open) setRoleDialog(false) }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editRole ? 'Редактировать роль' : 'Создать роль'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {!editRole && (
              <div className="space-y-2">
                <Label>Slug</Label>
                <Input
                  value={roleSlug}
                  onChange={e => setRoleSlug(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
                  placeholder="editor"
                  className="font-mono"
                />
              </div>
            )}
            <div className="space-y-2">
              <Label>Название</Label>
              <Input value={roleName} onChange={e => setRoleName(e.target.value)} placeholder="Редактор" />
            </div>
            <div className="space-y-2">
              <Label>Описание <span className="text-muted-foreground text-xs">(необязательно)</span></Label>
              <Input value={roleDesc} onChange={e => setRoleDesc(e.target.value)} placeholder="Описание роли" />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="role-default"
                checked={roleIsDefault}
                onCheckedChange={v => setRoleIsDefault(!!v)}
              />
              <Label htmlFor="role-default">Назначать по умолчанию новым пользователям</Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="role-is-admin"
                checked={roleIsAdmin}
                onCheckedChange={v => setRoleIsAdmin(!!v)}
              />
              <Label htmlFor="role-is-admin">Админская роль (даёт право управлять другими юзерами через API)</Label>
            </div>
            {roleIsAdmin && (() => {
              const existingAdmin = roles.find(r => r.is_admin_role && r.id !== editRole?.id)
              return existingAdmin ? (
                <p className="text-xs text-amber-500 mt-1">
                  ⚠ Сейчас админская роль назначена «{existingAdmin.name}». При сохранении флаг будет снят с неё и назначен этой роли.
                </p>
              ) : null
            })()}
            {permissions.length > 0 && (
              <div className="space-y-2">
                <Label>Разрешения</Label>
                <div className="border rounded-md p-3 space-y-2 max-h-48 overflow-y-auto">
                  {permissions.map(p => (
                    <div key={p.id} className="flex items-center gap-2">
                      <Checkbox
                        id={`rp-${p.id}`}
                        checked={rolePermIds.includes(p.id)}
                        onCheckedChange={() => toggleRolePermId(p.id)}
                      />
                      <label htmlFor={`rp-${p.id}`} className="text-sm cursor-pointer flex-1">
                        <span className="font-medium">{p.name}</span>
                        <span className="text-muted-foreground font-mono text-xs ml-2">{p.slug}</span>
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setRoleDialog(false)}>Отмена</Button>
              <Button
                onClick={handleSaveRole}
                disabled={roleSaving || !roleName.trim() || (!editRole && !roleSlug.trim())}
              >
                {roleSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Сохранить
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Role Confirm */}
      <Dialog open={!!deleteRoleTarget} onOpenChange={open => { if (!open) setDeleteRoleTarget(null) }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Удалить роль</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Удалить роль <span className="font-medium text-foreground">{deleteRoleTarget?.name}</span>? Это действие необратимо.
          </p>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setDeleteRoleTarget(null)}>Отмена</Button>
            <Button variant="destructive" onClick={handleDeleteRole} disabled={deleting}>
              {deleting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Удалить
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Permission Confirm */}
      <Dialog open={!!deletePermTarget} onOpenChange={open => { if (!open) setDeletePermTarget(null) }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Удалить разрешение</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Удалить разрешение <span className="font-medium text-foreground">{deletePermTarget?.name}</span>? Это действие необратимо.
          </p>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setDeletePermTarget(null)}>Отмена</Button>
            <Button variant="destructive" onClick={handleDeletePerm} disabled={deleting}>
              {deleting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Удалить
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
