import { create } from 'zustand'
import axios from 'axios'
import { supabase } from '@/lib/supabase'
import type { Session } from '@supabase/supabase-js'

export type Role = 'trainee' | 'admin' | 'researcher'

export interface AppUser {
  id: number
  email: string
  role: Role
  full_name?: string
  gender?: string
  race?: string
  year_of_study?: string
}

interface AuthState {
  token: string | null
  user: AppUser | null
  isAuthenticated: boolean
  loading: boolean
  setSession: (session: Session | null) => void
  setUser: (user: AppUser | null) => void
  logout: () => Promise<void>
  refreshProfile: () => Promise<void>
  initialize: () => Promise<void>
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  loading: true,

  setSession: (session) => {
    const token = session?.access_token ?? null
    set({
      token,
      isAuthenticated: !!token,
      ...(token ? {} : { user: null }),
    })
  },

  setUser: (user) => {
    set({ user })
  },

  logout: async () => {
    await supabase.auth.signOut()
    set({ token: null, user: null, isAuthenticated: false })
  },

  refreshProfile: async () => {
    const token = get().token
    if (!token) {
      set({ user: null })
      return
    }
    try {
      const { default: api } = await import('@/api/client')
      const { data: profile } = await api.get('/v1/auth/me')
      set({ user: profile, isAuthenticated: true })
    } catch (err) {
      if (
        axios.isAxiosError(err) &&
        (err.response?.status === 401 || err.response?.status === 403)
      ) {
        await get().logout()
        set({ token: null, user: null, isAuthenticated: false })
      } else {
        set({ user: null, isAuthenticated: true })
      }
    }
  },

  initialize: async () => {
    set({ loading: true })

    const { data } = await supabase.auth.getSession()
    const session = data.session
    const accessToken = session?.access_token ?? null

    set({
      token: accessToken,
      user: null,
      isAuthenticated: false,
    })

    if (accessToken) {
      await get().refreshProfile()
    }

    set({ loading: false })

    supabase.auth.onAuthStateChange(async (_event, nextSession) => {
      const token = nextSession?.access_token ?? null
      set({
        token,
        isAuthenticated: !!token,
        ...(token ? {} : { user: null }),
      })
      if (token) {
        await get().refreshProfile()
      }
    })
  },
}))
