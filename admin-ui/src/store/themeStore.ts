import { create } from 'zustand'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  toggle: () => void
}

const getInitialTheme = (): Theme => {
  const saved = localStorage.getItem('theme') as Theme
  if (saved) return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: getInitialTheme(),
  toggle: () => {
    const next = get().theme === 'light' ? 'dark' : 'light'
    localStorage.setItem('theme', next)
    document.documentElement.classList.toggle('dark', next === 'dark')
    set({ theme: next })
  },
}))

// Initialize on load
const theme = getInitialTheme()
document.documentElement.classList.toggle('dark', theme === 'dark')
