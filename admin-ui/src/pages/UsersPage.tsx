import { useEffect, useState, useMemo } from 'react'
import { fetchUsers, approveUser, rejectUser, deleteUser, updateUser } from '@/api/users'
import type { UserRead } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import {
  CheckCircle, XCircle, Trash2, Shield, ShieldOff,
  Search, ChevronLeft, ChevronRight,
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

type FilterTab = 'all' | 'pending' | 'approved' | 'superadmin' | 'inactive'

export default function UsersPage() {
  const currentUser = useAuthStore((s) => s.user)
  const [users, setUsers] = useState<UserRead[]>([])
  const [confirmState, setConfirmState] = useState<{
    open: boolean; title: string; description: string; onConfirm: () => void
  }>({ open: false, title: '', description: '', onConfirm: () => {} })

  const [search, setSearch] = useState('')
  const [tab, setTab] = useState<FilterTab>('all')
  const [page, setPage] = useState(0)

  const load = () => {
    fetchUsers().then((r) => setUsers(r.data)).catch(() => toast.error('Failed to load users'))
  }
  useEffect(() => { load() }, [])

  // Reset page on filter/search change
  useEffect(() => { setPage(0) }, [search, tab])

  const handleApprove = async (id: string) => {
    await approveUser(id)
    toast.success('User approved')
    load()
  }

  const handleReject = (id: string, username: string) => {
    setConfirmState({
      open: true,
      title: 'Reject user',
      description: `Reject registration for "${username}"?`,
      onConfirm: async () => {
        try {
          await rejectUser(id)
          toast.success('User rejected')
          load()
        } catch (err: any) {
          toast.error(err.response?.data?.detail || 'Failed to reject user')
        }
      },
    })
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
      description: `Delete "${username}"? All their services, API keys and data will be permanently deleted.`,
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

  // Tab counts
  const counts: Record<FilterTab, number> = useMemo(() => ({
    all: users.length,
    pending: users.filter((u) => !u.is_approved && u.is_active).length,
    approved: users.filter((u) => u.is_approved && u.is_active).length,
    superadmin: users.filter((u) => u.is_superadmin).length,
    inactive: users.filter((u) => !u.is_active).length,
  }), [users])

  // Filter by tab
  const tabFiltered = useMemo(() => {
    switch (tab) {
      case 'pending':   return users.filter((u) => !u.is_approved && u.is_active)
      case 'approved':  return users.filter((u) => u.is_approved && u.is_active)
      case 'superadmin':return users.filter((u) => u.is_superadmin)
      case 'inactive':  return users.filter((u) => !u.is_active)
      default:          return users
    }
  }, [users, tab])

  // Then search
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return tabFiltered
    return tabFiltered.filter(
      (u) =>
        u.username.toLowerCase().includes(q) ||
        (u.email?.toLowerCase().includes(q) ?? false) ||
        (u.display_name?.toLowerCase().includes(q) ?? false)
    )
  }, [tabFiltered, search])

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const pageUsers = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const tabs: { key: FilterTab; label: string }[] = [
    { key: 'all',       label: 'All' },
    { key: 'pending',   label: 'Pending' },
    { key: 'approved',  label: 'Approved' },
    { key: 'superadmin',label: 'Superadmins' },
    { key: 'inactive',  label: 'Inactive' },
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Users</h2>
      </div>

      {/* Filter tabs + search */}
      <div className="flex items-center justify-between gap-4 mb-3 flex-wrap">
        {/* Tabs */}
        <div className="flex items-center gap-0.5 bg-muted/40 rounded-md p-0.5">
          {tabs.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors tabular-nums ${
                tab === key
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {label}
              {counts[key] > 0 && (
                <span className={`ml-1.5 ${tab === key ? 'text-foreground/60' : 'text-muted-foreground/60'}`}>
                  {counts[key]}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="flex items-center gap-2">
          <div className="relative max-w-xs">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by username, email…"
              className="pl-8 h-8 text-sm w-56"
            />
          </div>
          <span className="text-xs text-muted-foreground tabular-nums whitespace-nowrap">
            {filtered.length} {filtered.length === 1 ? 'user' : 'users'}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40 text-left">
                <th className="px-3 py-2 w-6 font-medium text-muted-foreground text-xs uppercase tracking-wide"></th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">User</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">Role</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">Status</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">Registered</th>
                <th className="px-3 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wide text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {pageUsers.map((u) => {
                const isSelf = currentUser?.id === u.id
                const isPending = !u.is_approved && u.is_active
                const isInactive = !u.is_active

                // Status dot color
                const dotColor = isPending
                  ? 'bg-yellow-400'
                  : isInactive
                  ? 'bg-muted-foreground/30'
                  : 'bg-green-500'

                const dotTitle = isPending ? 'Pending approval' : isInactive ? 'Inactive' : 'Active'

                return (
                  <tr key={u.id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                    {/* Status dot */}
                    <td className="px-3 py-2.5">
                      <span
                        className={`inline-block h-2 w-2 rounded-full ${dotColor}`}
                        title={dotTitle}
                      />
                    </td>

                    {/* User identity */}
                    <td className="px-3 py-2.5 max-w-[220px]">
                      <div className="font-medium truncate">
                        {u.display_name || u.username}
                        {isSelf && (
                          <span className="ml-1.5 text-[10px] text-muted-foreground font-normal">(you)</span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">
                        @{u.username}
                        {u.email && <span className="ml-1.5">{u.email}</span>}
                      </div>
                    </td>

                    {/* Role */}
                    <td className="px-3 py-2.5">
                      {u.is_superadmin ? (
                        <span className="flex items-center gap-1 text-xs text-foreground/70">
                          <Shield className="h-3 w-3 shrink-0" />superadmin
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground/50">user</span>
                      )}
                    </td>

                    {/* Approval status */}
                    <td className="px-3 py-2.5">
                      {isPending && (
                        <span className="text-xs text-yellow-600 dark:text-yellow-400 font-medium">pending</span>
                      )}
                      {u.is_approved && u.is_active && (
                        <span className="text-xs text-muted-foreground">approved</span>
                      )}
                      {isInactive && (
                        <span className="text-xs text-muted-foreground/50">inactive</span>
                      )}
                    </td>

                    {/* Registered */}
                    <td className="px-3 py-2.5">
                      <span
                        className="text-xs text-muted-foreground whitespace-nowrap"
                        title={new Date(u.created_at).toLocaleString()}
                      >
                        {relativeTime(u.created_at)}
                      </span>
                    </td>

                    {/* Actions */}
                    <td className="px-3 py-2.5">
                      <div className="flex items-center justify-end gap-0.5">
                        {/* Approve — shown for pending or inactive */}
                        {(isPending || isInactive) && (
                          <Button
                            variant="ghost" size="icon" className="h-7 w-7 hover:text-green-500"
                            onClick={() => handleApprove(u.id)}
                            title={isInactive ? 'Reactivate' : 'Approve'}
                          >
                            <CheckCircle className="h-3.5 w-3.5" />
                          </Button>
                        )}

                        {/* Reject — shown for pending only */}
                        {isPending && (
                          <Button
                            variant="ghost" size="icon" className="h-7 w-7 hover:text-destructive"
                            onClick={() => handleReject(u.id, u.username)}
                            title="Reject"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                          </Button>
                        )}

                        {/* Toggle superadmin — only for approved active users, not self */}
                        {u.is_approved && u.is_active && !isSelf && (
                          <Button
                            variant="ghost" size="icon" className="h-7 w-7"
                            onClick={() => handleToggleSuperadmin(u)}
                            title={u.is_superadmin ? 'Remove superadmin' : 'Grant superadmin'}
                          >
                            {u.is_superadmin
                              ? <ShieldOff className="h-3.5 w-3.5 text-muted-foreground" />
                              : <Shield className="h-3.5 w-3.5 text-muted-foreground" />
                            }
                          </Button>
                        )}

                        {/* Delete — disabled for self */}
                        <Button
                          variant="ghost" size="icon" className="h-7 w-7 hover:text-destructive"
                          onClick={() => !isSelf && handleDelete(u.id, u.username)}
                          disabled={isSelf}
                          title={isSelf ? 'Cannot delete yourself' : 'Delete user'}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}

              {pageUsers.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-12 text-center text-sm text-muted-foreground">
                    {search ? 'No users match your search.' : 'No users found.'}
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

      <ConfirmDialog
        open={confirmState.open}
        onOpenChange={(open) => setConfirmState((s) => ({ ...s, open }))}
        title={confirmState.title}
        description={confirmState.description}
        confirmLabel="Confirm"
        variant="destructive"
        onConfirm={confirmState.onConfirm}
      />
    </div>
  )
}
