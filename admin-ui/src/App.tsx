import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import { Toaster } from 'sonner'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import ServicesPage from './pages/ServicesPage'
import ApiKeysPage from './pages/ApiKeysPage'
import HealthPage from './pages/HealthPage'
import PlaygroundPage from './pages/PlaygroundPage'
import UsersPage from './pages/UsersPage'
import SettingsPage from './pages/SettingsPage'
import Layout from './components/layout/Layout'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />
}

function SuperadminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" />
  if (!user?.is_superadmin) return <Navigate to="/" />
  return <>{children}</>
}

export default function App() {
  return (
    <>
      <Toaster richColors position="top-right" />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/*"
          element={
            <PrivateRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/services" element={<ServicesPage />} />
                  <Route path="/api-keys" element={<ApiKeysPage />} />
                  <Route path="/health" element={<HealthPage />} />
                  <Route path="/playground" element={<PlaygroundPage />} />
                  <Route path="/users" element={<SuperadminRoute><UsersPage /></SuperadminRoute>} />
                  <Route path="/settings" element={<SuperadminRoute><SettingsPage /></SuperadminRoute>} />
                </Routes>
              </Layout>
            </PrivateRoute>
          }
        />
      </Routes>
    </>
  )
}
