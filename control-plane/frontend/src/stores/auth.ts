import { create } from 'zustand'

interface AuthState {
  apiKey: string
  setApiKey: (key: string) => void
  clear: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  apiKey: localStorage.getItem('wolfpack_api_key') || '',
  setApiKey: (key) => {
    localStorage.setItem('wolfpack_api_key', key)
    set({ apiKey: key })
  },
  clear: () => {
    localStorage.removeItem('wolfpack_api_key')
    set({ apiKey: '' })
  },
}))