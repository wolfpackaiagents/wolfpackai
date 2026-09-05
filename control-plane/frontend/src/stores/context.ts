import { create } from 'zustand'

type ScopeState = {
  environmentId: string
  registrationId: string
  range: string
  setEnvironment: (id: string) => void
  setRegistration: (id: string) => void
  setRange: (range: string) => void
}

export const useScopeStore = create<ScopeState>((set) => ({
  environmentId: '', registrationId: '', range: '24h',
  setEnvironment: (environmentId) => set({ environmentId, registrationId: '' }),
  setRegistration: (registrationId) => set({ registrationId }),
  setRange: (range) => set({ range }),
}))
