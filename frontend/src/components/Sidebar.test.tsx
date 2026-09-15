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

  it('shows Research sub-links (Analytics, Sessions) and the Admin link for an admin', () => {
    useAuthStore.setState({ user: { id: 1, email: 'a@a.com', role: 'admin' } })
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )
    const hrefs = screen.getAllByRole('link').map((el) => el.getAttribute('href'))
    expect(hrefs).toContain('/research?tab=analytics')
    expect(hrefs).toContain('/research?tab=evaluate')
    expect(screen.getByRole('link', { name: /^Admin$/i })).toBeInTheDocument()
  })

  it('shows Research sub-links but no Admin link for a researcher', () => {
    useAuthStore.setState({ user: { id: 2, email: 'r@r.com', role: 'researcher' } })
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )
    const hrefs = screen.getAllByRole('link').map((el) => el.getAttribute('href'))
    expect(hrefs).toContain('/research?tab=analytics')
    expect(hrefs).toContain('/research?tab=evaluate')
    expect(screen.queryByRole('link', { name: /^Admin$/i })).not.toBeInTheDocument()
  })

  it('shows neither the Research sub-links nor the Admin link for a trainee', () => {
    useAuthStore.setState({ user: { id: 3, email: 't@t.com', role: 'trainee' } })
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    )
    const hrefs = screen.getAllByRole('link').map((el) => el.getAttribute('href'))
    expect(hrefs).not.toContain('/research?tab=analytics')
    expect(hrefs).not.toContain('/research?tab=evaluate')
    expect(screen.queryByRole('link', { name: /^Admin$/i })).not.toBeInTheDocument()
  })
})
