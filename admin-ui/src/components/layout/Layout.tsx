import { Link, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useThemeStore } from '@/store/themeStore'
import { LayoutDashboard, Server, Key, LogOut, Moon, Sun, HeartPulse, Users, Settings, FlaskConical, Gauge } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const { logout, user } = useAuthStore()
  const { theme, toggle } = useThemeStore()

  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/services', label: 'Services', icon: Server },
    { path: '/api-keys', label: 'API Keys', icon: Key },
    { path: '/health', label: 'Health Check', icon: HeartPulse },
    { path: '/playground', label: 'Playground', icon: FlaskConical },
    ...(user?.is_superadmin ? [
      { path: '/load-tests', label: 'Load Tests', icon: Gauge },
      { path: '/users', label: 'Users', icon: Users },
      { path: '/settings', label: 'Settings', icon: Settings },
    ] : []),
  ]

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 border-r bg-card flex flex-col">
        <div className="p-6">
          <h1 className="text-xl font-bold">ProxyML</h1>
          <p className="text-xs text-muted-foreground mt-1">Admin Panel</p>
        </div>
        <nav className="flex-1 px-3 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                location.pathname === item.path
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="p-3 border-t space-y-2">
          {user && (
            <div className="px-3 py-1 text-sm">
              <div className="font-medium truncate">{user.display_name || user.username}</div>
              <div className="text-xs text-muted-foreground truncate">@{user.username}</div>
            </div>
          )}
          <Button variant="ghost" size="sm" className="w-full justify-start gap-3" onClick={toggle}>
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </Button>
          <Button variant="ghost" size="sm" className="w-full justify-start gap-3 text-destructive" onClick={logout}>
            <LogOut className="h-4 w-4" />
            Logout
          </Button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">{children}</div>
      </main>
    </div>
  )
}
