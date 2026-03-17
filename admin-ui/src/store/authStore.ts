import { create } from 'zustand'
import type { UserRead } from '@/api/auth'

interface AuthState {
  token: string | null
  user: UserRead | null
  isAuthenticated: boolean
  login: (token: string, user: UserRead) => void
  logout: () => void
  setUser: (user: UserRead) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  user: (() => {
    try {
      const raw = localStorage.getItem('user')
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })(),
  isAuthenticated: !!localStorage.getItem('token'),
  login: (token: string, user: UserRead) => {
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
    set({ token, user, isAuthenticated: true })
  },
  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    set({ token: null, user: null, isAuthenticated: false })
  },
  setUser: (user: UserRead) => {
    localStorage.setItem('user', JSON.stringify(user))
    set({ user })
  },
}))
