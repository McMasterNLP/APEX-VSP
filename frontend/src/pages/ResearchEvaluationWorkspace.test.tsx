import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Navigate, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ResearchEvaluationWorkspace } from './ResearchEvaluationWorkspace'
import { OverviewTab } from './research-workspace/OverviewTab'
import { RunCompareTab } from './research-workspace/RunCompareTab'
import { SavedRunsTab } from './research-workspace/SavedRunsTab'
import { ReviewAnnotateTab } from './research-workspace/ReviewAnnotateTab'
import { ExportTab } from './research-workspace/ExportTab'
import { fetchAdminSessionDetail } from '@/api/admin.api'
import {
  fetchResearchEvaluatorDescriptors,
  fetchSavedResearchRuns,
} from '@/api/research.api'
import { useAuthStore } from '@/store/authStore'
import { resetAuthTestMocks } from '@/test/authTestMocks'

vi.mock('@/api/admin.api', async () => {
  const actual = await vi.importActual<typeof import('@/api/admin.api')>('@/api/admin.api')
  return {
    ...actual,
    fetchAdminSessionDetail: vi.fn(),
  }
})

vi.mock('@/api/research.api', () => ({
  createResearchAnnotationSet: vi.fn(),
  downloadResearchEvaluationExport: vi.fn(),
  fetchSavedResearchRun: vi.fn(),
  fetchSavedResearchRuns: vi.fn(),
  fetchResearchEvaluatorDescriptors: vi.fn(),
  getResearchApiMessage: (_error: unknown, fallback: string) => fallback,
  runResearchEvaluations: vi.fn(),
  saveResearchEvaluationRun: vi.fn(),
}))

const mockedFetchDetail = vi.mocked(fetchAdminSessionDetail)
const mockedDescriptors = vi.mocked(fetchResearchEvaluatorDescriptors)
const mockedSavedRuns = vi.mocked(fetchSavedResearchRuns)

function renderWorkspace(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/research/evaluate/:sessionId" element={<ResearchEvaluationWorkspace />}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<OverviewTab />} />
          <Route path="run" element={<RunCompareTab />} />
          <Route path="runs" element={<SavedRunsTab />} />
          <Route path="review" element={<ReviewAnnotateTab />} />
          <Route path="export" element={<ExportTab />} />
        </Route>
      </Routes>
    </MemoryRouter>
  )
}

describe('ResearchEvaluationWorkspace', () => {
  beforeEach(() => {
    resetAuthTestMocks()
    vi.clearAllMocks()
    useAuthStore.setState({
      token: 't',
      isAuthenticated: true,
      loading: false,
      user: { id: 1, email: 'r@r.com', role: 'researcher' },
    })
    mockedDescriptors.mockResolvedValue({ schema_version: '1.0', evaluators: [] })
    mockedSavedRuns.mockResolvedValue([
      {
        run_uuid: 'run-1',
        item1_run_id: 'r1',
        evaluator_identifier: 'baseline',
        evaluator_version: '1.0',
        framework_identifier: 'apex-spikes-afce',
        framework_version: '1.0',
        transcript_hash: 'a'.repeat(64),
        execution_mode: 'offline',
        status: 'success',
        created_at: '2026-01-01T00:00:00Z',
        transcript_matches_current: true,
      },
      {
        run_uuid: 'run-2',
        item1_run_id: 'r2',
        evaluator_identifier: 'baseline',
        evaluator_version: '1.0',
        framework_identifier: 'apex-spikes-afce',
        framework_version: '1.0',
        transcript_hash: 'a'.repeat(64),
        execution_mode: 'offline',
        status: 'success',
        created_at: '2026-01-02T00:00:00Z',
        transcript_matches_current: true,
      },
    ])
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
  })

  it('redirects a bare session URL to the overview tab', async () => {
    renderWorkspace('/research/evaluate/42')
    await waitFor(() => {
      expect(screen.getByText('Hello')).toBeInTheDocument()
    })
    expect(screen.getByRole('heading', { name: 'Transcript' })).toBeInTheDocument()
  })

  it('renders tab links pointing at the five relative tab paths', async () => {
    renderWorkspace('/research/evaluate/42/overview')
    await waitFor(() => {
      expect(screen.getByText('Session 42 evaluation workspace')).toBeInTheDocument()
    })
    const nav = screen.getByRole('navigation', { name: /evaluation workspace tabs/i })
    const hrefs = Array.from(nav.querySelectorAll('a')).map((a) => a.getAttribute('href'))
    expect(hrefs).toEqual([
      '/research/evaluate/42/overview',
      '/research/evaluate/42/run',
      '/research/evaluate/42/runs',
      '/research/evaluate/42/review',
      '/research/evaluate/42/export',
    ])
  })

  it('renders the sticky header status strip from shared hook state', async () => {
    renderWorkspace('/research/evaluate/42/overview')
    await waitFor(() => {
      expect(screen.getByText('Session 42 evaluation workspace')).toBeInTheDocument()
    })
    await waitFor(() => {
      // Two saved runs were mocked; the status strip's "Saved runs" stat should reflect it.
      expect(screen.getByText('2')).toBeInTheDocument()
    })
    expect(screen.getByText('None')).toBeInTheDocument() // Annotation set: no set created yet
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(1) // Coverage / Last updated
    expect(screen.getByText('completed')).toBeInTheDocument() // session state pill
  })
})
