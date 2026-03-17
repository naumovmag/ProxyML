import { useEffect, useState } from 'react'
import { fetchUsers, approveUser, rejectUser, deleteUser, updateUser } from '@/api/users'
import type { UserRead } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { CheckCircle, XCircle, Trash2, Shield, ShieldOff } from 'lucide-react'
import { toast } from 'sonner'

export default function UsersPage() {
  const [users, setUsers] = useState<UserRead[]>([])
  const [confirmState, setConfirmState] = useState<{ open: boolean; title: string; description: string; onConfirm: () => void }>({
    open: false, title: '', description: '', onConfirm: () => {},
  })

  const load = () => {
    fetchUsers().then((r) => setUsers(r.data)).catch(() => toast.error('Failed to load users'))
  }
  useEffect(() => { load() }, [])

  const handleApprove = async (id: string) => {
    await approveUser(id)
    toast.success('User approved')
    load()
  }

  const handleReject = async (id: string) => {
    await rejectUser(id)
    toast.success('User rejected')
    load()
  }

  const handleToggleSuperadmin = async (user: UserRead) => {
    await updateUser(user.id, { is_superadmin: !user.is_superadmin })
    toast.success(user.is_superadmin ? 'Superadmin removed' : 'Superadmin granted')
    load()
  }

  const handleDelete = (id: string, username: string) => {
    setConfirmState({
      open: true,
      title: 'Delete user',
      description: `Are you sure you want to delete user "${username}"? All their services, API keys and data will be permanently deleted.`,
      onConfirm: async () => {
        try {
          await deleteUser(id)
          toast.success('User deleted')
          load()
        } catch (err: any) {
          toast.error(err.response?.data?.detail || 'Failed to delete user')
        }
      },
    })
  }

  const pendingUsers = users.filter((u) => !u.is_approved && u.is_active)
  const activeUsers = users.filter((u) => u.is_approved && u.is_active)
  const inactiveUsers = users.filter((u) => !u.is_active)

  const renderUser = (user: UserRead) => (
    <Card key={user.id}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div className="flex items-center gap-3">
          <CardTitle className="text-lg">{user.display_name || user.username}</CardTitle>
          <span className="text-sm text-muted-foreground">@{user.username}</span>
          {user.is_superadmin && <Badge variant="default">Superadmin</Badge>}
          {user.is_approved && user.is_active && <Badge variant="success">Active</Badge>}
          {!user.is_approved && user.is_active && <Badge variant="warning">Pending</Badge>}
          {!user.is_active && <Badge variant="secondary">Inactive</Badge>}
        </div>
        <div className="flex items-center gap-2">
          {!user.is_approved && user.is_active && (
            <>
              <Button variant="outline" size="sm" onClick={() => handleApprove(user.id)}>
                <CheckCircle className="h-4 w-4 mr-1 text-green-500" />
                Approve
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleReject(user.id)}>
                <XCircle className="h-4 w-4 mr-1 text-red-500" />
                Reject
              </Button>
            </>
          )}
          {!user.is_active && (
            <Button variant="outline" size="sm" onClick={() => handleApprove(user.id)}>
              <CheckCircle className="h-4 w-4 mr-1 text-green-500" />
              Reactivate
            </Button>
          )}
          {user.is_approved && user.is_active && (
            <Button variant="ghost" size="sm" onClick={() => handleToggleSuperadmin(user)} title={user.is_superadmin ? 'Remove superadmin' : 'Grant superadmin'}>
              {user.is_superadmin ? <ShieldOff className="h-4 w-4" /> : <Shield className="h-4 w-4" />}
            </Button>
          )}
          <Button variant="ghost" size="icon" onClick={() => handleDelete(user.id, user.username)}>
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-sm text-muted-foreground space-y-1">
          {user.email && <div><span className="font-medium">Email:</span> {user.email}</div>}
          <div><span className="font-medium">Registered:</span> {new Date(user.created_at).toLocaleDateString()}</div>
        </div>
      </CardContent>
    </Card>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Users</h2>
      </div>

      {pendingUsers.length > 0 && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-3 text-yellow-600 dark:text-yellow-400">
            Pending Approval ({pendingUsers.length})
          </h3>
          <div className="grid gap-3">
            {pendingUsers.map(renderUser)}
          </div>
        </div>
      )}

      {activeUsers.length > 0 && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-3">Active Users ({activeUsers.length})</h3>
          <div className="grid gap-3">
            {activeUsers.map(renderUser)}
          </div>
        </div>
      )}

      {inactiveUsers.length > 0 && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-3 text-muted-foreground">Inactive ({inactiveUsers.length})</h3>
          <div className="grid gap-3">
            {inactiveUsers.map(renderUser)}
          </div>
        </div>
      )}

      {users.length === 0 && (
        <Card>
          <CardContent className="p-12 text-center text-muted-foreground">
            No users found.
          </CardContent>
        </Card>
      )}

      <ConfirmDialog
        open={confirmState.open}
        onOpenChange={(open) => setConfirmState((s) => ({ ...s, open }))}
        title={confirmState.title}
        description={confirmState.description}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={confirmState.onConfirm}
      />
    </div>
  )
}
