import { vi } from 'vitest'
import type { Session } from '@supabase/supabase-js'

export const mockSignOut = vi.fn().mockResolvedValue({ error: null })

export const mockGetSession = vi.fn().mockResolvedValue({
  data: { session: null as Session | null },
})

export const mockOnAuthStateChange = vi.fn(
  (cb: (event: string, session: Session | null) => void) => {
    void cb
    return {
      data: { subscription: { unsubscribe: vi.fn() } },
    }
  }
)

/** Mocked `api.get` used by {@link refreshProfile} via dynamic import. */
export const apiGet = vi.fn()
export const apiPost = vi.fn()

export function resetAuthTestMocks() {
  mockSignOut.mockClear()
  mockSignOut.mockResolvedValue({ error: null })
  mockGetSession.mockClear()
  mockGetSession.mockResolvedValue({ data: { session: null } })
  mockOnAuthStateChange.mockClear()
  mockOnAuthStateChange.mockImplementation(
    (cb: (event: string, session: Session | null) => void) => {
      void cb
      return { data: { subscription: { unsubscribe: vi.fn() } } }
    }
  )
  apiGet.mockReset()
  apiPost.mockReset()
}
