import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { Sidebar } from '@/components/Sidebar'
import { useAuthStore } from '@/store/authStore'
import { resetAuthTestMocks } from '@/test/authTestMocks'

describe('Sidebar admin nav group', () => {
  beforeEach(() => {
    resetAuthTestMocks()
    useAuthStore.setState({
      token: 't',
      isAuthenticated: true,
      loading: false,
      user: null,
    })
  })

  it('shows both Research and Admin links for an admin', () => {
    useAuthStore.setState({ user: { id: 1, email: 'a@a.com', role: 'admin' } })
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )
    expect(screen.getByRole('link', { name: /Research/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Admin/i })).toBeInTheDocument()
  })

  it('shows only the Research link for a researcher', () => {
    useAuthStore.setState({ user: { id: 2, email: 'r@r.com', role: 'researcher' } })
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )
    expect(screen.getByRole('link', { name: /Research/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Admin$/i })).not.toBeInTheDocument()
  })

  it('shows neither Research nor Admin links for a trainee', () => {
    useAuthStore.setState({ user: { id: 3, email: 't@t.com', role: 'trainee' } })
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )
    expect(screen.queryByRole('link', { name: /Research/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Admin$/i })).not.toBeInTheDocument()
  })
})
