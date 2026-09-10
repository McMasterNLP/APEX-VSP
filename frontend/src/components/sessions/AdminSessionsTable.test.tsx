import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminSessionsTable } from './AdminSessionsTable'
import { fetchAdminSessions } from '@/api/admin.api'

vi.mock('@/api/admin.api', () => ({
  fetchAdminSessions: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchAdminSessions)

const session = (overrides: Partial<Record<string, unknown>> = {}) => ({
  id: 1,
  user_id: 7,
  user_full_name: 'Jane Doe',
  user_email: 'jane@test.com',
  case_id: 3,
  state: 'completed',
  started_at: '2024-01-01T00:00:00Z',
  turns: [],
  ...overrides,
})

describe('AdminSessionsTable', () => {
  beforeEach(() => {
    mockedFetch.mockReset()
  })

  it('shows a loading state, then rows once data resolves', async () => {
    mockedFetch.mockResolvedValue({
      sessions: [session()],
      total: 1,
      skip: 0,
      limit: 50,
    } as never)

    render(<AdminSessionsTable onRowClick={vi.fn()} />)

    expect(screen.getByText(/Loading sessions/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    })
    expect(mockedFetch).toHaveBeenCalledWith(0, 50)
  })

  it('shows an empty state when there are no sessions', async () => {
    mockedFetch.mockResolvedValue({ sessions: [], total: 0, skip: 0, limit: 50 } as never)
    render(<AdminSessionsTable onRowClick={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText(/No sessions found/i)).toBeInTheDocument()
    })
  })

  it('shows an error state on fetch failure', async () => {
    mockedFetch.mockRejectedValue(new Error('boom'))
    render(<AdminSessionsTable onRowClick={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText(/Failed to load session logs/i)).toBeInTheDocument()
    })
  })

  it('invokes onRowClick with the clicked session on row click', async () => {
    mockedFetch.mockResolvedValue({
      sessions: [session({ id: 42 })],
      total: 1,
      skip: 0,
      limit: 50,
    } as never)
    const onRowClick = vi.fn()
    render(<AdminSessionsTable onRowClick={onRowClick} />)

    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('42'))
    expect(onRowClick).toHaveBeenCalledWith(expect.objectContaining({ id: 42 }))
  })
})
