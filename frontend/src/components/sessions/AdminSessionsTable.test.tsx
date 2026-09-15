import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminSessionsTable, type AdminSessionsTableProps } from './AdminSessionsTable'
import { fetchAdminSessions, fetchSessionFilterOptions } from '@/api/admin.api'
import { fetchSessionEvaluationStatuses } from '@/api/research.api'

vi.mock('@/api/admin.api', () => ({
  fetchAdminSessions: vi.fn(),
  fetchSessionFilterOptions: vi.fn(),
}))

vi.mock('@/api/research.api', () => ({
  fetchSessionEvaluationStatuses: vi.fn(),
}))

const mockedFetch = vi.mocked(fetchAdminSessions)
const mockedFetchStatuses = vi.mocked(fetchSessionEvaluationStatuses)
const mockedFetchFilterOptions = vi.mocked(fetchSessionFilterOptions)

const EMPTY_FILTER_OPTIONS = {
  cases: [],
  patient_plugins: [],
  evaluator_plugins: [],
  evaluators: [],
}

const session = (overrides: Partial<Record<string, unknown>> = {}) => ({
  id: 1,
  user_id: 7,
  user_full_name: 'Jane Doe',
  user_email: 'jane@test.com',
  case_id: 3,
  case_title: null,
  state: 'completed',
  started_at: '2024-01-01T00:00:00Z',
  turns: [],
  ...overrides,
})

/** Renders with the router context `useSearchParams` (filter-in-URL) requires. */
function renderTable(props: AdminSessionsTableProps) {
  return render(
    <MemoryRouter>
      <AdminSessionsTable {...props} />
    </MemoryRouter>
  )
}

describe('AdminSessionsTable', () => {
  beforeEach(() => {
    mockedFetch.mockReset()
    mockedFetchStatuses.mockReset()
    mockedFetchStatuses.mockResolvedValue([])
    mockedFetchFilterOptions.mockReset()
    mockedFetchFilterOptions.mockResolvedValue(EMPTY_FILTER_OPTIONS as never)
  })

  it('shows a loading state, then rows once data resolves', async () => {
    mockedFetch.mockResolvedValue({
      sessions: [session()],
      total: 1,
      skip: 0,
      limit: 50,
    } as never)

    renderTable({ onRowClick: vi.fn() })

    expect(screen.getByText(/Loading sessions/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    })
    expect(mockedFetch).toHaveBeenCalledWith(0, 50, {})
  })

  it('shows an empty state when there are no sessions', async () => {
    mockedFetch.mockResolvedValue({ sessions: [], total: 0, skip: 0, limit: 50 } as never)
    renderTable({ onRowClick: vi.fn() })
    await waitFor(() => {
      expect(screen.getByText(/No sessions found/i)).toBeInTheDocument()
    })
  })

  it('shows an error state on fetch failure', async () => {
    mockedFetch.mockRejectedValue(new Error('boom'))
    renderTable({ onRowClick: vi.fn() })
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
    renderTable({ onRowClick })

    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('42'))
    expect(onRowClick).toHaveBeenCalledWith(expect.objectContaining({ id: 42 }))
  })

  it('shows the case title when present, falling back to a Case # label', async () => {
    mockedFetch.mockResolvedValue({
      sessions: [
        session({ id: 1, case_id: 3, case_title: 'Breaking Bad News' }),
        session({ id: 2, case_id: 9, case_title: null }),
      ],
      total: 2,
      skip: 0,
      limit: 50,
    } as never)
    renderTable({ onRowClick: vi.fn() })
    await waitFor(() => {
      expect(screen.getByText('Breaking Bad News')).toBeInTheDocument()
    })
    expect(screen.getByText('Case #9')).toBeInTheDocument()
  })

  it('does not fetch evaluation statuses when showEvaluationStatus is off', async () => {
    mockedFetch.mockResolvedValue({
      sessions: [session({ id: 1 })],
      total: 1,
      skip: 0,
      limit: 50,
    } as never)
    renderTable({ onRowClick: vi.fn() })
    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument()
    })
    expect(mockedFetchStatuses).not.toHaveBeenCalled()
    expect(screen.queryByText(/Evaluation status/i)).not.toBeInTheDocument()
    // Evaluator-only filters are also hidden outside the evaluation workflow.
    expect(screen.queryByLabelText('Evaluator')).not.toBeInTheDocument()
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

    renderTable({ onRowClick: vi.fn(), showEvaluationStatus: true })

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
    // Scoped to table cells: the Evaluation status filter dropdown now has options
    // with this same text ("Locked", "In review", etc.), so a bare getByText is
    // ambiguous once that dropdown is present.
    expect(screen.getByRole('cell', { name: 'Locked' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'In review' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'No runs yet' })).toBeInTheDocument()
    expect(screen.getAllByRole('cell', { name: 'Needs review' }).length).toBe(2)
  })

  it('shows a pagination summary and pages forward and back using skip', async () => {
    mockedFetch.mockResolvedValueOnce({
      sessions: [session({ id: 1 })],
      total: 120,
      skip: 0,
      limit: 50,
    } as never)

    renderTable({ onRowClick: vi.fn() })
    await waitFor(() => {
      expect(screen.getByText('Showing 1–50 of 120')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()

    mockedFetch.mockResolvedValueOnce({
      sessions: [session({ id: 2 })],
      total: 120,
      skip: 50,
      limit: 50,
    } as never)
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledWith(50, 50, {}))
    await waitFor(() => {
      expect(screen.getByText('Showing 51–100 of 120')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Previous' })).not.toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).not.toBeDisabled()

    mockedFetch.mockResolvedValueOnce({
      sessions: [session({ id: 1 })],
      total: 120,
      skip: 0,
      limit: 50,
    } as never)
    fireEvent.click(screen.getByRole('button', { name: 'Previous' }))
    await waitFor(() => expect(mockedFetch).toHaveBeenLastCalledWith(0, 50, {}))
  })

  it('filters by user id and resets to the first page', async () => {
    mockedFetch.mockResolvedValue({
      sessions: [session({ id: 1 })],
      total: 1,
      skip: 0,
      limit: 50,
    } as never)

    renderTable({ onRowClick: vi.fn() })
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledWith(0, 50, {}))

    fireEvent.change(screen.getByLabelText('User ID'), {
      target: { value: '7' },
    })
    await waitFor(() =>
      expect(mockedFetch).toHaveBeenLastCalledWith(0, 50, { userId: 7 })
    )
    expect(screen.getByRole('button', { name: 'Clear all' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Clear all' }))
    await waitFor(() => expect(mockedFetch).toHaveBeenLastCalledWith(0, 50, {}))
  })

  it('filters by case using the case dropdown, populated from filter options', async () => {
    mockedFetchFilterOptions.mockResolvedValue({
      ...EMPTY_FILTER_OPTIONS,
      cases: [{ id: 3, title: 'Breaking Bad News' }],
    } as never)
    mockedFetch.mockResolvedValue({
      sessions: [session({ id: 1 })],
      total: 1,
      skip: 0,
      limit: 50,
    } as never)

    renderTable({ onRowClick: vi.fn() })
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledWith(0, 50, {}))
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Breaking Bad News' })).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Case'), { target: { value: '3' } })
    await waitFor(() =>
      expect(mockedFetch).toHaveBeenLastCalledWith(0, 50, { caseId: 3 })
    )
    expect(screen.getByText('Case: Breaking Bad News')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Remove filter: Case/i }))
    await waitFor(() => expect(mockedFetch).toHaveBeenLastCalledWith(0, 50, {}))
  })

  it('shows and applies the evaluation-status and evaluator filters only when enabled', async () => {
    mockedFetchFilterOptions.mockResolvedValue({
      ...EMPTY_FILTER_OPTIONS,
      evaluators: [{ id: 5, label: 'Dr. Reviewer' }],
    } as never)
    mockedFetch.mockResolvedValue({
      sessions: [session({ id: 1 })],
      total: 1,
      skip: 0,
      limit: 50,
    } as never)

    renderTable({ onRowClick: vi.fn(), showEvaluationStatus: true })
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledWith(0, 50, {}))

    fireEvent.change(screen.getByLabelText('Evaluation status'), {
      target: { value: 'needs_review' },
    })
    await waitFor(() =>
      expect(mockedFetch).toHaveBeenLastCalledWith(0, 50, { evaluationStatus: 'needs_review' })
    )

    fireEvent.change(screen.getByLabelText('Evaluator'), { target: { value: '5' } })
    await waitFor(() =>
      expect(mockedFetch).toHaveBeenLastCalledWith(0, 50, {
        evaluationStatus: 'needs_review',
        evaluatorUserId: 5,
      })
    )
    expect(screen.getByText('Status: Needs review')).toBeInTheDocument()
    expect(screen.getByText('Evaluator: Dr. Reviewer')).toBeInTheDocument()
  })
})
