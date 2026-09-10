import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ResearchEvaluationSessionPage } from './ResearchEvaluationSessionPage'
import { fetchAdminSessionDetail } from '@/api/admin.api'
import { useAuthStore } from '@/store/authStore'
import { resetAuthTestMocks } from '@/test/authTestMocks'

vi.mock('@/api/admin.api', async () => {
  const actual = await vi.importActual<typeof import('@/api/admin.api')>('@/api/admin.api')
  return {
    ...actual,
    fetchAdminSessionDetail: vi.fn(),
  }
})

vi.mock('@/components/admin/research/ResearchEvaluationPanel', () => ({
  ResearchEvaluationPanel: ({ sessionId, sessionState }: { sessionId: number; sessionState: string }) => (
    <div>Evaluation panel for session {sessionId} ({sessionState})</div>
  ),
}))

const mockedFetchDetail = vi.mocked(fetchAdminSessionDetail)

describe('ResearchEvaluationSessionPage', () => {
  beforeEach(() => {
    resetAuthTestMocks()
    mockedFetchDetail.mockReset()
    useAuthStore.setState({
      token: 't',
      isAuthenticated: true,
      loading: false,
      user: { id: 1, email: 'r@r.com', role: 'researcher' },
    })
  })

  it('loads session detail and renders the evaluation panel', async () => {
    mockedFetchDetail.mockResolvedValue({
      session: {
        id: 42,
        user_id: 7,
        user_full_name: 'Jane Doe',
        user_email: 'jane@test.com',
        case_id: 3,
        state: 'completed',
        started_at: '2024-01-01T00:00:00Z',
        turns: [
          { id: 1, turn_number: 1, role: 'user', text: 'Hello', timestamp: '2024-01-01T00:00:00Z' },
        ],
      },
      feedback: null,
      metrics_timeline: [],
    } as never)

    render(
      <MemoryRouter initialEntries={['/research/evaluate/42']}>
        <Routes>
          <Route path="/research/evaluate/:sessionId" element={<ResearchEvaluationSessionPage />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText(/Loading session/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText(/Session 42 – Evaluation Workspace/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/Evaluation panel for session 42 \(completed\)/i)).toBeInTheDocument()
    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(mockedFetchDetail).toHaveBeenCalledWith('42')
  })

  it('shows an error message when the fetch fails', async () => {
    mockedFetchDetail.mockRejectedValue(new Error('boom'))

    render(
      <MemoryRouter initialEntries={['/research/evaluate/99']}>
        <Routes>
          <Route path="/research/evaluate/:sessionId" element={<ResearchEvaluationSessionPage />} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText(/Failed to load session detail/i)).toBeInTheDocument()
    })
  })
})
