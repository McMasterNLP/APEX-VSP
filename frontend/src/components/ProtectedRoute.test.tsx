import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { useAuthStore } from '@/store/authStore'
import { apiGet, resetAuthTestMocks } from '@/test/authTestMocks'

describe('ProtectedRoute', () => {
  beforeEach(() => {
    resetAuthTestMocks()
    useAuthStore.setState({
      token: null,
      user: null,
      isAuthenticated: false,
      loading: false,
    })
  })

  it('shows loading while auth is initializing', () => {
    useAuthStore.setState({ loading: true })
    render(
      <MemoryRouter initialEntries={['/app']}>
        <Routes>
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <div>Inside</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('redirects to /login when not authenticated', () => {
    render(
      <MemoryRouter initialEntries={['/app']}>
        <Routes>
          <Route path="/login" element={<div>Login page</div>} />
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <div>Inside</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Inside')).not.toBeInTheDocument()
  })

  it('renders children when authenticated', () => {
    useAuthStore.setState({
      loading: false,
      isAuthenticated: true,
      token: 't',
      user: { id: 1, email: 'a@a.com', role: 'trainee' },
    })
    render(
      <MemoryRouter initialEntries={['/app']}>
        <Routes>
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <div>Inside</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('Inside')).toBeInTheDocument()
  })

  it('redirects trainee away from admin-only route when role does not match', () => {
    useAuthStore.setState({
      loading: false,
      isAuthenticated: true,
      token: 't',
      user: { id: 1, email: 't@t.com', role: 'trainee' },
    })
    render(
      <MemoryRouter initialEntries={['/admin-only']}>
        <Routes>
          <Route path="/dashboard" element={<div>Dashboard</div>} />
          <Route
            path="/admin-only"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <div>Admin</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.queryByText('Admin')).not.toBeInTheDocument()
  })

  it('allows a researcher into a research-gated route', () => {
    useAuthStore.setState({
      loading: false,
      isAuthenticated: true,
      token: 't',
      user: { id: 1, email: 'r@r.com', role: 'researcher' },
    })
    render(
      <MemoryRouter initialEntries={['/research']}>
        <Routes>
          <Route path="/dashboard" element={<div>Dashboard</div>} />
          <Route
            path="/research"
            element={
              <ProtectedRoute allowedRoles={['admin', 'researcher']}>
                <div>Research</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('Research')).toBeInTheDocument()
  })

  it('redirects a researcher away from an admin-only route', () => {
    useAuthStore.setState({
      loading: false,
      isAuthenticated: true,
      token: 't',
      user: { id: 1, email: 'r@r.com', role: 'researcher' },
    })
    render(
      <MemoryRouter initialEntries={['/admin-only']}>
        <Routes>
          <Route path="/dashboard" element={<div>Dashboard</div>} />
          <Route
            path="/admin-only"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <div>Admin</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.queryByText('Admin')).not.toBeInTheDocument()
  })

  it('calls refreshProfile when authenticated but user is missing', async () => {
    useAuthStore.setState({
      loading: false,
      isAuthenticated: true,
      token: 't',
      user: null,
    })
    apiGet.mockResolvedValue({
      data: { id: 1, email: 'lazy@x.com', role: 'trainee' as const },
    })

    render(
      <MemoryRouter initialEntries={['/app']}>
        <Routes>
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <div>Inside</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(apiGet).toHaveBeenCalledWith('/v1/auth/me')
    })
  })
})
