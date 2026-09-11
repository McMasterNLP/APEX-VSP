import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminSessionsTable } from './AdminSessionsTable'
import { fetchAdminSessions } from '@/api/admin.api'
import { fetchSessionEvaluationStatuses } from '@/api/research.api'

vi.mock('@/api/admin.api', () => ({
  fetchAdminSessions: vi.fn(),
}))

vi.mock('@/api/research.api', () => ({
  fetchSessionEvaluationStatuses: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchAdminSessions)
const mockedFetchStatuses = vi.mocked(fetchSessionEvaluationStatuses)

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
    mockedFetchStatuses.mockReset()
    mockedFetchStatuses.mockResolvedValue([])
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

  it('does not fetch evaluation statuses when showEvaluationStatus is off', async () => {
    mockedFetch.mockResolvedValue({
      sessions: [session({ id: 1 })],
      total: 1,
      skip: 0,
      limit: 50,
    } as never)
    render(<AdminSessionsTable onRowClick={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument()
    })
    expect(mockedFetchStatuses).not.toHaveBeenCalled()
    expect(screen.queryByText(/Evaluation status/i)).not.toBeInTheDocument()
  })

  it('shows a status chip per row and sorts by rank then recency when enabled', async () => {
    mockedFetch.mockResolvedValue({
      sessions: [
        session({ id: 1, started_at: '2024-01-01T00:00:00Z' }), // no runs -> "No runs yet"
        session({ id: 2, started_at: '2024-01-03T00:00:00Z' }), // draft, not locked -> "In review"
        session({ id: 3, started_at: '2024-01-02T00:00:00Z' }), // complete -> "Locked"
        session({ id: 4, started_at: '2024-01-04T00:00:00Z' }), // has run, no set -> "Needs review"
        session({ id: 5, started_at: '2024-01-05T00:00:00Z' }), // has run, no set, more recent
      ],
      total: 5,
      skip: 0,
      limit: 50,
    } as never)
    mockedFetchStatuses.mockResolvedValue([
      { session_id: 1, has_saved_runs: false, latest_annotation_set_status: null, latest_annotation_set_locked: null },
      { session_id: 2, has_saved_runs: true, latest_annotation_set_status: 'in_review', latest_annotation_set_locked: false },
      { session_id: 3, has_saved_runs: true, latest_annotation_set_status: 'complete', latest_annotation_set_locked: true },
      { session_id: 4, has_saved_runs: true, latest_annotation_set_status: null, latest_annotation_set_locked: null },
      { session_id: 5, has_saved_runs: true, latest_annotation_set_status: null, latest_annotation_set_locked: null },
    ])

    render(<AdminSessionsTable onRowClick={vi.fn()} showEvaluationStatus />)

    await waitFor(() => {
      expect(mockedFetchStatuses).toHaveBeenCalledWith([1, 2, 3, 4, 5])
    })

    // Wait for the fully-settled sort (statuses arrive one render after the session
    // rows), asserting order and per-row chip text together so a stale intermediate
    // render can't satisfy a looser check.
    await waitFor(() => {
      const rows = screen.getAllByRole('row').slice(1) // drop header row
      const idsInOrder = rows.map((row) => row.querySelector('td')?.textContent)
      // Needs review (5 is more recent than 4) > In review > No runs yet > Locked
      expect(idsInOrder).toEqual(['5', '4', '2', '1', '3'])
    })
    expect(screen.getByText('Locked')).toBeInTheDocument()
    expect(screen.getByText('In review')).toBeInTheDocument()
    expect(screen.getByText('No runs yet')).toBeInTheDocument()
    expect(screen.getAllByText('Needs review').length).toBe(2)
  })
})
