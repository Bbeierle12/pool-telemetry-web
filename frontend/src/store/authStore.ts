import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Profile } from '../types'

interface AuthState {
  profile: Profile | null
  token: string | null
  isAuthenticated: boolean
  login: (token: string, profile: Profile) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      profile: null,
      token: null,
      isAuthenticated: false,

      login: (token: string, profile: Profile) => {
        set({
          token,
          profile,
          isAuthenticated: true,
        })
      },

      logout: () => {
        set({
          token: null,
          profile: null,
          isAuthenticated: false,
        })
      },
    }),
    {
      name: 'pool-telemetry-auth',
    }
  )
)
